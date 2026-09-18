"""Chat uses the bounded harness and resolves citations through retrieval HTTP."""

import json
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
from services.orchestrator.search_policy import required_research
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
                raise ValueError("invalid_citation")
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
        if call.name == "generate_image":
            if not self.allow_image:
                return {"error": "tool_unavailable"}
            try:
                self.image_prompt = GenerateImage.model_validate_json(
                    call.arguments
                ).prompt
                return {"selected": "generate_image"}
            except ValueError:
                return {"error": "invalid_image_arguments"}
        if call.name != "rag_search":
            output = await super().execute(call, timeout)
            data = output.get("data")
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


async def process(request: ChatRequest, item: Interaction) -> None:
    from services.orchestrator.narration import clean_answer

    await _process(request, item)
    if item.state == "done":
        item.reponse = clean_answer(item.reponse)


async def _process(request: ChatRequest, item: Interaction) -> None:
    # Attachments take precedence over project/corpus commands and lexical routing.
    if request.documents:
        from services.orchestrator.document_chat import process_documents

        await process_documents(request, item)
        return
    from services.orchestrator.project_commands import select

    if await select(request, item, retrieval_url()):
        return
    if request.project_id is not None:
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
    if not followup and request.messages[-1].images:
        await process_vision(request, item)
        return
    started = time.monotonic()
    model = await GatewayModel.connect(
        os.environ.get("ATLAS_GATEWAY_URL", "http://127.0.0.1:8010"),
        local_enabled=os.environ.get("GPU_LOCAL", "0") == "1",
    )
    if followup:
        model.tools = []
    else:
        model.tools.append(declaration())
    model.observing = True
    model.sink = sink_context.get()
    model.configure_quality(request.model, request.max_tokens)
    item.reasoning_effort = request.reasoning_effort
    model.local_enabled = os.environ.get("GPU_LOCAL", "0") == "1"
    item.cout_eur = 0.1  # Conservative upper bound until the loop returns its ledger.
    tools = ChatTools(item, request.messages[-1].text, allow_image=not followup)
    try:
        result = await run(
            Query(question=iteration or request.messages[-1].text, lang=request.lang),
            model,
            tools,
            Path("prompts/chat-agent.txt").read_text()
            + Path("prompts/chat.txt").read_text()
            + Path("prompts/web-chat.txt").read_text()
            + (Path("prompts/followup.txt").read_text() if followup else "")
            + language_instruction(request.lang),
            Limits(
                profile=request.model,
                tokens=262144,
                cost=Decimal("0.10"),
                wall_clock=max(
                    0, request.timeout_seconds - (time.monotonic() - started)
                ),
            ),
            history=[
                {"role": m.role, "content": m.text} for m in request.messages[:-1]
            ],
            retry_web=True,
            initial_calls=required_research(request.messages[-1].text, request.lang)
            if not followup
            else (),
            terminal_tools=frozenset({"generate_image"})
            if not followup
            else frozenset(),
        )
        item.reponse, item.state, item.cout_eur = (
            result.text,
            result.state,
            float(result.cost),
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
