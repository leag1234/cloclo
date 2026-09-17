"""POC-P6: reserve worst-case usage before starting cancellable I/O."""

from packages.profiles import PROFILES

import asyncio
import json
import logging
import time
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from services.guardrails.input_filter import validate_input


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    question: str = Field(min_length=1, max_length=32000, pattern=r"\S")
    lang: Literal["fr", "de", "es", "it", "en"]

    _safe_question = field_validator("question")(validate_input)


@dataclass(frozen=True)
class Limits:
    tokens: int = 16384
    profile: str | None = None
    tool_calls: int = 10
    wall_clock: float = 120
    cost: Decimal = Decimal("0.05")

    def __post_init__(self) -> None:
        if self.profile is not None and self.profile not in PROFILES:
            raise ValueError("invalid_limits")
        if not (
            0 <= self.tokens <= (262144 if self.profile else 16384)
            and 0 <= self.tool_calls <= 10
            and (0 <= self.wall_clock <= 120)
            and (
                0
                <= self.cost
                <= Decimal("0.10" if self.profile is not None else "0.05")
            )
        ):
            raise ValueError("invalid_limits")


@dataclass(frozen=True)
class Reservation:
    tokens: int
    cost: Decimal

    def __post_init__(self) -> None:
        if self.tokens < 0 or not self.cost.is_finite() or self.cost < 0:
            raise ValueError("invalid_reservation")


@dataclass(frozen=True)
class Call:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class Turn:
    text: str
    calls: tuple[Call, ...] = ()
    usage: Reservation | None = None


@dataclass
class Result:
    text: str = ""
    state: str = "model"
    reason: str = ""
    tokens: int = 0
    cost: Decimal = Decimal(0)
    tool_calls: int = 0
    trace: list[dict[str, object]] = field(default_factory=list)


Message = dict[str, object]


class Model(Protocol):
    def estimate(self, messages: list[Message]) -> Reservation: ...
    async def complete(self, messages: list[Message], timeout: float) -> Turn: ...


class Tools(Protocol):
    def estimate(self, call: Call) -> Reservation: ...
    async def execute(self, call: Call, timeout: float) -> Message: ...


class Stop(Exception):
    pass


async def run(
    query: Query,
    model: Model,
    tools: Tools,
    system: str,
    limits: Limits = Limits(),
    clock: Callable[[], float] = time.monotonic,
    history: list[Message] | None = None,
    retry_web: bool = False,
    terminal_tools: frozenset[str] = frozenset(),
) -> Result:
    result = Result()
    deadline = clock() + limits.wall_clock
    messages: list[Message] = [
        {"role": "system", "content": system},
        *(history or []),
        {
            "role": "user",
            "content": json.dumps(
                {
                    **(
                        {"scope": Path("prompts/current-question.txt").read_text()}
                        if limits.profile
                        else {}
                    ),
                    **query.model_dump(),
                },
                ensure_ascii=False,
            ),
        },
    ]
    counts: Counter[str] = Counter()
    recent: list[tuple[str, str]] = []
    quota_recovered = False

    def remaining() -> float:
        seconds = deadline - clock()
        if seconds <= 0:
            raise Stop("wall_clock")
        return seconds

    def reserve(usage: Reservation) -> None:
        remaining()
        if result.tokens + usage.tokens > limits.tokens:
            raise Stop("tokens")
        if result.cost + usage.cost > limits.cost:
            raise Stop("cost")
        result.tokens += usage.tokens
        result.cost += usage.cost

    async def invoke(operation: Awaitable[Turn] | Awaitable[Message]) -> Turn | Message:
        try:
            async with asyncio.timeout(remaining()):
                value = await operation
            remaining()
            return value
        except TimeoutError:
            raise Stop("wall_clock") from None

    try:
        while True:
            result.state = "model"
            reserved = model.estimate(messages)
            reserve(reserved)
            turn = await invoke(model.complete(messages, remaining()))
            if not isinstance(turn, Turn):
                raise ValueError("invalid_model_response")
            if turn.usage is not None:
                if (
                    turn.usage.tokens > reserved.tokens
                    or turn.usage.cost > reserved.cost
                ):
                    raise ValueError("provider_usage_exceeds_reservation")
                result.tokens -= reserved.tokens - turn.usage.tokens
                result.cost -= reserved.cost - turn.usage.cost
            if not turn.calls:
                if not turn.text.strip():
                    raise ValueError("empty_model_response")
                result.text, result.state = turn.text, "done"
                return result
            if quota_recovered:
                raise Stop("tool_quota_exhausted")
            messages.append(
                {
                    "role": "assistant",
                    "content": turn.text,
                    "tool_calls": [
                        {
                            "id": c.id,
                            "type": "function",
                            "function": {"name": c.name, "arguments": c.arguments},
                        }
                        for c in turn.calls
                    ],
                }
            )
            pending_calls = list(turn.calls)
            retried = False
            for call in pending_calls:
                if call not in turn.calls:
                    messages.append(
                        {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": call.id,
                                    "type": "function",
                                    "function": {
                                        "name": call.name,
                                        "arguments": call.arguments,
                                    },
                                }
                            ],
                        }
                    )
                result.state = "tool"
                remaining()
                quota = (
                    "tool_calls"
                    if result.tool_calls >= limits.tool_calls
                    else "search_limit"
                    if call.name == "web_search" and counts[call.name] >= 3
                    else "fetch_limit"
                    if call.name == "web_fetch" and counts[call.name] >= 8
                    else ""
                )
                if quota and limits.profile and not quota_recovered:
                    quota_recovered = True
                    for denied in pending_calls[pending_calls.index(call) :]:
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": denied.id,
                                "content": json.dumps(
                                    {
                                        "error": "tool_quota_exhausted",
                                        "reason": quota,
                                        "tools_executed": result.tool_calls,
                                        "tool_limit": limits.tool_calls,
                                        "searches_executed": counts["web_search"],
                                        "search_limit": 3,
                                        "fetches_executed": counts["web_fetch"],
                                        "fetch_limit": 8,
                                    }
                                ),
                            }
                        )
                    logging.getLogger(__name__).info(
                        json.dumps(
                            {
                                "event": "tool_quota_exhausted",
                                "reason": quota,
                                "executed": result.tool_calls,
                                "searches": counts["web_search"],
                                "search_limit": 3,
                                "fetches": counts["web_fetch"],
                                "fetch_limit": 8,
                                "tool_limit": limits.tool_calls,
                            }
                        )
                    )
                    break
                if result.tool_calls >= limits.tool_calls:
                    raise Stop("tool_calls")
                if call.name == "web_search" and counts[call.name] >= 3:
                    raise Stop("search_limit")
                if call.name == "web_fetch" and counts[call.name] >= 8:
                    raise Stop("fetch_limit")
                try:
                    canonical = json.dumps(json.loads(call.arguments), sort_keys=True)
                except json.JSONDecodeError:
                    canonical = call.arguments
                recent.append((call.name, canonical))
                if len(recent) >= 3 and recent[-1] == recent[-2] == recent[-3]:
                    raise Stop("loop_detected")
                reserve(tools.estimate(call))
                result.tool_calls += 1
                counts[call.name] += 1
                output = await invoke(tools.execute(call, min(15, remaining())))
                if not isinstance(output, dict):
                    raise ValueError("invalid_tool_response")
                if (
                    retry_web
                    and not retried
                    and call.name == "web_search"
                    and output.get("error") in {"timeout", "search_unavailable"}
                ):
                    arguments = json.loads(call.arguments)
                    arguments["query"] = str(arguments["query"]) + " official source"
                    retry = Call(
                        call.id + "-retry",
                        call.name,
                        json.dumps(arguments, ensure_ascii=False),
                    )
                    pending_calls.append(retry)
                    retried = True
                event: Message = {
                    "tool": call.name,
                    "arguments": call.arguments,
                    "output": output,
                }
                result.trace.append(event)
                logging.getLogger(__name__).info(
                    json.dumps(
                        {
                            "event": "tool_finished",
                            "tool": call.name,
                            "count": result.tool_calls,
                        }
                    )
                )
                if call.name in terminal_tools and "error" not in output:
                    result.state = "done"
                    return result
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(output, ensure_ascii=False),
                    }
                )
    except Stop as exc:
        result.reason = str(exc)
    except (ValueError, RuntimeError, OSError):
        result.reason = "provider_error"
    result.state = "stopped"
    result.text = (
        f"Explicit stop: {result.reason}. Tools executed: {result.tool_calls}."
    )
    logging.getLogger(__name__).info(
        json.dumps(
            {
                "event": "request_stopped",
                "reason": result.reason,
                "tokens_reserved": result.tokens,
                "cost_reserved": str(result.cost),
            }
        )
    )
    return result
