"""Model-independent client; provider selection and prices belong to the gateway."""

import json
from decimal import Decimal
from time import monotonic
from typing import Literal

import aiohttp
from pydantic import BaseModel, ConfigDict, Field

from services.orchestrator.loop import Call, Message, Reservation, Turn
from services.orchestrator.tools import declarations


class Configuration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input_eur_per_mtok: Decimal = Field(ge=0, allow_inf_nan=False)
    output_eur_per_mtok: Decimal = Field(ge=0, allow_inf_nan=False)
    max_tokens: int = Field(gt=0, le=2048)


class WireCall(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=80)
    arguments: str = Field(max_length=16000)


class WireUsage(BaseModel):
    prompt_tokens: int = Field(ge=0, strict=True)
    completion_tokens: int = Field(ge=0, le=2048, strict=True)


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    provider: Literal["local", "escalade"]
    route: Literal["simple", "complexe"]


class WireTurn(BaseModel):
    observation: Observation | None = None
    usage: WireUsage
    model_config = ConfigDict(extra="forbid", strict=True)
    text: str = Field(max_length=32000)
    calls: list[WireCall] = Field(max_length=10)


class GatewayModel:
    def __init__(self, url: str, configuration: Configuration) -> None:
        self.url, self.configuration = url.rstrip("/"), configuration
        self.tools = declarations()
        self.prefix: list[Message] = []
        self.prompt_tokens = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.observations: list[Observation] = []
        self.local_enabled = True
        self.observing = False
        self.generation_ms = 0.0

    @staticmethod
    async def post(url: str, payload: Message, timeout: float) -> Message:
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=timeout), trust_env=False
            ) as session:
                async with session.post(
                    url, json=payload, allow_redirects=False
                ) as response:
                    if response.status != 200:
                        raise RuntimeError("gateway_error")
                    data = bytearray()
                    async for piece in response.content.iter_chunked(16384):
                        data.extend(piece)
                        if len(data) > 800000:
                            raise ValueError("gateway_response_limit")
            value: object = json.loads(data)
            if not isinstance(value, dict):
                raise ValueError("gateway_response_invalid")
            return value
        except aiohttp.ClientError:
            raise RuntimeError("gateway_unavailable") from None

    @classmethod
    async def connect(cls, url: str) -> "GatewayModel":
        config = await cls.post(url.rstrip("/") + "/agent/config", {}, 5)
        return cls(url, Configuration.model_validate(config))

    def observe(self, messages: list[Message], prompt_tokens: int) -> None:
        self.prefix = json.loads(json.dumps(messages))
        self.prompt_tokens = prompt_tokens

    def estimate(self, messages: list[Message]) -> Reservation:
        incoming = (
            len(
                json.dumps(
                    {"messages": messages, "tools": self.tools}, ensure_ascii=False
                ).encode()
            )
            + 256
        )
        if self.prefix and messages[: len(self.prefix)] == self.prefix:
            incoming = (
                self.prompt_tokens
                + len(
                    json.dumps(
                        messages[len(self.prefix) :], ensure_ascii=False
                    ).encode()
                )
                + 256
            )
        outgoing = self.configuration.max_tokens
        cost = (
            incoming * self.configuration.input_eur_per_mtok
            + outgoing * self.configuration.output_eur_per_mtok
        ) / 1_000_000
        return Reservation(incoming + outgoing, cost)

    async def complete(self, messages: list[Message], timeout: float) -> Turn:
        payload: Message = {
            "messages": messages,
            "tools": self.tools,
            "timeout": timeout,
        }
        if self.observing:
            payload.update(local_enabled=self.local_enabled, observe=True)
        started = monotonic()
        try:
            result = WireTurn.model_validate(
                await self.post(self.url + "/agent/complete", payload, timeout)
            )
        finally:
            self.generation_ms += (monotonic() - started) * 1000
        if self.observing and result.observation is None:
            raise ValueError("missing_observation")
        if result.observation is not None:
            self.observations.append(result.observation)
        self.input_tokens += result.usage.prompt_tokens
        self.output_tokens += result.usage.completion_tokens
        usage = result.usage
        self.observe(messages, usage.prompt_tokens)
        cost = (
            usage.prompt_tokens * self.configuration.input_eur_per_mtok
            + usage.completion_tokens * self.configuration.output_eur_per_mtok
        ) / 1_000_000
        return Turn(
            result.text,
            tuple(Call(c.id, c.name, c.arguments) for c in result.calls),
            Reservation(usage.prompt_tokens + usage.completion_tokens, cost),
        )
