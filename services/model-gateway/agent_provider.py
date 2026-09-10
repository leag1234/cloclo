"""Validated tool-calling transport and human-confirmed pricing, POC-P6."""

import asyncio
import json
import logging
import re
from time import monotonic
import os
from decimal import Decimal
from pathlib import Path
from typing import Literal

import aiohttp
import yaml
from pydantic import BaseModel, ConfigDict, Field


def classify(messages: list[dict[str, object]]) -> str:
    # Conservative allowlist: only short, familiar transformations use S.
    simple = r"(?i)\b(tradui\w*|translate|reformul\w*|formuliere|rewrite|corrig\w*|summary|résumer|abkürzung|bedeutet|significa|capital|come si dice|che ore|auguri|asunto|ideen)\b"
    complex_task = r"(?i)\b(analys\w*|anális\w*|analyz\w*|ris\w*|risk\w*|strat\w*|proof|prove|beweis\w*|dimostr\w*|design\w*|progett\w*|refactor\w*|algorithm\w*|algoritm\w*)\b"
    users = [m.get("content") for m in messages if m.get("role") == "user"]
    if not users or any(m.get("role") == "tool" for m in messages):
        return "reasoning"
    if all(
        isinstance(t, str)
        and 0 < len(t.strip()) <= 240
        and re.search(simple, t)
        and not re.search(complex_task, t)
        for t in users
    ):
        return "chat_simple"
    return "reasoning"


class Function(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    arguments: str = Field(max_length=16000)


class ToolCall(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    type: Literal["function"]
    function: Function


class Reply(BaseModel):
    content: str | None = Field(default=None, max_length=32000)
    tool_calls: list[ToolCall] = Field(default_factory=list, max_length=10)


class Choice(BaseModel):
    finish_reason: Literal["stop", "tool_calls"]
    message: Reply


class Usage(BaseModel):
    prompt_tokens: int = Field(ge=0, strict=True)
    completion_tokens: int = Field(ge=0, le=2048, strict=True)


class Completion(BaseModel):
    usage: Usage
    choices: list[Choice] = Field(min_length=1, max_length=1)


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    messages: list[dict[str, object]] = Field(min_length=1, max_length=100)
    tools: list[dict[str, object]] = Field(min_length=1, max_length=4)
    timeout: float = Field(gt=0, le=120)
    local_enabled: bool = True
    observe: bool = False


class AgentProvider:
    def __init__(self) -> None:
        self.model = os.environ["ESCALATION_MODEL"]
        routing = yaml.safe_load(Path(__file__).with_name("routing.yaml").read_text())
        self.local_endpoint = os.path.expandvars(
            routing["providers"]["local"]["base_url"]
        ).rstrip("/")
        self.local_model = os.path.expandvars(
            routing["task_classes"]["chat_simple"]["primary"]["model"]
        )
        catalogue = yaml.safe_load(Path(__file__).with_name("pricing.yaml").read_text())
        if self.model not in catalogue["models"]:
            raise ValueError("missing_price")
        self.price = catalogue["models"][self.model]
        for key in ("input_eur_per_mtok", "output_eur_per_mtok"):
            value = Decimal(str(self.price[key]))
            if not value.is_finite() or value < 0:
                raise ValueError("invalid_price")

    def configuration(self) -> dict[str, object]:
        return {
            key: str(self.price[key])
            for key in ("input_eur_per_mtok", "output_eur_per_mtok")
        } | {"max_tokens": 2048}

    async def complete(self, payload: object) -> dict[str, object]:
        request = AgentRequest.model_validate(payload)
        endpoint = os.environ["SCW_GENERATIVE_BASE_URL"].rstrip("/")
        if not endpoint.startswith("https://"):
            raise ValueError("provider_configuration")
        started = monotonic()
        route = classify(request.messages)
        fallback = False

        def observed(answer: dict[str, object], provider: str) -> dict[str, object]:
            if request.observe:
                return {
                    **answer,
                    "observation": {
                        "provider": provider,
                        "route": "simple" if route == "chat_simple" else "complexe",
                    },
                }
            return answer

        if route == "chat_simple" and request.local_enabled:
            try:
                if "$" in self.local_model or "$" in self.local_endpoint:
                    raise RuntimeError("local_unconfigured")
                async with asyncio.timeout(min(2.0, request.timeout * 0.2)):
                    answer = await self._complete(
                        request,
                        self.local_endpoint,
                        self.local_model,
                        "",
                        min(2.0, request.timeout * 0.2),
                    )
                logging.getLogger(__name__).info(
                    json.dumps(
                        {
                            "event": "routing",
                            "route": route,
                            "provider": "local",
                            "fallback": False,
                        }
                    )
                )
                return observed(answer, "local")
            except (RuntimeError, TimeoutError):
                fallback = True
        remaining = request.timeout - (monotonic() - started)
        if remaining <= 0:
            raise TimeoutError("timeout")
        logging.getLogger(__name__).info(
            json.dumps(
                {
                    "event": "routing",
                    "route": route,
                    "provider": "scaleway",
                    "fallback": fallback,
                }
            )
        )
        async with asyncio.timeout(remaining):
            answer = await self._complete(
                request,
                endpoint,
                self.model,
                os.environ["SCW_GENERATIVE_API_KEY"],
                remaining,
            )
            return observed(answer, "escalade")

    async def _complete(
        self, request: AgentRequest, endpoint: str, model: str, key: str, timeout: float
    ) -> dict[str, object]:
        body = {
            "model": model,
            "messages": request.messages,
            "tools": request.tools,
            "tool_choice": "auto",
            "max_tokens": 2048,
            "temperature": 0,
            "reasoning_effort": "none",
        }
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=timeout), trust_env=False
            ) as session:
                async with session.post(
                    endpoint + "/chat/completions",
                    json=body,
                    headers={"Authorization": "Bearer " + key} if key else {},
                    allow_redirects=False,
                ) as response:
                    if response.status != 200:
                        raise RuntimeError("provider_error")
                    data = bytearray()
                    async for piece in response.content.iter_chunked(16384):
                        data.extend(piece)
                        if len(data) > 800000:
                            raise RuntimeError("provider_response_limit")
            completion = Completion.model_validate(json.loads(data))
            reply = completion.choices[0].message
            if not reply.content and not reply.tool_calls:
                raise RuntimeError("provider_response_invalid")
            ids = [call.id for call in reply.tool_calls]
            if len(ids) != len(set(ids)):
                raise RuntimeError("provider_response_invalid")
            return {
                "text": reply.content or "",
                "usage": completion.usage.model_dump(),
                "calls": [
                    {
                        "id": call.id,
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    }
                    for call in reply.tool_calls
                ],
            }
        except (aiohttp.ClientError, ValueError):
            raise RuntimeError("provider_error") from None
