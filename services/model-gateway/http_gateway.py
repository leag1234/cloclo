"""Local HTTP boundary for the CPU retrieval models (contracts/m2-gateway)."""

import asyncio
import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer

from gateway_cpu import CPUModels, EMBEDDING_REVISION
from generation import Generator
from agent_provider import AgentProvider


def serve(backend: CPUModels, port: int = 8010) -> HTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            pass  # Request bodies and URLs must not enter infrastructure logs.

        def do_POST(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 800000:
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
            except RuntimeError:
                status, response = 502, {"code": "provider_error"}
            body = json.dumps(response).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return HTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with serve(CPUModels()) as server:
        server.serve_forever()
