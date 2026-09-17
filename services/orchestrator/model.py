"""Model-independent client; provider selection and prices belong to the gateway."""

from packages.profiles import PROFILES

import json
from packages.tool_history import final_messages
import re
from decimal import Decimal
from pathlib import Path
from time import monotonic
from typing import Literal

import aiohttp
from pydantic import BaseModel, ConfigDict, Field

from services.orchestrator.loop import Call, Message, Reservation, Turn
from services.orchestrator.tools import declarations
from services.orchestrator.stream_client import Sink, receive
from services.orchestrator.narration import NarrationFilter, clean_answer


class Configuration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input_eur_per_mtok: Decimal = Field(ge=0, allow_inf_nan=False)
    output_eur_per_mtok: Decimal = Field(ge=0, allow_inf_nan=False)
    max_tokens: int = Field(gt=0, le=2048)
    gateway_reserves_quality: bool = False


class WireCall(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=80)
    arguments: str = Field(max_length=16000)


class WireUsage(BaseModel):
    prompt_tokens: int = Field(ge=0, strict=True)
    completion_tokens: int = Field(ge=0, le=19000, strict=True)


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    provider: Literal["local", "escalade"]
    route: Literal["simple", "complexe"]
    task_type: Literal["text", "code", "vision"] | None = None
    fallback: bool = False


class WireTurn(BaseModel):
    provider_model: str = Field(default="", max_length=200)
    observation: Observation | None = None
    usage: WireUsage
    model_config = ConfigDict(extra="forbid", strict=True)
    cost_eur: Decimal | None = Field(
        default=None, ge=0, le=Decimal("0.20"), allow_inf_nan=False, strict=False
    )
    reasoning: str = Field(default="", max_length=256000)
    trace_tokens: int = Field(default=0, ge=0)
    answer_tokens: int = Field(default=0, ge=0)
    token_split_estimated: bool = False
    reasoning_retried: bool = False
    text: str = Field(max_length=128000)
    calls: list[WireCall] = Field(max_length=10)


class GatewayError(RuntimeError):
    def __init__(self, code: str, status: int, detail: str = "") -> None:
        self.code, self.status, self.detail = code, status, detail
        super().__init__(code)


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
        self.sink: Sink | None = None
        self.reasoning_effort = "none"
        self.stream_turn = 0
        self.profile: str | None = None
        self.max_tokens = configuration.max_tokens
        self.provider_model = ""
        self.spent = Decimal(0)
        self.reasoning = ""
        self.trace_tokens = 0
        self.answer_tokens = 0
        self.token_split_estimated = False
        self.reasoning_retried = False

    def configure_quality(self, profile: str, max_tokens: int) -> None:
        if profile not in PROFILES:
            raise ValueError("invalid_profile")
        self.profile, self.max_tokens = profile, max_tokens
        self.reasoning_effort = "none"

    @property
    def allowance(self) -> Decimal:
        return max(
            Decimal(0),
            Decimal("0.10" if self.profile is not None else "0.05") - self.spent,
        )

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
                        if url.endswith(
                            ("/vision/complete", "/images/generate", "/images/start")
                        ):
                            error = json.loads(await response.content.read(512))
                            codes = {
                                "cost_budget": 504,
                                "configuration_missing": 503,
                                "timeout": 504,
                                "context_exceeded": 413,
                                "invalid_input": 400,
                                "provider_error": 502,
                            }
                            code = (
                                error.get("code") if isinstance(error, dict) else None
                            )
                            if code in codes:
                                detail = ""
                                if code == "context_exceeded" and all(
                                    type(error.get(k)) is int
                                    for k in ("tokens", "limit")
                                ):
                                    detail = f"context_exceeded: {error['tokens']} tokens, limit {error['limit']} tokens"
                                if code == "timeout" and all(
                                    type(error.get(k)) in (int, float)
                                    and 0 <= error[k] <= 1000000
                                    for k in ("elapsed_seconds", "limit_seconds")
                                ):
                                    detail = f"Timeout: {error['elapsed_seconds']:.3f} seconds elapsed, limit {error['limit_seconds']:.3f} seconds"
                                if code == "configuration_missing":
                                    missing = error.get("missing")
                                    if isinstance(missing, list) and all(
                                        isinstance(name, str)
                                        and re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", name)
                                        for name in missing
                                    ):
                                        detail = (
                                            "Missing required environment variables: "
                                            + ", ".join(missing)
                                        )
                                raise GatewayError(code, codes[code], detail)
                        raise RuntimeError("gateway_error")
                    maximum = 2800000 if url.endswith("/images/generate") else 800000
                    data = bytearray()
                    async for piece in response.content.iter_chunked(16384):
                        data.extend(piece)
                        if len(data) > maximum:
                            raise ValueError("gateway_response_limit")
            value: object = json.loads(data)
            if not isinstance(value, dict):
                raise ValueError("gateway_response_invalid")
            return value
        except aiohttp.ClientError:
            raise RuntimeError("gateway_unavailable") from None

    @classmethod
    async def connect(cls, url: str, local_enabled: bool = True) -> "GatewayModel":
        config = await cls.post(
            url.rstrip("/") + "/agent/config", {"local_enabled": local_enabled}, 5
        )
        return cls(url, Configuration.model_validate(config))

    def observe(self, messages: list[Message], prompt_tokens: int) -> None:
        self.prefix = json.loads(json.dumps(messages))
        self.prompt_tokens = prompt_tokens

    def estimate(self, messages: list[Message]) -> Reservation:
        incoming = (
            max(
                len(
                    json.dumps(
                        {
                            "messages": value,
                            "tools": self.available_tools(messages)
                            if self.profile
                            else self.tools,
                        },
                        ensure_ascii=False,
                    ).encode()
                )
                for value in (messages, final_messages(messages))
                if self.profile or value == messages
            )
            + 256
        )
        # Profile recovery retains the full input bound on unknown usage. A
        # previously measured prefix cannot shrink that possible reservation.
        if (
            not self.profile
            and self.prefix
            and messages[: len(self.prefix)] == self.prefix
        ):
            incoming = (
                self.prompt_tokens
                + len(
                    json.dumps(
                        messages[len(self.prefix) :], ensure_ascii=False
                    ).encode()
                )
                + 256
            )
        if self.profile:
            # Hold the remaining allowance; the gateway reserves each actual attempt.
            primary_cost = (
                incoming * self.configuration.input_eur_per_mtok
                + self.max_tokens * self.configuration.output_eur_per_mtok
            ) / 1_000_000
            return Reservation(
                incoming * 2 + self.max_tokens + 3000,
                self.allowance
                if self.configuration.gateway_reserves_quality
                else max(primary_cost, self.allowance),
            )
        outgoing = self.configuration.max_tokens
        cost = (
            incoming * self.configuration.input_eur_per_mtok
            + outgoing * self.configuration.output_eur_per_mtok
        ) / 1_000_000
        return Reservation(incoming + outgoing, cost)

    def available_tools(self, messages: list[Message]) -> list[dict[str, object]]:
        if any(
            message.get("role") == "tool"
            and isinstance(message.get("content"), str)
            and '"error": "tool_quota_exhausted"' in str(message["content"])
            for message in messages
        ):
            return []
        completed = {m.get("tool_call_id") for m in messages if m.get("role") == "tool"}
        counts: dict[str, int] = {}
        for message in messages:
            calls = message.get("tool_calls")
            if not isinstance(calls, list):
                continue
            for call in calls:
                if not isinstance(call, dict) or call.get("id") not in completed:
                    continue
                function = call.get("function")
                if isinstance(function, dict) and isinstance(function.get("name"), str):
                    name = function["name"]
                    counts[name] = counts.get(name, 0) + 1
        if sum(counts.values()) >= 10:
            return []
        ceilings = {"web_search": 3, "web_fetch": 8}
        available = []
        for tool in self.tools:
            function = tool.get("function")
            if isinstance(function, dict):
                name = str(function.get("name"))
                if counts.get(name, 0) < ceilings.get(name, 10):
                    remaining = min(
                        10 - sum(counts.values()),
                        ceilings.get(name, 10) - counts.get(name, 0),
                    )
                    available.append(
                        {
                            **tool,
                            "function": {
                                **function,
                                "description": str(function.get("description", ""))
                                + Path("prompts/tool-quota.txt")
                                .read_text()
                                .format(remaining=remaining),
                            },
                        }
                    )
        return available

    async def complete(self, messages: list[Message], timeout: float) -> Turn:
        payload: Message = {
            "messages": messages,
            "tools": self.available_tools(messages),
            "timeout": timeout,
        }
        if self.profile:
            payload.update(
                profile=self.profile,
                max_tokens=self.max_tokens,
                reasoning_effort=self.reasoning_effort,
                budget_eur=str(self.allowance),
            )
        if self.observing:
            payload.update(local_enabled=self.local_enabled, observe=True)
        reserved = self.estimate(messages)
        started = monotonic()
        try:
            if self.sink is None:
                wire = await self.post(self.url + "/agent/complete", payload, timeout)
            else:
                payload["reasoning_effort"] = self.reasoning_effort
                self.stream_turn += 1
                await self.sink(
                    {
                        "turn": self.stream_turn,
                        "phase": "generating",
                        "reserved_eur": str(self.estimate(messages).cost),
                        "max_output_tokens": self.max_tokens,
                    }
                )
                parser = NarrationFilter()
                sink = self.sink

                async def filtered(event: dict[str, object]) -> None:
                    delta = event.get("delta")
                    if isinstance(delta, dict) and isinstance(
                        delta.get("content"), str
                    ):
                        count = len(parser.removed)
                        text = parser.feed(delta["content"])
                        if len(parser.removed) > count:
                            await sink(
                                {"phase": "narration", "sentences": len(parser.removed)}
                            )
                        if text:
                            await sink({"delta": {**delta, "content": text}})
                    else:
                        await sink(event)

                wire = await receive(
                    self.url + "/agent/stream", payload, timeout, filtered
                )
                tail = parser.finish()
                if tail:
                    await sink({"delta": {"content": tail}})
            result = WireTurn.model_validate(wire)
            if result.text:
                result.text = clean_answer(result.text, allow_empty=bool(result.calls))
            if (
                not self.profile
                and result.usage.completion_tokens > self.configuration.max_tokens
            ):
                raise ValueError("output_budget")
            if self.profile and result.usage.completion_tokens > self.max_tokens + 3000:
                raise ValueError("output_budget")
            if self.sink is not None:
                await self.sink(
                    {
                        "turn": self.stream_turn,
                        "phase": "intermediate" if result.calls else "final",
                        "tools": [c.name for c in result.calls],
                    }
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
        if self.profile:
            if result.cost_eur is None or result.cost_eur > reserved.cost:
                raise ValueError("invalid_profile_cost")
            self.provider_model = result.provider_model
            cost = result.cost_eur
            self.spent += cost
            self.reasoning += result.reasoning
            self.trace_tokens += result.trace_tokens
            self.answer_tokens += result.answer_tokens
            self.token_split_estimated |= result.token_split_estimated
            self.reasoning_retried |= result.reasoning_retried
            if result.reasoning_retried:
                # Recovery can request tools; its following turn must finish
                # without restarting the reasoning that already failed.
                self.reasoning_effort = "none"
                self.max_tokens = 3000
        if (
            not self.profile
            and result.observation is not None
            and result.observation.fallback
        ):
            # The primary may have been billed without returning usage. Retain the full reservation.
            cost = reserved.cost
        return Turn(
            result.text,
            tuple(Call(c.id, c.name, c.arguments) for c in result.calls),
            Reservation(usage.prompt_tokens + usage.completion_tokens, cost),
        )
