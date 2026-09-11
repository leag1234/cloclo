"""Image generation is routed through the gateway, including SSE chats."""

import json
from pathlib import Path
import os
import time
from packages.images import ImageURL
from packages.language import question_language
from services.orchestrator.interactions import Interaction
from services.orchestrator.model import GatewayModel
from services.orchestrator.stream_client import sink_context


async def process_image(prompt: str, item: Interaction) -> None:
    started = time.monotonic()
    item.task_type, item.modele_utilise, item.route_decision = (
        "imagegen",
        "local",
        "simple",
    )
    item.cout_eur = 0.05
    try:
        response = await GatewayModel.post(
            os.environ.get("ATLAS_GATEWAY_URL", "http://127.0.0.1:8010")
            + "/images/generate",
            {"prompt": prompt},
            95,
        )
        image = ImageURL.model_validate({"url": response["image"]})
        cost = float(str(response["cost_eur"]))
        if not 0 <= cost <= 0.05:
            raise ValueError("invalid_provider_cost")
        labels = json.loads(Path("prompts/image-labels.json").read_text())
        label = labels.get(question_language(prompt), labels["en"])
        item.reponse = f"![{label}]({image.url})"
        item.cout_eur, item.state = cost, "done"
        sink = sink_context.get()
        if sink is not None:
            await sink({"delta": {"content": item.reponse}})
    finally:
        item.latence_ms["generation"] = (time.monotonic() - started) * 1000
