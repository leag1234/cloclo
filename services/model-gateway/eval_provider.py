"""POC-R2/F8: bounded evaluation transport, provider usage and observed SSE timing."""

import json
import math
import os
import signal
from contextlib import contextmanager
from collections.abc import Iterator
from types import FrameType
from pathlib import Path
from time import monotonic
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

import yaml
from pydantic import BaseModel, ConfigDict, Field


@contextmanager
def deadline(seconds: float) -> Iterator[None]:
    """The evaluation CLI runs on Linux's main thread; interrupt slow SSE reads."""

    def expired(signum: int, frame: FrameType | None) -> None:
        raise TimeoutError("eval_deadline")

    if signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0):
        raise RuntimeError("nested_eval_timer")
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


class StreamUsage(BaseModel):
    model_config = ConfigDict(strict=True)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=1, le=2048)
    prompt_tokens_details: dict[str, int] | None = None


def summarize_stream(
    events: list[tuple[float, bytes]], input_price: float, output_price: float
) -> dict[str, Any]:
    if any(not math.isfinite(p) or p < 0 for p in (input_price, output_price)):
        raise ValueError("invalid_price")
    text, first, last, elapsed, stopped, done = "", None, None, 0.0, False, False
    usage = None
    for seconds, line in events:
        if not math.isfinite(seconds) or seconds < elapsed:
            raise ValueError("invalid_stream_time")
        elapsed = seconds
        if not line.startswith(b"data:"):
            continue
        data = line[5:].strip()
        if data == b"[DONE]":
            done = True
            break
        item = json.loads(data)
        if item.get("usage") is not None:
            usage = StreamUsage.model_validate(item["usage"])
        for choice in item.get("choices", []):
            if choice.get("index", 0) != 0:
                raise ValueError("unexpected_choice")
            content = choice.get("delta", {}).get("content")
            if content:
                if not isinstance(content, str) or stopped:
                    raise ValueError("invalid_content")
                text += content
                first = seconds if first is None else first
                last = seconds
            reason = choice.get("finish_reason")
            if reason is not None:
                if reason != "stop":
                    raise ValueError("incomplete_generation")
                stopped = True
    if not done or not stopped or usage is None or not text or first is None:
        raise ValueError("incomplete_stream")
    cached = (usage.prompt_tokens_details or {}).get("cached_tokens")
    if cached is not None and not 0 <= cached <= usage.prompt_tokens:
        raise ValueError("invalid_cached_tokens")
    return {
        "text": text,
        "telemetry": {
            "tokens": usage.prompt_tokens + usage.completion_tokens,
            "input_tokens": usage.prompt_tokens,
            "output_tokens": usage.completion_tokens,
            # Undiscounted catalogue cost is conservative when cache billing differs.
            "cost": (
                usage.prompt_tokens * input_price
                + usage.completion_tokens * output_price
            )
            / 1e6,
            "latency": elapsed,
            "ttft": first,
            "tok_s": usage.completion_tokens / (last - first)
            if last is not None and last > first
            else None,
            "cache_hit_ratio": cached / usage.prompt_tokens
            if cached is not None and usage.prompt_tokens
            else None,
            "source": "provider usage; client monotonic SSE timing; undiscounted catalogue cost",
        },
    }


class EvalProvider:
    def __init__(self) -> None:
        self.roles = {
            "system": os.environ["ESCALATION_MODEL"],
            "production": os.environ["JUDGE_MODEL"],
            "reference": "gpt-oss-120b",
        }
        self.prices = yaml.safe_load(
            Path(__file__).with_name("pricing.yaml").read_text()
        )["models"]
        if len(set(self.roles.values())) != 3:
            raise ValueError("non_independent_judges")

    def complete(self, role: str, messages: list[dict[str, str]]) -> dict[str, Any]:
        if role not in self.roles or not messages or len(messages) > 100:
            raise ValueError("invalid_eval_request")
        if any(
            set(m) != {"role", "content"}
            or m["role"] not in {"system", "user", "assistant"}
            or not isinstance(m["content"], str)
            or not m["content"].strip()
            for m in messages
        ):
            raise ValueError("invalid_eval_messages")
        model = self.roles[role]
        price = self.prices[model]
        rates = [float(price[k]) for k in ("input_eur_per_mtok", "output_eur_per_mtok")]
        if any(not math.isfinite(p) or p < 0 for p in rates):
            raise ValueError("invalid_price")
        # UTF-8 bytes plus framing bound input tokens before the paid call.
        size = len(json.dumps(messages, ensure_ascii=False).encode()) + 32 * len(
            messages
        )
        reservation = (size * rates[0] + 2048 * rates[1]) / 1e6
        if size > 32000 or reservation > 0.05:
            raise ValueError("eval_request_budget")
        endpoint = os.environ["SCW_GENERATIVE_BASE_URL"].rstrip("/")
        if not endpoint.startswith("https://"):
            raise ValueError("provider_configuration")
        body = {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": 2048,
            "stream": True,
            "stream_options": {"include_usage": True},
            "reasoning_effort": "none" if role == "system" else "low",
        }
        request = Request(
            endpoint + "/chat/completions",
            data=json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + os.environ["SCW_GENERATIVE_API_KEY"],
            },
        )
        started = monotonic()
        events = []
        received = 0
        try:
            with deadline(120), urlopen(request, timeout=120) as response:
                while True:
                    line = response.readline(800001)
                    if not line:
                        break
                    seconds = monotonic() - started
                    received += len(line)
                    if seconds > 120 or received > 800000:
                        raise ValueError("eval_response_budget")
                    events.append((seconds, line))
                    if line.strip() == b"data: [DONE]":
                        break
        except URLError:
            raise RuntimeError("eval_provider_error") from None
        result = summarize_stream(events, *rates)
        if result["telemetry"]["cost"] > reservation:
            raise ValueError("usage_exceeded_reservation")
        return result | {"role": role, "model": model}
