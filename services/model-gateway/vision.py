"""M12 sovereign vision with a conservative reservation before any paid call."""

import asyncio
import json
import os
from decimal import Decimal
from pathlib import Path
from time import monotonic
from typing import Literal
from packages.language import conversation_language, language_instruction

import aiohttp
import yaml
from pydantic import Field

from agent_provider import Completion
from packages.images import VisionInput


class VisionRequest(VisionInput):
    lang: Literal["fr", "de", "es", "it", "en"] = "fr"
    timeout: float = Field(gt=0, le=120, default=120)


class VisionProvider:
    def __init__(self) -> None:
        self.config = yaml.safe_load(
            Path(__file__).with_name("vision.yaml").read_text()
        )
        self.input_price = Decimal(str(self.config["input_eur_per_mtok"]))
        self.output_price = Decimal(str(self.config["output_eur_per_mtok"]))
        if any(
            not p.is_finite() or p < 0 for p in (self.input_price, self.output_price)
        ):
            raise ValueError("missing_price")

    def cost(self, incoming: int, outgoing: int) -> Decimal:
        return (incoming * self.input_price + outgoing * self.output_price) / 1000000

    def reserve(self, request: VisionRequest) -> tuple[int, Decimal]:
        images = [im for m in request.messages for im in m.images]
        if not images:
            raise ValueError("image_required")
        # One token per UTF-8 byte bounds text; include message framing and image
        # row/end markers. Native 16x16 patches bound any provider downscaling.
        tokens = 1024 + sum(len(m.text.encode()) + 64 for m in request.messages)
        tokens += sum(
            ((int(im["width"]) + 15) // 16 + 1) * ((int(im["height"]) + 15) // 16) + 1
            for im in images
        )
        if tokens + self.config["max_tokens"] > self.config["context_tokens"]:
            raise ValueError("context_exceeded")
        reservation = self.cost(tokens, self.config["max_tokens"])
        if reservation > Decimal("0.05"):
            raise RuntimeError("cost_budget")
        return tokens, reservation

    async def complete(self, payload: object) -> dict[str, object]:
        started = monotonic()
        request = VisionRequest.model_validate(payload)
        incoming, reserved = self.reserve(request)
        prompt = Path("prompts/vision.txt").read_text()
        prompt += Path("prompts/chat.txt").read_text()
        prompt += language_instruction(
            conversation_language(request.messages, request.lang)
        )
        # Count the versioned system instruction before transport as well.
        incoming += len(prompt.encode()) + 64
        reserved = self.cost(incoming, self.config["max_tokens"])
        if incoming + self.config["max_tokens"] > self.config["context_tokens"]:
            raise ValueError("context_exceeded")
        if reserved > Decimal("0.05"):
            raise RuntimeError("cost_budget")
        messages = [{"role": "system", "content": prompt}]
        messages.extend(m.model_dump() for m in request.messages)
        body = {
            "model": self.config["model"],
            "messages": messages,
            "max_tokens": self.config["max_tokens"],
            "temperature": 0,
        }
        remaining = request.timeout - (monotonic() - started)
        if remaining <= 0:
            raise TimeoutError("timeout")
        async with asyncio.timeout(remaining):
            data = await self.post(body, remaining)
        result = Completion.model_validate(data)
        choice, usage = result.choices[0], result.usage
        if (
            choice.finish_reason != "stop"
            or not choice.message.content
            or choice.message.tool_calls
            or usage.prompt_tokens > incoming
        ):
            raise RuntimeError("provider_response_invalid")
        cost = self.cost(usage.prompt_tokens, usage.completion_tokens)
        if cost > reserved:
            raise RuntimeError("provider_response_invalid")
        return {
            "text": choice.message.content,
            "usage": usage.model_dump(),
            "cost_eur": str(cost),
            "reserved_eur": str(reserved),
            "observation": {"provider": "escalade", "route": "complexe"},
        }

    async def post(self, body: dict[str, object], timeout: float) -> object:
        endpoint = os.environ["SCW_GENERATIVE_BASE_URL"].rstrip("/")
        if not endpoint.startswith("https://"):
            raise ValueError("provider_configuration")
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=timeout), trust_env=False
            ) as client:
                async with client.post(
                    endpoint + "/chat/completions",
                    json=body,
                    headers={
                        "Authorization": "Bearer "
                        + os.environ["SCW_GENERATIVE_API_KEY"]
                    },
                    allow_redirects=False,
                ) as response:
                    if response.status != 200:
                        raise RuntimeError("provider_error")
                    data = bytearray()
                    async for piece in response.content.iter_chunked(16384):
                        data.extend(piece)
                        if len(data) > 800000:
                            raise RuntimeError("provider_response_limit")
            return json.loads(data)
        except (aiohttp.ClientError, ValueError):
            raise RuntimeError("provider_error") from None
