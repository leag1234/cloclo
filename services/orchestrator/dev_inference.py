"""Authenticated inference: reserve before I/O, settle usage or retain the bound."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import aclosing
import json
import logging
from time import monotonic
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import ValidationError
import dev_gateway as gateway
from services.orchestrator.dev_auth import QuotaError, Store
from services.orchestrator.dev_chat import ChatInput, Output
from services.orchestrator.dev_input import responses
from services.orchestrator.dev_responses import Wire


def error(code: str, status: int) -> JSONResponse:
    return JSONResponse({"error": {"type": code, "message": code}}, status_code=status)


async def drive(
    store: Store,
    developer: str,
    request_id: str,
    plan: gateway.Plan,
    output: Output,
    deadline: float,
) -> AsyncGenerator[dict[str, Any], None]:
    settled, charged, started = False, None, monotonic()
    try:
        if deadline <= monotonic():
            raise TimeoutError("timeout")
        async with (
            asyncio.timeout(max(0, deadline - monotonic())),
            aclosing(gateway.events(plan)) as frames,
        ):
            async for frame in frames:
                chunk = output.feed(frame)
                if "usage" in frame:
                    charged = frame["cost_micro_eur"]
                    store.finish(
                        request_id,
                        charged,
                        frame["usage"]["prompt_tokens"],
                        frame["usage"]["completion_tokens"],
                    )
                    settled = True
                    if charged > plan.reserved:
                        raise RuntimeError("budget_exceeded")
                yield chunk
    except (ValueError, RuntimeError, TimeoutError, OSError, KeyError, TypeError):
        yield {"error": {"type": "provider_error", "message": "provider_error"}}
    finally:
        if not settled:
            store.finish(request_id, None)
        logging.getLogger("uvicorn.error").info(
            json.dumps(
                {
                    "event": "devapi_request",
                    "request": request_id,
                    "developer": developer,
                    "duration_ms": round((monotonic() - started) * 1000),
                    "charged_micro_eur": charged,
                    "reserved_micro_eur": plan.reserved,
                    "usage": output.usage,
                }
            )
        )


async def chat(request: Request, protocol: str = "chat") -> Response:
    deadline = monotonic() + 120
    try:
        body = bytearray()
        async with asyncio.timeout(120):
            async for piece in request.stream():
                body.extend(piece)
                if len(body) > 1048576:
                    return error("body_limit", 400)
        raw = json.loads(body)
        parsed = (
            responses(raw) if protocol == "responses" else ChatInput.model_validate(raw)
        )
        plan = gateway.prepare(parsed)
        store, developer = request.state.store, request.state.developer
        request_id = store.reserve(developer, plan.reserved)
    except QuotaError:
        return error("quota_exceeded", 429)
    except PermissionError:
        return error("unauthorized", 401)
    except (ValueError, TypeError, AttributeError, ValidationError) as exc:
        code = (
            str(exc)
            if str(exc) in {"cost_budget", "context_exceeded"}
            else "invalid_request"
        )
        return error(code, 400)
    except (TimeoutError, KeyError):
        return error("unavailable", 503)
    output = Output(request_id, parsed)
    wire = Wire(output, raw) if protocol == "responses" else None

    async def chunks() -> AsyncGenerator[str, None]:
        if wire:
            for event in wire.start():
                yield (
                    "event: " + event["type"] + "\ndata: " + json.dumps(event) + "\n\n"
                )
        async with aclosing(
            drive(store, developer, request_id, plan, output, deadline)
        ) as frames:
            async for chunk in frames:
                if wire:
                    for event in wire.feed(chunk):
                        yield (
                            "event: "
                            + event["type"]
                            + "\ndata: "
                            + json.dumps(event)
                            + "\n\n"
                        )
                elif chunk.get("choices") != [] or parsed.stream_options.include_usage:
                    yield "data: " + json.dumps(chunk) + "\n\n"
        if wire is None:
            yield "data: [DONE]\n\n"

    if parsed.stream:
        return StreamingResponse(
            chunks(),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no"},
        )
    async with aclosing(
        drive(store, developer, request_id, plan, output, deadline)
    ) as frames:
        async for frame in frames:
            if "error" in frame:
                return error("provider_error", 502)
            if wire:
                wire.feed(frame)
    return JSONResponse(wire.result() if wire else output.result())
