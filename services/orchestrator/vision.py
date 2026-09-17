"""Vision branch materializes owned image references only for the current request."""

import os
import json
import re
from pathlib import Path
import time
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field
from packages.images import ImagePart
from services.orchestrator.chat_schema import ChatRequest
from services.orchestrator.interactions import Interaction
from services.orchestrator.model import GatewayModel
from services.orchestrator.stream_client import sink_context


class VisionUsage(BaseModel):
    prompt_tokens: int = Field(ge=0, strict=True)
    completion_tokens: int = Field(ge=0, le=19000, strict=True)


class VisionObservation(BaseModel):
    provider: Literal["escalade"]
    route: Literal["complexe"]


class VisionReply(BaseModel):
    provider_model: str = Field(default="", max_length=200)
    text: str = Field(min_length=1, max_length=128000)
    usage: VisionUsage
    cost_eur: Decimal = Field(ge=0, le=Decimal("0.20"), allow_inf_nan=False)
    observation: VisionObservation
    reasoning: str = Field(default="", max_length=256000)
    trace_tokens: int = Field(default=0, ge=0)
    answer_tokens: int = Field(default=0, ge=0)
    token_split_estimated: bool = False
    reasoning_retried: bool = False


async def process_vision(request: ChatRequest, item: Interaction) -> None:
    text = request.messages[-1].text
    editing = re.search(
        r"(?i)\b(edit\w*|modifi\w*|retouch\w*|bearbeit\w*|modificar|int[éeè]gr\w*|integr\w*|fusion\w*|combin\w*)\b"
        r"|\b(?:mets?|mettre|put|bring)\b.{0,60}\b(?:ensemble|together)\b"
        r"|\b(?:fais|faire|crée|cree|create|make)\b.{0,60}\b(?:montage|collage)\b",
        text,
    )
    analyzing = re.search(
        r"(?i)^\s*(?:please\s+)?(?:analyse|analyze|describe|décris|decris|compare|beschreib\w*|analysier\w*|vergleiche|analiza|compara|descrivi|analizza|confronta)\b",
        text,
    )
    if editing and not analyzing:
        labels = json.loads(Path("prompts/image-edit.json").read_text())
        language = request.lang
        item.reponse, item.state, item.task_type = labels[language], "done", "vision"
        sink = sink_context.get()
        if sink:
            await sink({"delta": {"content": item.reponse}})
        return
    started = time.monotonic()
    item.reasoning_effort = request.reasoning_effort
    item.cout_eur = 0.1  # Retain reservation on missing/invalid provider usage.
    item.task_type = "vision"
    item.images = [im for message in request.messages for im in message.images]
    item.modele_utilise, item.route_decision = "escalade", "complexe"
    try:
        result = VisionReply.model_validate(
            await GatewayModel.post(
                os.environ.get("ATLAS_GATEWAY_URL", "http://127.0.0.1:8010").rstrip("/")
                + "/vision/complete",
                {
                    "messages": [m.model_dump() for m in request.messages],
                    "timeout": request.timeout_seconds - 5.0,
                    "lang": request.lang,
                    "profile": request.model,
                    "max_tokens": request.max_tokens,
                },
                request.timeout_seconds - 5.0,
            )
        )
        if result.cost_eur > Decimal("0.10"):
            raise ValueError("invalid_vision_cost")
        item.provider_model = result.provider_model
        item.reasoning = result.reasoning
        item.trace_tokens, item.answer_tokens = (
            result.trace_tokens,
            result.answer_tokens,
        )
        item.token_split_estimated = result.token_split_estimated
        item.reasoning_retried = result.reasoning_retried
        text = result.text
        for message in request.messages:
            if isinstance(message.content, list):
                for part in message.content:
                    if isinstance(part, ImagePart):
                        url = part.image_url.url
                        text = text.replace(url, "[IMAGE]").replace(
                            url.split(",", 1)[1], "[IMAGE]"
                        )
        sink = sink_context.get()
        if sink is not None:
            if result.reasoning:
                await sink({"delta": {"reasoning_content": result.reasoning}})
            if result.reasoning_retried:
                await sink({"phase": "reasoning_fallback"})
            await sink({"delta": {"content": text}})
        item.reponse, item.state = text, "done"
        item.tokens = {
            "in": result.usage.prompt_tokens,
            "out": result.usage.completion_tokens,
        }
        item.cout_eur = float(result.cost_eur)
    finally:
        item.latence_ms["generation"] = (time.monotonic() - started) * 1000
