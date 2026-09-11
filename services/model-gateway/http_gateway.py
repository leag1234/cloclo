"""Local HTTP boundary for the CPU retrieval models (contracts/m2-gateway)."""

import asyncio
import json
import logging
import select
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer

from gateway_cpu import CPUModels, EMBEDDING_REVISION
from generation import Generator
from agent_provider import AgentProvider
from vision import VisionProvider


def serve(backend: CPUModels, port: int = 8010) -> HTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            pass  # Request bodies and URLs must not enter infrastructure logs.

        def stream_response(self, request: object) -> None:
            from stream_transport import StreamRequest

            validated = StreamRequest.model_validate(request)
            provider = AgentProvider()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            self.connection.setblocking(False)

            async def send(event: dict[str, object]) -> None:
                await asyncio.get_running_loop().sock_sendall(
                    self.connection, ("data: " + json.dumps(event) + "\n\n").encode()
                )

            async def relay() -> None:
                from contextlib import aclosing

                async def produce() -> None:
                    async with aclosing(
                        provider.stream(validated.model_dump())
                    ) as events:
                        async for event in events:
                            await send(event)

                task = asyncio.create_task(produce())
                try:
                    while not task.done():
                        await asyncio.wait({task}, timeout=0.05)
                        readable, _, _ = select.select([self.connection], [], [], 0)
                        if readable and not self.connection.recv(1, socket.MSG_PEEK):
                            return
                    await task
                finally:
                    if not task.done():
                        task.cancel()
                    await asyncio.gather(task, return_exceptions=True)

            async def bounded_relay() -> None:
                try:
                    async with asyncio.timeout(validated.timeout):
                        await relay()
                except (ValueError, RuntimeError, TimeoutError, OSError):
                    async with asyncio.timeout(0.1):
                        await send({"error": "provider_error"})

            try:
                asyncio.run(bounded_relay())
            except (BrokenPipeError, ConnectionResetError):
                return
            except (ValueError, RuntimeError, TimeoutError, OSError):
                return

        def do_POST(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                maximum = 6 * 1024 * 1024 if self.path == "/vision/complete" else 800000
                if not 0 < length <= maximum:
                    raise ValueError("context_exceeded")
                self.connection.settimeout(30)
                request = json.loads(self.rfile.read(length))
                if not isinstance(request, dict):
                    raise ValueError("invalid_input")
                response: dict[str, object]
                if self.path == "/embeddings":
                    if set(request) != {"texts", "kind"} or request["kind"] not in {
                        "query",
                        "document",
                    }:
                        raise ValueError("invalid_input")
                    texts = request["texts"]
                    if not isinstance(texts, list) or not all(
                        isinstance(t, str) for t in texts
                    ):
                        raise ValueError("invalid_input")
                    response = {
                        "vectors": backend.embed(texts),
                        "revision": EMBEDDING_REVISION,
                    }
                elif self.path == "/rerank":
                    if set(request) != {"question", "passages"} or not isinstance(
                        request["question"], str
                    ):
                        raise ValueError("invalid_input")
                    passages = request["passages"]
                    if not isinstance(passages, list) or any(
                        not isinstance(p, dict)
                        or set(p) != {"chunk_id", "text"}
                        or not isinstance(p["text"], str)
                        or not isinstance(p["chunk_id"], str)
                        or len(p["chunk_id"]) != 64
                        or any(c not in "0123456789abcdef" for c in p["chunk_id"])
                        for p in passages
                    ):
                        raise ValueError("invalid_input")
                    ids = [p["chunk_id"] for p in passages]
                    if len(set(ids)) != len(ids):
                        raise ValueError("invalid_input")
                    scores = backend.rerank(
                        request["question"], [p["text"] for p in passages]
                    )
                    response = {
                        "scores": [
                            {"chunk_id": key, "score": value}
                            for key, value in zip(ids, scores, strict=True)
                        ]
                    }
                elif self.path == "/agent/config":
                    if set(request) - {"local_enabled"} or not isinstance(
                        request.get("local_enabled", True), bool
                    ):
                        raise ValueError("invalid_input")
                    response = AgentProvider().configuration(
                        request.get("local_enabled", True)
                    )
                elif self.path == "/agent/stream":
                    self.stream_response(request)
                    return
                elif self.path == "/vision/complete":
                    response = asyncio.run(VisionProvider().complete(request))
                elif self.path == "/agent/complete":
                    response = asyncio.run(AgentProvider().complete(request))
                elif self.path == "/answer":
                    response = Generator()(request)
                else:
                    raise ValueError("invalid_input")
                status = 200
            except ValueError as exc:
                reason = str(exc)
                code = (
                    "context_exceeded"
                    if reason == "context_exceeded"
                    else "provider_error"
                    if reason.startswith("invalid_provider_")
                    else "invalid_citation"
                    if reason == "invalid_citation"
                    else "invalid_input"
                )
                status, response = (
                    {
                        "context_exceeded": 413,
                        "provider_error": 502,
                        "invalid_citation": 502,
                        "invalid_input": 400,
                    }[code],
                    {"code": code},
                )
            except TypeError:
                status, response = 400, {"code": "invalid_input"}
            except TimeoutError:
                status, response = 504, {"code": "timeout"}
            except RuntimeError as exc:
                if self.path == "/vision/complete" and str(exc) == "cost_budget":
                    status, response = 504, {"code": "cost_budget"}
                else:
                    status, response = 502, {"code": "provider_error"}
            body = json.dumps(response).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with serve(CPUModels()) as server:
        server.serve_forever()
