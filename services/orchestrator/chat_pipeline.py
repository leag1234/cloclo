"""Chat uses the bounded harness and resolves citations through retrieval HTTP."""

from packages.limits import LimitError
from packages.validation import describe_validation
from pydantic import ValidationError

import asyncio
import json
import copy
import os
import re
import time
from decimal import Decimal
from pathlib import Path

import aiohttp
from pydantic import BaseModel, Field

from services.orchestrator.cache import Cache
from services.orchestrator.chat_schema import ChatRequest
from services.orchestrator.interactions import Interaction
from services.orchestrator.loop import Call, Limits, Message, Query, run
from services.orchestrator.model import GatewayError, GatewayModel
from services.orchestrator.tools import Rag, Runtime
from services.orchestrator.stream_client import sink_context
from services.orchestrator.vision import process_vision
from services.orchestrator.search_policy import required_research, corpus_allowed
from services.orchestrator.followup import is_followup, image_iteration
from packages.language import conversation_language, language_instruction
from services.orchestrator.image_tool import GenerateImage, declaration, finish


class Source(BaseModel):
    chunk_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    doc_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=32000)


class Passage(Source):
    score: float = Field(allow_inf_nan=False)


class Passages(BaseModel):
    passages: list[Passage] = Field(max_length=8)


def select_passages(
    passages: list[Passage], query: str = "", token_budget: int = 1000
) -> list[dict[str, str]]:
    from packages.evidence import whole_chunks

    return whole_chunks(
        [
            {"chunk_id": p.chunk_id, "source": p.source, "text": p.text}
            for p in sorted(passages, key=lambda p: p.score, reverse=True)
        ],
        token_budget,
    )


def retrieval_url() -> str:
    return os.environ.get("ATLAS_RETRIEVAL_URL", "http://127.0.0.1:8011").rstrip("/")


async def source(key: str) -> dict[str, object]:
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=5), trust_env=False
    ) as client:
        async with client.get(
            retrieval_url() + "/sources/" + key, allow_redirects=False
        ) as response:
            if response.status != 200:
                raise ValueError("invalid_citation")
            body = await response.read()
            if len(body) > 800000:
                raise LimitError("source_response_limit", len(body), 800000, "bytes")
    return Source.model_validate(json.loads(body)).model_dump()


async def render_citations(item: Interaction) -> None:
    uncited = re.sub(r"\[[^\]]*\]\([^)]*/sources/[a-f0-9]{64}\)", "", item.reponse)
    keys = list(dict.fromkeys(re.findall(r"\b[a-f0-9]{64}\b", uncited)))
    retrieved = {str(p["chunk_id"]): p for p in item.chunks_recuperes}
    if not set(keys) <= retrieved.keys():
        raise ValueError("invalid_citation")
    for number, key in enumerate(keys, 1):
        resolved = await source(key)
        if any(
            resolved[k] != retrieved[key][k]
            for k in ("chunk_id", "doc_id", "source", "text")
        ):
            raise ValueError("citation_changed")
        item.citations.append(resolved)
        url = os.environ.get("ATLAS_PUBLIC_URL", "http://localhost:8020").rstrip("/")
        item.reponse = re.sub(
            r"[`\[]?" + key + r"[`\]]?",
            f"[Source {number}]({url}/sources/{key})",
            item.reponse,
        )


class ChatTools(Runtime):
    def __init__(
        self, item: Interaction, question: str = "", allow_image: bool = False
    ) -> None:
        super().__init__(
            Cache(Path(os.environ.get("ATLAS_WEB_CACHE", "BRAIN/web-cache.sqlite"))),
            Decimal(0),
            question,
        )
        self.item = item
        self.allow_image = allow_image
        self.image_prompt: str | None = None
        self.source_truncated = False
        self.model: GatewayModel | None = None
        self.terminal = None
        if os.environ.get("ATLAS_TERMINAL_ENABLED") == "1":
            from services.orchestrator.terminal_client import TerminalClient

            self.terminal = TerminalClient(item.request_id)

    async def execute(self, call: Call, timeout: float) -> Message:
        sink = sink_context.get()
        urls: list[str] = []
        try:
            arguments = json.loads(call.arguments)
            if call.name == "web_fetch" and isinstance(arguments.get("url"), str):
                urls.append(arguments["url"])
        except (ValueError, AttributeError):
            pass
        if sink:
            await sink({"phase": "tool_started", "tool": call.name, "urls": urls})
        if call.name in {"terminal_command", "publish_document"}:
            from services.orchestrator.terminal_client import Command, Publish

            if self.terminal is None:
                return {"error": "terminal_unavailable"}
            try:
                if call.name == "terminal_command":
                    output = await self.terminal.execute(
                        Command.model_validate_json(call.arguments).command, timeout
                    )
                    if self.model is not None and self.model.has_attachments:
                        output = self.document_evidence(output)
                else:
                    publication = Publish.model_validate_json(call.arguments)
                    output = await self.terminal.publish(
                        publication.path, publication.strategy, timeout
                    )
                    self.item.files = list(self.terminal.files)
                    self.item.file_strategies = list(self.terminal.strategies)
                if call.name == "terminal_command" and (
                    output.get("error") or output.get("exit_code", 0) != 0
                ):
                    self.item.erreurs.append("terminal_operation_failed")
                    return {"error": "terminal_operation_failed", "data": output}
                if self.model is not None and self.model.required_file_tool:
                    if call.name == "terminal_command":
                        self.model.required_file_tool = "publish_document"
                    elif all(
                        any(url.endswith("." + ext) for url in self.terminal.files)
                        for ext in self.model.required_file_formats
                    ):
                        self.model.required_file_tool = None
                return {"trust": "untrusted", "data": output}
            except LimitError as exc:
                return {"error": exc.code, "message": exc.detail}
            except ValidationError as exc:
                return {
                    "error": "invalid_arguments",
                    "message": describe_validation(exc),
                }
            except (ValueError, RuntimeError, aiohttp.ClientError, TimeoutError):
                self.item.erreurs.append("terminal_operation_failed")
                return {"error": "terminal_operation_failed"}
        if call.name == "generate_image":
            if not self.allow_image:
                return {"error": "tool_unavailable"}
            try:
                self.image_prompt = GenerateImage.model_validate_json(
                    call.arguments
                ).prompt
                return {"selected": "generate_image"}
            except ValidationError as exc:
                return {
                    "error": "invalid_image_arguments",
                    "message": describe_validation(exc),
                }
            except ValueError:
                return {"error": "invalid_image_arguments"}
        if call.name != "rag_search":
            output = await super().execute(call, timeout)
            data = output.get("data")
            if call.name == "web_search" and isinstance(data, dict):
                data = self.search_evidence(data)
                output = {**output, "data": data}
            if isinstance(data, dict):
                self.source_truncated |= data.get("truncated") is True
                if isinstance(data.get("url"), str):
                    urls = [data["url"]]
                results = data.get("results")
                if isinstance(results, list):
                    urls = [
                        str(r["link"])
                        for r in results
                        if isinstance(r, dict) and isinstance(r.get("link"), str)
                    ]
            if call.name in {"web_search", "web_fetch"} and "error" not in output:
                self.item.retrieved_urls.extend(urls)
            if "error" in output:
                self.item.erreurs.append(str(output["error"]))
            sink = sink_context.get()
            if sink:
                await sink(
                    {
                        "phase": "tool_finished",
                        "tool": call.name,
                        "urls": urls,
                        "ok": "error" not in output,
                    }
                )
            if sink and isinstance(data, dict):
                if data.get("synthesis"):
                    await sink(
                        {"phase": "synthesized", "tool": call.name, "urls": urls}
                    )
                if data.get("truncated"):
                    await sink(
                        {"phase": "source_truncated", "tool": call.name, "urls": urls}
                    )
            if (
                call.name == "web_search"
                and (
                    os.environ.get("ATLAS_SEARCH_PROVIDER") == "tavily"
                    or output.get("error") in {"quota_exceeded", "search_rate_limited"}
                )
                and (
                    "error" in output
                    or not isinstance(data, dict)
                    or not data.get("results")
                )
            ):
                # Stop before another inference can silently replace failed research
                # with remembered facts, including during streamed responses.
                reason = (
                    "quota exhausted"
                    if output.get("error") == "quota_exceeded"
                    else "hourly limit reached"
                    if output.get("error") == "search_rate_limited"
                    else "provider failed or returned no results"
                )
                raise GatewayError(
                    str(output["error"])
                    if output.get("error") in {"quota_exceeded", "search_rate_limited"}
                    else "search_unavailable",
                    503,
                    f"Web search unavailable: {reason}. "
                    + (
                        f"Provider HTTP {output['provider_status']}. "
                        if type(output.get("provider_status")) is int
                        else ""
                    )
                    + "No verified result was obtained "
                    "(required: at least 1). I cannot verify this answer from current sources. "
                    "Search limits: 3 calls per request and 900 local reservations per month.",
                )
            return output
        started = time.monotonic()
        if not corpus_allowed(self.question):
            return {"error": "corpus_excluded_by_user"}
        succeeded = False
        try:
            request = Rag.model_validate_json(call.arguments)
            result = Passages.model_validate(
                await GatewayModel.post(
                    retrieval_url() + "/search", request.model_dump(), timeout
                )
            )
            succeeded = True
            passages = [p.model_dump() for p in result.passages]
            self.item.chunks_recuperes.extend(passages)
            return {
                "trust": "untrusted",
                "data": {
                    "passages": select_passages(result.passages, request.query, 8000)
                },
            }
        except LimitError as exc:
            return {"error": exc.code, "message": exc.detail}
        except ValidationError as exc:
            self.item.erreurs.append("retrieval_unavailable")
            if any(
                error.get("ctx", {}).get("max_length") is not None
                for error in exc.errors()
            ):
                return {
                    "error": "retrieval_unavailable",
                    "message": describe_validation(exc),
                }
            return {"error": "retrieval_unavailable"}
        except (ValueError, RuntimeError, TimeoutError):
            self.item.erreurs.append("retrieval_unavailable")
            return {"error": "retrieval_unavailable"}
        finally:
            if sink:
                await sink(
                    {
                        "phase": "tool_finished",
                        "tool": call.name,
                        "urls": [],
                        "ok": succeeded,
                    }
                )
            self.item.latence_ms["retrieval"] += (time.monotonic() - started) * 1000

    def search_evidence(self, data: Message) -> Message:
        """Budget evidence for the next inference; every later step rechecks cost."""
        from services.orchestrator.content import select_passages as select_text

        rows = data.get("results")
        if self.model is None or not isinstance(rows, list) or not rows:
            return data
        price = self.model.configuration.input_eur_per_mtok
        if price <= 0:
            return data
        # Account for JSON escaping and retain half the allowance for output
        # and other context. Do not reserve ten hypothetical future calls.
        budget = max(1, int(self.model.allowance * 1000000 / (price * 2 * 2)))
        if self.model.produces_files:
            budget = min(budget, 8000)
        per_source = max(1, budget // len(rows))
        result = copy.deepcopy(data)
        copied = result["results"]
        assert isinstance(copied, list)
        for row in copied:
            if not isinstance(row, dict) or not isinstance(row.get("content"), str):
                continue
            if self.model.produces_files and isinstance(row.get("snippet"), str):
                row["snippet"] = row["snippet"][:per_source]
            text = row["content"]
            measured = len(text.encode())
            if measured <= per_source:
                continue
            parts = select_text(text, self.question, per_source)
            selected = "\n".join(part.text for part in parts)
            if self.model.produces_files:
                selected = selected.encode()[:per_source].decode("utf-8", "ignore")
            row.update(
                content=selected,
                source_bytes=measured,
                preview_limit_bytes=per_source,
                truncated=True,
                detail=f"Selected {len(selected.encode())} of {measured} preview bytes; limit {per_source} bytes. Use web_fetch on the source link for full evidence.",
            )
        return result

    def document_evidence(self, output: Message) -> Message:
        """Apply M10 to complete output before reserving another inference."""
        from services.orchestrator.content import hierarchical_summary

        entries = output.get("output")
        if (
            self.model is None
            or output.get("exit_code") != 0
            or not isinstance(entries, list)
        ):
            return output
        text = "\n".join(
            entry["data"]
            for entry in entries
            if isinstance(entry, dict) and isinstance(entry.get("data"), str)
        )
        size = len(text.encode())
        reservation = size * 2 * self.model.configuration.input_eur_per_mtok / 1_000_000
        # Retain room for history, escaped tool results and the final answer.
        if size <= 131072 and reservation <= self.model.allowance / 2:
            return output
        summary, _, sections = hierarchical_summary(text, self.question)
        metadata: dict[str, str | int | bool] = {
            "hierarchical_synthesis": True,
            "source_characters": len(text),
            "source_bytes": size,
            "selected_characters": len(summary),
            "sections_examined": sections,
            "remaining_budget_eur": str(self.model.allowance),
            "estimated_evidence_reservation_eur": str(reservation),
        }
        self.item.documents.append(metadata)
        return {
            **output,
            "output": [{"type": "output", "data": summary}],
            "truncated": True,
            "detail": (
                f"Selected {len(summary)} of {len(text)} characters within the "
                f"remaining {self.model.allowance} EUR budget. These extracts are "
                "not a complete reading. For an exhaustive summary, read all "
                "remaining sections in bounded outputs; otherwise state the gap."
            ),
            "synthesis": metadata,
        }


async def process(request: ChatRequest, item: Interaction) -> None:
    from services.orchestrator.narration import clean_answer

    await _process(request, item)
    if item.state == "done" and any(
        d.get("hierarchical_synthesis") for d in item.documents
    ):
        labels = json.loads(Path("prompts/activity-labels.json").read_text())
        notice = labels.get(request.lang, labels["en"])["synthesized"]
        if not item.reponse.endswith(notice):
            item.reponse += "\n\n" + notice
    if item.state == "done" and item.task_type not in {
        "imagegen",
        "vision",
    }:
        from services.orchestrator.source_truth import (
            without_unretrieved,
            source_footer,
        )

        item.reponse = without_unretrieved(
            clean_answer(item.reponse),
            set(item.retrieved_urls)
            | {str(c.get("source")) for c in item.citations}
            | set(
                re.findall(
                    re.escape(
                        os.environ.get(
                            "ATLAS_PUBLIC_URL", "http://localhost:8020"
                        ).rstrip("/")
                    )
                    + r"/sources/[a-f0-9]{64}",
                    item.reponse,
                )
            ),
        )
        item.reponse += source_footer(item.retrieved_urls, request.lang)


async def _process(request: ChatRequest, item: Interaction) -> None:
    # Attachments take precedence over project/corpus commands and lexical routing.
    if request.documents and os.environ.get("ATLAS_TERMINAL_ENABLED") != "1":
        from services.orchestrator.document_chat import process_documents

        await process_documents(request, item)
        return
    from services.orchestrator.project_commands import select

    if not request.has_attachments and await select(request, item, retrieval_url()):
        return
    if request.project_id is not None and not request.has_attachments:
        from services.orchestrator.project_chat import process_project

        await process_project(request, item)
        return
    request = request.model_copy(
        update={"lang": conversation_language(request.messages, request.ui_locale)}
    )
    followup = is_followup(request.messages)
    if followup:
        item.task_type = "followup"
    iteration = image_iteration(request.messages)
    if not followup and request.messages[-1].images and not request.documents:
        await process_vision(request, item)
        return
    started = time.monotonic()
    model = await GatewayModel.connect(
        os.environ.get("ATLAS_GATEWAY_URL", "http://127.0.0.1:8010"),
        local_enabled=os.environ.get("GPU_LOCAL", "0") == "1",
    )
    discovery = (
        required_research(
            request.messages[-1].text,
            request.lang,
            device_timings=os.environ.get("ATLAS_SEARCH_PROVIDER") == "tavily",
        )
        if not followup and not request.has_attachments
        else ()
    )
    if followup and os.environ.get("ATLAS_TERMINAL_ENABLED") != "1":
        model.tools = []
    else:
        model.tools.append(declaration())
    if os.environ.get("ATLAS_TERMINAL_ENABLED") == "1":
        model.tools.extend(json.loads(Path("prompts/file-tools.json").read_text()))
        if request.documents:
            model.tools = [
                t
                for t in model.tools
                if isinstance(function := t.get("function"), dict)
                and function.get("name") != "rag_search"
            ]
    if not corpus_allowed(request.messages[-1].text):
        model.tools = [
            tool
            for tool in model.tools
            if isinstance(function := tool.get("function"), dict)
            and function.get("name") != "rag_search"
        ]
    model.observing = True
    model.sink = sink_context.get()
    from packages.file_intent import produces_file

    produces_files = produces_file(request.messages[-1].text)
    if (
        os.environ.get("ATLAS_TERMINAL_ENABLED") == "1"
        and not produces_files
        and not request.has_attachments
    ):
        model.tools = [
            tool
            for tool in model.tools
            if isinstance(function := tool.get("function"), dict)
            and function.get("name") not in {"terminal_command", "publish_document"}
        ]
    model.configure_quality(
        request.model,
        request.max_tokens,
        has_attachments=request.has_attachments,
        produces_files=produces_files,
    )
    item.reasoning_effort = request.reasoning_effort
    model.local_enabled = os.environ.get("GPU_LOCAL", "0") == "1"
    item.cout_eur = (
        0.30 if request.has_attachments or produces_files else 0.10
    )  # Reserved until ledger returns.
    tools = ChatTools(item, request.messages[-1].text, allow_image=not followup)
    tools.model = model
    file_context = ""
    if tools.terminal is not None:
        await tools.terminal.initialize()
        paths = [
            await tools.terminal.upload(document, request.timeout_seconds)
            for document in request.documents
        ]
        file_context = (
            Path("prompts/files.txt").read_text()
            + "\n"
            + json.dumps(
                {"request_directory": tools.terminal.root, "attachments": paths},
                ensure_ascii=False,
            )
        )
    try:
        result = await run(
            Query(question=iteration or request.messages[-1].text, lang=request.lang),
            model,
            tools,
            Path("prompts/chat.txt").read_text()
            + Path("prompts/chat-agent.txt").read_text()
            + Path("prompts/web-chat.txt").read_text()
            + (
                Path("prompts/tavily.txt").read_text()
                if os.environ.get("ATLAS_SEARCH_PROVIDER") == "tavily"
                else ""
            )
            + (Path("prompts/followup.txt").read_text() if followup else "")
            + language_instruction(request.lang)
            + file_context,
            Limits(
                profile=request.model,
                tokens=None,
                cost=Decimal(
                    "0.30" if request.has_attachments or produces_files else "0.10"
                ),
                has_attachments=request.has_attachments,
                produces_files=produces_files,
                wall_clock=max(
                    0, request.timeout_seconds - (time.monotonic() - started)
                ),
            ),
            history=[
                {"role": m.role, "content": m.text} for m in request.messages[:-1]
            ],
            retry_web=True,
            initial_calls=discovery,
            terminal_tools=frozenset({"generate_image"})
            if not followup
            else frozenset(),
        )
        from services.orchestrator.file_content import answer_content, requested_formats

        formats = requested_formats(request.messages[-1].text)
        preserve_code = bool(
            re.search(
                r"\b(?:script|code|python|sql|function|fonction|programm)\b",
                request.messages[-1].text,
                re.I,
            )
        )
        file_recovery_attempted = False
        if (
            produces_files
            and tools.terminal is not None
            and not tools.terminal.files
            and tools.terminal.commands == 0
            and "terminal_operation_failed" not in item.erreurs
            and result.tool_calls <= 7
        ):
            file_recovery_attempted = True
            first_result = result
            remaining_seconds = max(
                0, request.timeout_seconds - (time.monotonic() - started)
            )
            remaining_cost = max(Decimal(0), Decimal("0.30") - first_result.cost)
            if remaining_seconds > 0 and remaining_cost > 0:
                # The same model retains its spending ledger. Recovery only needs
                # file tools; reopening search would reset its per-request quotas.
                model.spent = max(model.spent, first_result.cost)
                model.tools = [
                    tool
                    for tool in model.tools
                    if isinstance(function := tool.get("function"), dict)
                    and function.get("name") in {"terminal_command", "publish_document"}
                ]
                model.required_file_tool = "terminal_command"
                model.required_file_formats = formats
                recovery_history: list[Message] = [
                    {"role": m.role, "content": m.text} for m in request.messages
                ]
                recovery_history.append(
                    {"role": "assistant", "content": first_result.text}
                )
                try:
                    result = await run(
                        Query(
                            question=iteration or request.messages[-1].text,
                            lang=request.lang,
                        ),
                        model,
                        tools,
                        Path("prompts/chat.txt").read_text()
                        + Path("prompts/chat-agent.txt").read_text()
                        + language_instruction(request.lang)
                        + file_context
                        + "\n\nFile-delivery recovery: the prior answer produced no file. "
                        "Use terminal_command to create the requested files from the "
                        "actual answer content, then publish_document for each file. "
                        "Follow the original request and its language for all titles "
                        "and content. For a presentation with PDF, render the same "
                        "substantive slide content into both formats, one PDF page per "
                        "slide. Never add placeholder or filler pages. Do not claim a "
                        "file or link exists unless publish_document succeeded. If "
                        "creation fails, return the actual requested content inline "
                        "and explain the failure in the request language.",
                        Limits(
                            profile=request.model,
                            tokens=None,
                            tool_calls=10 - first_result.tool_calls,
                            cost=remaining_cost,
                            has_attachments=request.has_attachments,
                            produces_files=True,
                            wall_clock=max(0, remaining_seconds - 30),
                        ),
                        history=recovery_history,
                    )
                    result.cost += first_result.cost
                    result.tool_calls += first_result.tool_calls
                except GatewayError as exc:
                    # Unknown failed usage retains the full remaining reservation.
                    # A delivery failure must not discard an already usable answer.
                    item.erreurs.append(exc.code)
                    item.provider_retries += exc.retries
                    result = first_result
                    result.cost += remaining_cost
            # Preserve substantive first-pass evidence, never an invented recovery URL.
            if not tools.terminal.files:
                result.text = first_result.text.strip() or result.text.strip()
        if produces_files and tools.terminal is not None:
            from services.orchestrator.file_content import render_command
            from services.orchestrator.file_results import inline_fallback

            terminal_already_failed = "terminal_operation_failed" in item.erreurs
            missing = tuple(
                ext
                for ext in formats
                if not any(url.endswith("." + ext) for url in tools.terminal.files)
            )
            if missing and "terminal_operation_failed" not in item.erreurs:
                command, paths = render_command(result.text, missing)
                remaining = request.timeout_seconds - (time.monotonic() - started)
                if (
                    command
                    and result.tool_calls + 1 + len(paths) <= 10
                    and remaining > 0
                    and result.cost < Decimal("0.30")
                ):
                    # Deterministic rendering uses no inference; all I/O stays in
                    # the original deadline and remaining tool allowance.
                    result.tool_calls += 1
                    try:
                        async with asyncio.timeout(remaining):
                            created = await tools.execute(
                                Call(
                                    "content-render",
                                    "terminal_command",
                                    json.dumps({"command": command}),
                                ),
                                min(30, remaining),
                            )
                            data = created.get("data")
                            if (
                                isinstance(data, dict)
                                and data.get("exit_code") == 0
                                and not created.get("error")
                            ):
                                for path in paths:
                                    remaining = request.timeout_seconds - (
                                        time.monotonic() - started
                                    )
                                    if remaining <= 0:
                                        break
                                    result.tool_calls += 1
                                    await tools.execute(
                                        Call(
                                            "content-publish-" + path,
                                            "publish_document",
                                            json.dumps(
                                                {"path": path, "strategy": "created"}
                                            ),
                                        ),
                                        min(30, remaining),
                                    )
                    except TimeoutError:
                        item.erreurs.append("file_render_timeout")
            missing = tuple(
                ext
                for ext in formats
                if not any(url.endswith("." + ext) for url in tools.terminal.files)
            )
            if not tools.terminal.files or missing:
                if not terminal_already_failed or file_recovery_attempted:
                    result.text = inline_fallback(
                        result.text,
                        request.lang,
                        preserve_code=preserve_code,
                        partial=bool(tools.terminal.files),
                    )
                    result.state = "done"
                    result.reason = "file_not_produced"
                else:
                    result.text = answer_content(
                        result.text, preserve_code=preserve_code
                    )
            else:
                result.text = answer_content(result.text, preserve_code=preserve_code)
        elif produces_files:
            from services.orchestrator.file_results import inline_fallback

            result.text = inline_fallback(
                result.text, request.lang, preserve_code=preserve_code
            )
        item.reponse, item.state, item.cout_eur = (
            result.text,
            result.state,
            float(result.cost),
        )
        if tools.terminal is not None:
            item.terminal_commands = tools.terminal.commands
            item.terminal_failed_commands = tools.terminal.failed_commands
            item.files = tools.terminal.files
            if item.files:
                from services.orchestrator.file_results import render_files

                if result.state != "done":
                    # Published files remain usable even if closing prose fails.
                    item.erreurs.append(result.reason or "closing_answer_failed")
                    item.state = "done"
                item.reponse = render_files(
                    item.reponse, item.files, tools.terminal.strategies, request.lang
                )
        if result.state == "done" and tools.image_prompt is not None:
            await finish(request, item, result, tools.image_prompt, started)
            return
        if result.reason:
            item.erreurs.append(result.reason)
        if result.state == "done" and not followup:
            await render_citations(item)
        if tools.source_truncated:
            labels = json.loads(Path("prompts/activity-labels.json").read_text())
            item.reponse += (
                "\n\n" + labels.get(request.ui_locale, labels["en"])["source_truncated"]
            )
    except GatewayError as exc:
        if tools.terminal is None or not tools.terminal.files:
            raise
        from services.orchestrator.file_results import render_files

        item.files = list(tools.terminal.files)
        item.file_strategies = list(tools.terminal.strategies)
        item.terminal_commands = tools.terminal.commands
        item.terminal_failed_commands = tools.terminal.failed_commands
        item.erreurs.append(exc.code)
        item.provider_retries += exc.retries
        item.reponse = render_files(
            exc.detail, item.files, item.file_strategies, request.lang
        )
        item.state = "done"
    finally:
        item.provider_retries += model.provider_retries
        item.tokens = {"in": model.input_tokens, "out": model.output_tokens}
        item.provider_model = model.provider_model
        item.reasoning = model.reasoning
        item.trace_tokens, item.answer_tokens = model.trace_tokens, model.answer_tokens
        item.token_split_estimated = model.token_split_estimated
        item.reasoning_retried = model.reasoning_retried
        item.latence_ms["generation"] = model.generation_ms
        if model.observations and item.task_type != "imagegen":
            item.modele_utilise = model.observations[-1].provider
            item.route_decision = model.observations[0].route
