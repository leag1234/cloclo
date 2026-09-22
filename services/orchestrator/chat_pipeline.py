"""Chat uses the bounded harness and resolves citations through retrieval HTTP."""

from packages.limits import LimitError
from packages.validation import describe_validation
from pydantic import ValidationError

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
                and os.environ.get("ATLAS_SEARCH_PROVIDER") == "tavily"
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
                    else "provider failed or returned no results"
                )
                raise GatewayError(
                    "search_unavailable",
                    503,
                    f"Web search unavailable: {reason}. No verified result was obtained "
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
        per_source = max(1, budget // len(rows))
        result = copy.deepcopy(data)
        copied = result["results"]
        assert isinstance(copied, list)
        for row in copied:
            if not isinstance(row, dict) or not isinstance(row.get("content"), str):
                continue
            text = row["content"]
            measured = len(text.encode())
            if measured <= per_source:
                continue
            parts = select_text(text, self.question, per_source)
            selected = "\n".join(part.text for part in parts)
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
    if item.state == "done":
        item.reponse = clean_answer(item.reponse)


async def _process(request: ChatRequest, item: Interaction) -> None:
    # Attachments take precedence over project/corpus commands and lexical routing.
    if request.documents and os.environ.get("ATLAS_TERMINAL_ENABLED") != "1":
        from services.orchestrator.document_chat import process_documents

        await process_documents(request, item)
        return
    from services.orchestrator.project_commands import select

    if not request.documents and await select(request, item, retrieval_url()):
        return
    if request.project_id is not None and not request.documents:
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
        if not followup and not request.documents
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
    model.configure_quality(
        request.model,
        request.max_tokens,
        has_attachments=bool(request.documents),
        produces_files=produces_files,
    )
    item.reasoning_effort = request.reasoning_effort
    model.local_enabled = os.environ.get("GPU_LOCAL", "0") == "1"
    item.cout_eur = (
        0.30 if request.documents or produces_files else 0.10
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
                cost=Decimal("0.30" if request.documents or produces_files else "0.10"),
                has_attachments=bool(request.documents),
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
        item.reponse, item.state, item.cout_eur = (
            result.text,
            result.state,
            float(result.cost),
        )
        if tools.terminal is not None:
            item.terminal_commands = tools.terminal.commands
            item.terminal_failed_commands = tools.terminal.failed_commands
            item.files = tools.terminal.files
            if result.state == "done" and item.files:
                from services.orchestrator.file_results import render_files

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
    finally:
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
