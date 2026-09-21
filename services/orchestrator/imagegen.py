"""Image generation is routed through the gateway, including SSE chats."""

import json
from pathlib import Path
import os
import time
from decimal import Decimal
from packages.images import ImageURL
from packages.limits import ProviderLimitError
from services.orchestrator.image_store import store
from services.orchestrator.interactions import Interaction
from services.orchestrator.model import GatewayError, GatewayModel
from services.orchestrator.stream_client import sink_context
from services.orchestrator.deadline import infrastructure_startup


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
    if not budget.is_finite():
        raise RuntimeError("cost_budget: expected a finite monetary amount")
    if not 0 < budget <= Decimal("0.05"):
        raise ProviderLimitError(
            "cost_budget", int(budget * 1000000), 50000, "microEUR"
        )
    if not 0 < timeout <= 120:
        raise ProviderLimitError(
            "deadline", int(timeout * 1000), 120000, "milliseconds"
        )
    try:
        if os.environ.get("ATLAS_IMAGE_ON_DEMAND") == "1":
            # Provision through the gateway; M13 accounts for loading separately.
            gateway = os.environ.get(
                "ATLAS_GATEWAY_URL", "http://127.0.0.1:8010"
            ).rstrip("/")
            health = await GatewayModel.post(
                gateway + "/images/ready", {}, min(3, timeout)
            )
            if health.get("ready") is not True:
                sink = sink_context.get()
                if sink:
                    labels = json.loads(Path("prompts/image-start.json").read_text())
                    await sink({"delta": {"content": labels[language] + "\n\n"}})
                loading = time.monotonic()
                try:
                    async with infrastructure_startup(900):
                        await GatewayModel.post(
                            gateway + "/images/start", {"timeout": 895}, 900
                        )
                finally:
                    item.startup_seconds = time.monotonic() - loading
            timeout -= time.monotonic() - started - item.startup_seconds
            if timeout <= 0:
                raise TimeoutError("image_worker_start_timeout")
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
        item.images[0]["original_request"] = item.question
        item.reponse = f"![{label}]({reference})"
        item.cout_eur, item.state = cost, "done"
        sink = sink_context.get()
        if sink is not None:
            await sink({"delta": {"content": item.reponse}})
    except GatewayError as exc:
        if exc.code == "configuration_missing":
            item.cout_eur = 0.0  # Startup refused before any generation transport.
        raise
    finally:
        item.latence_ms["generation"] = (time.monotonic() - started) * 1000
