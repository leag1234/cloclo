"""Project chat: scoped retrieval, automatic facts and one shared bounded ledger."""

import json
import os
import re
import time
from pathlib import Path

from pydantic import BaseModel, Field

from services.orchestrator.chat_pipeline import (
    ChatTools,
    Passages,
    Source,
    retrieval_url,
    select_passages,
)
from services.orchestrator.chat_schema import ChatRequest
from services.orchestrator.interactions import Interaction
from services.orchestrator.loop import Call, Limits, Message, Query, run
from services.orchestrator.memory import consolidated
from services.orchestrator.model import GatewayModel
from services.orchestrator.tools import Rag


class MemoryFact(BaseModel):
    id: str
    text: str = Field(max_length=500)
    kind: str


class HistoryTurn(BaseModel):
    question: str
    answer: str


class Context(BaseModel):
    instructions: str = Field(max_length=4000)
    revision: int = Field(ge=0)
    facts: list[MemoryFact] = Field(max_length=8)
    history: list[HistoryTurn] = Field(max_length=8)


class ProjectTools(ChatTools):
    def __init__(self, item: Interaction, project: str) -> None:
        super().__init__(item)
        self.project = project

    async def execute(self, call: Call, timeout: float) -> Message:
        # Memory must never be sent to an external web search engine.
        if call.name != "rag_search":
            return {"error": "tool_unavailable"}
        started = time.monotonic()
        try:
            request = Rag.model_validate_json(call.arguments)
            result = Passages.model_validate(
                await GatewayModel.post(
                    retrieval_url() + f"/projects/{self.project}/search",
                    request.model_dump(),
                    timeout,
                )
            )
            passages = [p.model_dump() for p in result.passages]
            self.item.chunks_recuperes.extend(passages)
            return {
                "trust": "untrusted",
                "data": {"passages": select_passages(result.passages)},
            }
        finally:
            self.item.latence_ms["retrieval"] += (time.monotonic() - started) * 1000


async def process_project(request: ChatRequest, item: Interaction) -> None:
    started = time.monotonic()
    project = request.project_id
    base = retrieval_url() + f"/projects/{project}"
    question = request.messages[-1].content
    context = Context.model_validate(
        await GatewayModel.post(
            base + "/context",
            {
                "conversation_id": request.conversation_id,
                "query": question,
            },
            5,
        )
    )
    model = await GatewayModel.connect(
        os.environ.get("ATLAS_GATEWAY_URL", "http://127.0.0.1:8010"),
        local_enabled=False,
    )
    model.local_enabled, model.observing = False, True
    model.tools = [
        t
        for t in model.tools
        if isinstance(t.get("function"), dict)
        and isinstance(function := t.get("function"), dict)
        and function.get("name") == "rag_search"
    ]
    item.cout_eur = 0.05
    history: list[Message] = []
    for turn in context.history:
        history.extend(
            [
                {"role": "user", "content": turn.question},
                {"role": "assistant", "content": turn.answer},
            ]
        )
    system = (
        Path("prompts/project.txt").read_text()
        + "\n"
        + json.dumps(
            {
                "project_instructions": context.instructions,
                "memory": [f.model_dump() for f in context.facts],
            },
            ensure_ascii=False,
        )
    )
    try:
        result = await run(
            Query(question=question, lang=request.lang),
            model,
            ProjectTools(item, str(project)),
            system,
            Limits(wall_clock=max(0, 120 - (time.monotonic() - started))),
            history=history,
        )
        item.state, item.cout_eur = result.state, float(result.cost)
        if result.reason:
            item.erreurs.append(result.reason)
        if result.state != "done":
            return
        answer, facts = consolidated(result.text, question)
        retrieved = {str(p["chunk_id"]): p for p in item.chunks_recuperes}
        keys = list(dict.fromkeys(re.findall(r"\b[a-f0-9]{64}\b", answer)))
        if not set(keys) <= retrieved.keys():
            raise ValueError("invalid_citation")
        # Sources are validated against this request's scoped retrieval results.
        for key in keys:
            item.citations.append(Source.model_validate(retrieved[key]).model_dump())
            answer = answer.replace(key, f"[Source](/projects/{project}/sources/{key})")
        if context.facts:
            answer = (
                "Mémoire du projet :\n"
                + "\n".join("- " + f.text for f in context.facts)
                + "\n\n"
                + answer
            )
        await GatewayModel.post(
            base + "/turns",
            {
                "conversation_id": request.conversation_id,
                "question": question,
                "answer": answer,
                "facts": facts,
                "revision": context.revision,
            },
            max(0.001, 120 - (time.monotonic() - started)),
        )
        item.reponse = answer
    finally:
        item.tokens = {"in": model.input_tokens, "out": model.output_tokens}
        item.latence_ms["generation"] = model.generation_ms
        if model.observations:
            item.modele_utilise = model.observations[-1].provider
            item.route_decision = model.observations[0].route
