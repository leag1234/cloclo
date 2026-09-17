"""Loopback OpenAI-compatible adapter with one journal row on every outcome."""

from packages.profiles import PROFILES

import asyncio
import json
import os
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import ValidationError
from packages.image_upload import UploadError
from services.orchestrator.image_store import prepare_uploads
import html

from services.orchestrator.chat_pipeline import process, source
from services.orchestrator.chat_schema import ChatRequest
from services.orchestrator.deadline import request_deadline
from services.orchestrator.chat_stream import response as stream_response
from services.orchestrator.model import GatewayError
from services.orchestrator.interactions import Interaction, write_interaction

from services.orchestrator.project_ui import router as project_router
from services.orchestrator.mcp_confirmation import router as mcp_router

from services.orchestrator.image_store import router as image_router

from services.orchestrator.app import app as harness_app

app = FastAPI(title="ATLAS chat")
app.mount("/harness", harness_app)

app.include_router(image_router)
app.include_router(project_router)

app.include_router(mcp_router)


@app.get("/v1/models")
def models() -> dict[str, object]:
    return {
        "object": "list",
        "data": [
            {"id": name, "object": "model", "created": 0, "owned_by": "atlas"}
            for name in PROFILES
        ],
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
    async with request_deadline(remaining):
        task = asyncio.create_task(process(payload, item))
        try:
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
    detail = ""
    try:
        body = bytearray()
        async with asyncio.timeout(5):
            async for piece in request.stream():
                body.extend(piece)
                if len(body) > 32 * 1024 * 1024:
                    status, code = 413, "request_size_exceeded"
                    detail = f"Request body: {len(body)} bytes, limit {32 * 1024 * 1024} bytes"
                    break
        if not code:
            try:
                raw = json.loads(body)
                if (
                    isinstance(raw, dict)
                    and isinstance(raw.get("messages"), list)
                    and raw["messages"]
                ):
                    last = raw["messages"][-1]
                    if isinstance(last, dict):
                        content = last.get("content", "")
                        if isinstance(content, str):
                            item.question = content[:32000]
                        elif isinstance(content, list):
                            item.question = "\n".join(
                                p["text"]
                                for p in content
                                if isinstance(p, dict)
                                and p.get("type") == "text"
                                and isinstance(p.get("text"), str)
                            )[:32000]
                raw, item.uploads, item.uploaded_images = await asyncio.to_thread(
                    prepare_uploads, raw
                )
                payload = ChatRequest.model_validate(raw)
            except UploadError as exc:
                status, code, detail = 413, exc.code, str(exc)
            except ValidationError as exc:
                status, code = 400, "invalid_request"
                # Do not reflect Pydantic inputs/context: these can contain image
                # data or credentials. Types and numeric bounds are safe.
                failures = exc.errors(
                    include_input=False, include_context=False, include_url=False
                )
                detail = "; ".join(str(e["type"]) for e in failures)
            except json.JSONDecodeError:
                status = 413 if len(body) > 160000 else 400
                code = "invalid_request"
                detail = f"Malformed JSON: {len(body)} bytes; malformed-body diagnostic limit 160000 bytes"
            except (ValueError, OSError):
                status, code, detail = (
                    400,
                    "invalid_request",
                    "Invalid JSON or image data",
                )
        if payload is not None:
            item.question = payload.messages[-1].text
            if payload.stream:
                streaming = True
                return stream_response(payload, item, started, process)
            await execute(
                request,
                payload,
                item,
                max(0, payload.timeout_seconds - (time.monotonic() - started)),
            )
            if item.state != "done":
                status = 502 if "provider_error" in item.erreurs else 504
                code = "request_stopped"
    except asyncio.CancelledError:
        status, code = 499, "cancelled"
    except GatewayError as exc:
        status, code, detail = exc.status, exc.code, exc.detail
    except TimeoutError:
        status, code = 504, "timeout"
        limit = (
            5.0 if payload is None else payload.timeout_seconds + item.startup_seconds
        )
        detail = f"Timeout: {time.monotonic() - started:.3f} seconds elapsed, limit {limit:.3f} seconds"
    except Exception:
        # Never reflect provider/transport exception text into logs or the client.
        status, code = 502, "provider_error"
    finally:
        if code:
            item.erreurs.append(code)
            item.state, item.reponse = "error", detail
            item.rejection = {"code": code, "message": detail}
        if not streaming:
            item.latence_ms["total"] = (time.monotonic() - started) * 1000
            write_interaction(
                item,
                Path(os.environ.get("ATLAS_INTERACTION_DIR", "BRAIN/interactions")),
            )
    if code:
        return JSONResponse(
            {"error": {"message": detail or code, "type": code, "code": code}},
            status_code=status,
        )
    usage = {
        "prompt_tokens": item.tokens["in"],
        "completion_tokens": item.tokens["out"],
        "total_tokens": sum(item.tokens.values()),
    }
    assert payload is not None
    base = {"id": item.request_id, "created": int(time.time()), "model": payload.model}
    message = {"role": "assistant", "content": item.reponse}
    if item.reasoning:
        message["reasoning_content"] = item.reasoning
    return JSONResponse(
        {
            **base,
            "object": "chat.completion",
            "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
            "usage": usage,
            "atlas": {
                "images": item.images,
                "uploaded_images": item.uploaded_images,
                "reasoning_effort": payload.reasoning_effort,
                "max_output_tokens": payload.max_tokens,
                "cost_eur": item.cout_eur,
                "provider_model": item.provider_model,
                "reasoning_retried": item.reasoning_retried,
                "status": json.loads(Path("prompts/activity-labels.json").read_text())[
                    payload.ui_locale
                ]["reasoning_fallback"]
                if item.reasoning_retried
                else "",
                "reasoning": {
                    "collapsed": True,
                    "trace_tokens": item.trace_tokens,
                    "answer_tokens": item.answer_tokens,
                    "estimated": item.token_split_estimated,
                },
            },
        }
    )
