"""Image generation is routed through the gateway, including SSE chats."""

import json
from pathlib import Path
import os
import time
from decimal import Decimal
from packages.images import ImageURL
from services.orchestrator.image_store import store
from services.orchestrator.interactions import Interaction
from services.orchestrator.model import GatewayModel
from services.orchestrator.stream_client import sink_context


async def process_image(
    prompt: str,
    item: Interaction,
    seed: int | None = None,
    *,
    language: str,
    budget: Decimal = Decimal("0.05"),
    timeout: float = 118,
) -> None:
    started = time.monotonic()
    item.task_type, item.modele_utilise, item.route_decision = (
        "imagegen",
        "local",
        "simple",
    )
    item.cout_eur = float(budget)
    if not 0 < budget <= Decimal("0.05") or not 0 < timeout <= 120:
        raise RuntimeError("cost_budget")
    try:
        response = await GatewayModel.post(
            os.environ.get("ATLAS_GATEWAY_URL", "http://127.0.0.1:8010")
            + "/images/generate",
            {
                "prompt": prompt,
                "seed": seed,
                "lang": language,
                "max_cost_eur": str(budget),
                "timeout": timeout,
            },
            timeout,
        )
        image = ImageURL.model_validate({"url": response["image"]})
        cost = float(str(response["cost_eur"]))
        if not 0 <= Decimal(str(cost)) <= budget:
            raise ValueError("invalid_provider_cost")
        labels = json.loads(Path("prompts/image-labels.json").read_text())
        label = labels[language]
        reference = store(image.url)
        item.images = [
            {
                k: v
                for k, v in response.items()
                if k != "image" and isinstance(v, (str, int))
            }
        ]
        item.images[0]["reference"] = reference
        item.reponse = f"![{label}]({reference})"
        item.cout_eur, item.state = cost, "done"
        sink = sink_context.get()
        if sink is not None:
            await sink({"delta": {"content": item.reponse}})
    finally:
        item.latence_ms["generation"] = (time.monotonic() - started) * 1000
