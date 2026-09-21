"""M13 bounded transport to the configured GPU address only."""

from packages.limits import LimitError, ProviderLimitError

import ipaddress
import json
import os
from decimal import Decimal
from time import monotonic
from pathlib import Path
from typing import Literal
from pydantic import Field

import aiohttp
from packages.imagegen import ImagePrompt
from packages.images import image_info
from image_prompt import reservation, rewrite


class ImageRequest(ImagePrompt):
    max_cost_eur: Decimal = Field(
        default=Decimal("0.05"),
        gt=0,
        le=Decimal("0.05"),
        strict=False,
        allow_inf_nan=False,
    )
    timeout: float = Field(default=115, gt=0, le=120)
    lang: Literal["fr", "de", "es", "it", "en"] = "fr"


async def generate(request: object) -> dict[str, object]:
    prompt = ImageRequest.model_validate(request)
    configured_ip = (
        os.environ.get("ATLAS_IMAGE_GPU_IP")
        or Path("BRAIN/gpu_ip.txt").read_text().strip()
    )
    configured_rate = os.environ.get("ATLAS_IMAGE_GPU_EUR_H") or str(
        json.loads(Path("BRAIN/gpu-cost.json").read_text())["hourly_eur"]
    )
    address = str(ipaddress.IPv4Address(configured_ip))
    rate = Decimal(configured_rate)
    if not rate.is_finite():
        raise RuntimeError("cost_budget: expected a finite hourly rate")
    if not 0 < rate <= 2:
        raise ProviderLimitError(
            "cost_budget", int(rate * 1000000), 2000000, "microEUR/hour"
        )
    started = monotonic()
    reserved = reservation(prompt.prompt, prompt.lang)
    available = prompt.max_cost_eur - reserved
    if available <= 0:
        raise ProviderLimitError(
            "cost_budget",
            int(reserved * 1000000),
            int(prompt.max_cost_eur * 1000000),
            "microEUR",
        )
    rewritten = await rewrite(
        prompt.prompt,
        min(30, prompt.timeout, float(available * 3600 / rate)),
        prompt.lang,
    )
    timeout = min(
        prompt.timeout - (monotonic() - started), float(available * 3600 / rate)
    )
    if timeout <= 0:
        raise ProviderLimitError(
            "image_deadline",
            int((monotonic() - started) * 1000),
            int(prompt.timeout * 1000),
            "milliseconds",
        )
    gpu_started = monotonic()
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=timeout), trust_env=False
    ) as client:
        async with client.post(
            f"http://{address}:8000/generate",
            json={"prompt": rewritten, "seed": prompt.seed},
            allow_redirects=False,
        ) as response:
            if response.status == 413:
                limits = json.loads(await response.content.read(512))
                if (
                    isinstance(limits, dict)
                    and all(
                        type(limits.get(k)) is int and limits[k] >= 0
                        for k in ("measured", "limit")
                    )
                    and limits.get("unit") in {"bytes", "characters", "tokens"}
                ):
                    raise LimitError(
                        "image_input_limit",
                        limits["measured"],
                        limits["limit"],
                        limits["unit"],
                    )
            if response.status != 200:
                raise RuntimeError("image_provider_error")
            body = bytearray()
            async for chunk in response.content.iter_chunked(65536):
                body.extend(chunk)
                if len(body) > 2800000:
                    raise ProviderLimitError(
                        "image_response_limit", len(body), 2800000, "bytes"
                    )
    data = json.loads(body)
    if not isinstance(data, dict) or not isinstance(data.get("image"), str):
        raise ValueError("invalid_provider_image")
    metadata = image_info(data["image"])
    if (metadata["format"], metadata["width"], metadata["height"]) != (
        "PNG",
        1024,
        1024,
    ):
        raise ValueError("invalid_provider_image")
    seed = data.get("seed")
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("invalid_provider_seed")
    return {
        "model": json.loads(Path(__file__).with_name("image-model.json").read_text())[
            "repository"
        ],
        "seed": seed,
        "prompt": prompt.prompt,
        "rewritten_prompt": rewritten,
        "width": 1024,
        "height": 1024,
        "max_sequence_length": 512,
        "steps": data["steps"],
        "image": data["image"],
        "cost_eur": float(
            reserved + rate * Decimal(str(monotonic() - gpu_started)) / 3600
        ),
    }


async def complete(request: object) -> dict[str, object]:
    try:
        return await generate(request)
    except TimeoutError:
        raise
    except (aiohttp.ClientError, KeyError, TypeError, OSError) as exc:
        raise RuntimeError("image_provider_unavailable") from exc
