"""M13 bounded transport to the configured GPU address only."""

import ipaddress
import json
import os
from decimal import Decimal
from time import monotonic
from pathlib import Path

import aiohttp
from packages.imagegen import ImagePrompt
from packages.images import image_info


async def generate(request: object) -> dict[str, object]:
    prompt = ImagePrompt.model_validate(request)
    configured_ip = (
        os.environ.get("ATLAS_IMAGE_GPU_IP")
        or Path("BRAIN/gpu_ip.txt").read_text().strip()
    )
    configured_rate = os.environ.get("ATLAS_IMAGE_GPU_EUR_H") or str(
        json.loads(Path("BRAIN/gpu-cost.json").read_text())["hourly_eur"]
    )
    address = str(ipaddress.IPv4Address(configured_ip))
    rate = Decimal(configured_rate)
    if not rate.is_finite() or not 0 < rate <= 2 or rate * 90 / 3600 > Decimal("0.05"):
        raise RuntimeError("cost_budget")
    started = monotonic()
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=90), trust_env=False
    ) as client:
        async with client.post(
            f"http://{address}:8000/generate",
            json=prompt.model_dump(),
            allow_redirects=False,
        ) as response:
            if response.status != 200:
                raise RuntimeError("image_provider_error")
            body = bytearray()
            async for chunk in response.content.iter_chunked(65536):
                body.extend(chunk)
                if len(body) > 2800000:
                    raise RuntimeError("image_response_limit")
    data = json.loads(body)
    if not isinstance(data, dict) or not isinstance(data.get("image"), str):
        raise ValueError("invalid_provider_image")
    metadata = image_info(data["image"])
    if (metadata["format"], metadata["width"], metadata["height"]) != ("PNG", 512, 512):
        raise ValueError("invalid_provider_image")
    return {
        "image": data["image"],
        "cost_eur": float(rate * Decimal(str(monotonic() - started)) / 3600),
    }


async def complete(request: object) -> dict[str, object]:
    try:
        return await generate(request)
    except TimeoutError:
        raise
    except (aiohttp.ClientError, KeyError, TypeError, OSError) as exc:
        raise RuntimeError("image_provider_unavailable") from exc
