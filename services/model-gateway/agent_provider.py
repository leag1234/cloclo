"""Validated tool-calling transport and human-confirmed pricing, POC-P6."""

import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Literal

import aiohttp
import yaml
from pydantic import BaseModel, ConfigDict, Field


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


class AgentProvider:
    def __init__(self) -> None:
        self.model = os.environ["ESCALATION_MODEL"]
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
        body = {
            "model": self.model,
            "messages": request.messages,
            "tools": request.tools,
            "tool_choice": "auto",
            "max_tokens": 2048,
            "temperature": 0,
            "reasoning_effort": "none",
        }
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=request.timeout), trust_env=False
            ) as session:
                async with session.post(
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
