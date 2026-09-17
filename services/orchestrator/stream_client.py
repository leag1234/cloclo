"""Gateway streaming boundary, invoked only after the harness reservation."""

from collections.abc import Awaitable, Callable
from contextvars import ContextVar
import json

import aiohttp

Sink = Callable[[dict[str, object]], Awaitable[None]]
sink_context: ContextVar[Sink | None] = ContextVar("stream_sink", default=None)


async def receive(
    url: str, payload: dict[str, object], timeout: float, sink: Sink
) -> dict[str, object]:
    total = 0
    result: dict[str, object] | None = None
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout),
            trust_env=False,
            read_bufsize=800000,
        ) as client:
            async with client.post(
                url, json=payload, allow_redirects=False
            ) as response:
                if response.status != 200:
                    raise RuntimeError("gateway_error")
                async for line in response.content:
                    total += len(line)
                    if total > (8000000 if payload.get("profile") else 1000000):
                        raise ValueError("stream_limit")
                    if not line.strip():
                        continue
                    if not line.startswith(b"data:") or result is not None:
                        raise ValueError("invalid_stream")
                    event = json.loads(line[5:])
                    if not isinstance(event, dict):
                        raise ValueError("invalid_stream")
                    if set(event) == {"result"} and isinstance(event["result"], dict):
                        result = event["result"]
                    elif set(event) == {"phase"} and event["phase"] in {
                        "reasoning_fallback",
                        "provider_fallback",
                    }:
                        await sink(event)
                    elif set(event) == {"delta"} and isinstance(event["delta"], dict):
                        delta = event["delta"]
                        if not delta or not set(delta) <= {
                            "content",
                            "reasoning_content",
                        }:
                            raise ValueError("invalid_delta")
                        if any(not isinstance(v, str) for v in delta.values()):
                            raise ValueError("invalid_delta")
                        await sink(event)
                    else:
                        raise ValueError("gateway_stream_error")
        if result is None:
            raise ValueError("incomplete_stream")
        return result
    except aiohttp.ClientError:
        raise RuntimeError("gateway_unavailable") from None
