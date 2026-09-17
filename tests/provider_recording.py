"""Record real provider streams, including interrupted attempts, for exact replay."""

import asyncio
import copy
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import aclosing
import time
import re
from typing import Any


async def capture_stream(
    source: AsyncGenerator[dict[str, Any], None],
    save: Callable[[Any], None],
) -> AsyncGenerator[dict[str, Any], None]:
    events: list[dict[str, Any]] = []
    previous = time.monotonic()
    try:
        async with aclosing(source):
            async for event in source:
                now = time.monotonic()
                events.append({"delay": now - previous, "event": event})
                previous = now
                if "result" in event:
                    save(events)
                yield event
    except (RuntimeError, TimeoutError, asyncio.CancelledError) as exc:
        # The enclosing request timeout cancels upstream. Preserve that real
        # interruption, never arbitrary exception text or a fabricated result.
        events.append(
            {
                "delay": time.monotonic() - previous,
                "error": "provider_error"
                if isinstance(exc, RuntimeError)
                else "timeout",
            }
        )
        save(events)
        raise


async def replay_stream(rows: Any) -> AsyncGenerator[dict[str, Any], None]:
    for row in rows:
        if "delay" not in row:
            yield row
            continue
        await asyncio.sleep(row["delay"])
        if "error" in row:
            if row["error"] == "timeout":
                raise TimeoutError("recorded_timeout")
            assert row["error"] == "provider_error", "unknown_recorded_error"
            raise RuntimeError("provider_error")
        yield row["event"]


async def capture_tool(source: Awaitable[Any], save: Callable[[Any], None]) -> Any:
    """Keep a real tool cancellation so replay preserves the following exchange."""
    try:
        result = await source
    except (ValueError, TimeoutError, asyncio.CancelledError) as exc:
        cancelled = isinstance(exc, asyncio.CancelledError)
        message = "" if cancelled else str(exc)
        assert re.fullmatch(r"[a-z_]*", message), "unsafe_tool_error_recording"
        save(
            {
                "recorded_exception": "TimeoutError"
                if cancelled
                else type(exc).__name__,
                "message": message,
            }
        )
        raise
    save(result)
    return result


class ExactHistory:
    """Opt-in acquisition reuse: only byte-equivalent request values, once per row."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.used: set[int] = set()

    def take(self, kind: str, request: object) -> Any:
        for index, row in enumerate(self.rows):
            if (
                index not in self.used
                and row["kind"] == kind
                and row["request"] == request
            ):
                self.used.add(index)
                return copy.deepcopy(row["response"])
        return None
