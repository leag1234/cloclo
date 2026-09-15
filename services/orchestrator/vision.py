"""Vision branch uses the gateway and never persists uploaded image bytes."""

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
    completion_tokens: int = Field(ge=0, le=2048, strict=True)


class VisionObservation(BaseModel):
    provider: Literal["escalade"]
    route: Literal["complexe"]


class VisionReply(BaseModel):
    text: str = Field(min_length=1, max_length=32000)
    usage: VisionUsage
    cost_eur: Decimal = Field(ge=0, le=Decimal("0.05"), allow_inf_nan=False)
    observation: VisionObservation


async def process_vision(request: ChatRequest, item: Interaction) -> None:
    if re.search(
        r"(?i)\b(edit\w*|modifi\w*|retouch\w*|bearbeit\w*|modificar)\b",
        request.messages[-1].text,
    ):
        labels = json.loads(Path("prompts/image-edit.json").read_text())
        language = request.lang
        item.reponse, item.state, item.task_type = labels[language], "done", "vision"
        sink = sink_context.get()
        if sink:
            await sink({"delta": {"content": item.reponse}})
        return
    started = time.monotonic()
    item.cout_eur = 0.05  # Retain reservation on missing/invalid provider usage.
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
                    "timeout": 115.0,
                    "lang": request.lang,
                },
                115.0,
            )
        )
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
            await sink({"delta": {"content": text}})
        item.reponse, item.state = text, "done"
        item.tokens = {
            "in": result.usage.prompt_tokens,
            "out": result.usage.completion_tokens,
        }
        item.cout_eur = float(result.cost_eur)
    finally:
        item.latence_ms["generation"] = (time.monotonic() - started) * 1000
