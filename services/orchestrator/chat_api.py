"""Loopback OpenAI-compatible adapter with one journal row on every outcome."""

import asyncio
import os
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import ValidationError
import html

from services.orchestrator.chat_pipeline import process, source
from services.orchestrator.chat_schema import ChatRequest
from services.orchestrator.chat_stream import response as stream_response
from services.orchestrator.interactions import Interaction, write_interaction

from services.orchestrator.project_ui import router as project_router

app = FastAPI(title="ATLAS chat")
app.include_router(project_router)


@app.get("/v1/models")
def models() -> dict[str, object]:
    return {
        "object": "list",
        "data": [{"id": "atlas", "object": "model", "created": 0, "owned_by": "atlas"}],
    }


@app.get("/sources/{key}")
async def sources(key: str) -> Response:
    if len(key) != 64 or any(c not in "0123456789abcdef" for c in key):
        return JSONResponse({"error": "invalid_chunk_id"}, status_code=400)
    try:
        passage = await source(key)
    except (ValueError, RuntimeError, OSError):
        return JSONResponse({"error": "source_unavailable"}, status_code=404)
    return HTMLResponse(
        "<meta charset=utf-8><title>Source ATLAS</title><h1>"
        + html.escape(str(passage["source"]))
        + "</h1><pre style='white-space:pre-wrap'>"
        + html.escape(str(passage["text"]))
        + "</pre>",
        headers={
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"
        },
    )


async def execute(
    request: Request, payload: ChatRequest, item: Interaction, remaining: float
) -> None:
    task = asyncio.create_task(process(payload, item))
    try:
        async with asyncio.timeout(remaining):
            while not task.done():
                await asyncio.wait({task}, timeout=0.1)
                if await request.is_disconnected():
                    raise asyncio.CancelledError
            await task
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@app.post("/v1/chat/completions")
async def chat(request: Request) -> Response:
    if request.headers.get("origin") not in (None, str(request.base_url).rstrip("/")):
        return JSONResponse({"error": "origin_rejected"}, status_code=403)
    item, started = Interaction(), time.monotonic()
    status, code, payload = 200, "", None
    streaming = False
    try:
        body = bytearray()
        async with asyncio.timeout(5):
            async for piece in request.stream():
                body.extend(piece)
                if len(body) > 160000:
                    status, code = 413, "context_exceeded"
                    break
        if not code:
            try:
                payload = ChatRequest.model_validate_json(body)
            except (ValidationError, ValueError):
                status, code = 400, "invalid_request"
        if payload is not None:
            item.question = payload.messages[-1].content
            if payload.stream:
                streaming = True
                return stream_response(payload, item, started, process)
            await execute(
                request, payload, item, max(0, 120 - (time.monotonic() - started))
            )
            if item.state != "done":
                status = 502 if "provider_error" in item.erreurs else 504
                code = "request_stopped"
    except asyncio.CancelledError:
        status, code = 499, "cancelled"
    except TimeoutError:
        status, code = 504, "timeout"
    except Exception:
        # Never reflect provider/transport exception text into logs or the client.
        status, code = 502, "provider_error"
    finally:
        if code:
            item.erreurs.append(code)
            item.state, item.reponse = "error", ""
        if not streaming:
            item.latence_ms["total"] = (time.monotonic() - started) * 1000
            write_interaction(
                item,
                Path(os.environ.get("ATLAS_INTERACTION_DIR", "BRAIN/interactions")),
            )
    if code:
        return JSONResponse(
            {"error": {"message": code, "type": code, "code": code}}, status_code=status
        )
    usage = {
        "prompt_tokens": item.tokens["in"],
        "completion_tokens": item.tokens["out"],
        "total_tokens": sum(item.tokens.values()),
    }
    base = {"id": item.request_id, "created": int(time.time()), "model": "atlas"}
    message = {"role": "assistant", "content": item.reponse}
    return JSONResponse(
        {
            **base,
            "object": "chat.completion",
            "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
            "usage": usage,
        }
    )
