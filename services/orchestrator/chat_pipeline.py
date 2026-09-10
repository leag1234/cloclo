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
from services.orchestrator.model import GatewayModel
from services.orchestrator.tools import Rag, Runtime


class Source(BaseModel):
    chunk_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    doc_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=32000)


class Passage(Source):
    score: float = Field(allow_inf_nan=False)


class Passages(BaseModel):
    passages: list[Passage] = Field(max_length=8)


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
    keys = list(dict.fromkeys(re.findall(r"\b[a-f0-9]{64}\b", item.reponse)))
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
    def __init__(self, item: Interaction) -> None:
        super().__init__(
            Cache(Path(os.environ.get("ATLAS_WEB_CACHE", "BRAIN/web-cache.sqlite"))),
            Decimal(0),
        )
        self.item = item

    async def execute(self, call: Call, timeout: float) -> Message:
        if call.name != "rag_search":
            output = await super().execute(call, timeout)
            if "error" in output:
                self.item.erreurs.append(str(output["error"]))
            return output
        started = time.monotonic()
        try:
            request = Rag.model_validate_json(call.arguments)
            result = Passages.model_validate(
                await GatewayModel.post(
                    retrieval_url() + "/search", request.model_dump(), timeout
                )
            )
            passages = [p.model_dump() for p in result.passages]
            self.item.chunks_recuperes.extend(passages)
            return {
                "trust": "untrusted",
                "data": {
                    "passages": [
                        {
                            "chunk_id": p.chunk_id,
                            "source": p.source,
                            "text": p.text.encode()[:1200].decode(
                                "utf-8", errors="ignore"
                            ),
                        }
                        for p in result.passages
                    ]
                },
            }
        except (ValueError, RuntimeError, TimeoutError):
            self.item.erreurs.append("retrieval_unavailable")
            return {"error": "retrieval_unavailable"}
        finally:
            self.item.latence_ms["retrieval"] += (time.monotonic() - started) * 1000


async def process(request: ChatRequest, item: Interaction) -> None:
    started = time.monotonic()
    model = await GatewayModel.connect(
        os.environ.get("ATLAS_GATEWAY_URL", "http://127.0.0.1:8010"),
        local_enabled=os.environ.get("GPU_LOCAL", "0") == "1",
    )
    model.observing = True
    model.local_enabled = os.environ.get("GPU_LOCAL", "0") == "1"
    item.cout_eur = 0.05  # Conservative upper bound until the loop returns its ledger.
    tools = ChatTools(item)
    try:
        result = await run(
            Query(question=request.messages[-1].content, lang=request.lang),
            model,
            tools,
            Path("prompts/agent.txt").read_text()
            + Path("prompts/chat.txt").read_text(),
            Limits(wall_clock=max(0, 120 - (time.monotonic() - started))),
            history=[m.model_dump() for m in request.messages[:-1]],
        )
        item.reponse, item.state, item.cout_eur = (
            result.text,
            result.state,
            float(result.cost),
        )
        if result.reason:
            item.erreurs.append(result.reason)
        if result.state == "done":
            await render_citations(item)
    finally:
        item.tokens = {"in": model.input_tokens, "out": model.output_tokens}
        item.latence_ms["generation"] = model.generation_ms
        if model.observations:
            item.modele_utilise = model.observations[-1].provider
            item.route_decision = model.observations[0].route
