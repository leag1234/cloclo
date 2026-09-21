"""Same-origin local project UI and bounded proxy to retrieval-owned APIs."""

from packages.limits import LimitError

import asyncio
from pathlib import Path

import aiohttp
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from services.orchestrator.chat_pipeline import retrieval_url

router = APIRouter()
ROOT = Path(__file__).parent
CSP = "default-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"


@router.get("/project-ui")
def ui() -> Response:
    return HTMLResponse(
        (ROOT / "project_ui.html").read_text(), headers={"Content-Security-Policy": CSP}
    )


@router.get("/project-ui.js")
def javascript() -> Response:
    return Response((ROOT / "project_ui.js").read_text(), media_type="text/javascript")


@router.api_route("/projects", methods=["GET", "POST"])
@router.api_route("/projects/{path:path}", methods=["GET", "POST", "PATCH", "DELETE"])
async def proxy(request: Request, path: str = "") -> Response:
    if request.headers.get("origin") not in (None, str(request.base_url).rstrip("/")):
        return JSONResponse({"error": "origin_rejected"}, status_code=403)
    if any(part in {".", ".."} for part in path.split("/")) or any(
        c in path for c in "?#!\\"
    ):
        return JSONResponse({"error": "invalid_path"}, status_code=400)
    try:
        data = bytearray()
        async with asyncio.timeout(35):
            async for chunk in request.stream():
                data.extend(chunk)
                if len(data) > 160000:
                    raise LimitError("body_limit", len(data), 160000, "bytes")
            async with aiohttp.ClientSession(trust_env=False) as client:
                async with client.request(
                    request.method,
                    retrieval_url() + "/projects" + ("/" + path if path else ""),
                    data=bytes(data),
                    headers={"Content-Type": "application/json"},
                    allow_redirects=False,
                ) as reply:
                    result = bytearray()
                    async for chunk in reply.content.iter_chunked(16384):
                        result.extend(chunk)
                        if len(result) > 800000:
                            raise LimitError(
                                "response_limit", len(result), 800000, "bytes"
                            )
                    return Response(
                        bytes(result),
                        status_code=reply.status,
                        media_type="application/json",
                    )
    except LimitError as exc:
        return JSONResponse({"error": exc.code, "message": exc.detail}, status_code=413)
    except (aiohttp.ClientError, TimeoutError, ValueError):
        return JSONResponse({"error": "project_unavailable"}, status_code=503)
