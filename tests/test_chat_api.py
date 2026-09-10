"""HTTP chat protocol, SSE, errors and exactly one journal row per request."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from services.orchestrator.chat_api import app
from services.orchestrator.chat_schema import ChatRequest
from services.orchestrator.interactions import Interaction


class ChatAPITests(unittest.TestCase):
    def test_json_sse_history_and_errors(self) -> None:
        async def respond(request: ChatRequest, item: Interaction) -> None:
            self.assertEqual(request.messages[-1].content, "Bonjour")
            item.reponse = "Réponse avec preuve"
            item.state = "done"
            item.tokens = {"in": 20, "out": 5}
            item.modele_utilise = "escalade"
            item.route_decision = "complexe"

        payload = {
            "model": "atlas",
            "messages": [{"role": "user", "content": "Bonjour"}],
        }
        with (
            tempfile.TemporaryDirectory() as root,
            patch.dict(os.environ, {"ATLAS_INTERACTION_DIR": root}),
            TestClient(app) as client,
        ):
            self.assertEqual(client.get("/v1/models").json()["data"][0]["id"], "atlas")
            with patch("services.orchestrator.chat_api.process", side_effect=respond):
                response = client.post("/v1/chat/completions", json=payload)
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(
                    data["choices"][0]["message"]["content"], "Réponse avec preuve"
                )
                self.assertEqual(data["usage"]["total_tokens"], 25)
                response = client.post(
                    "/v1/chat/completions", json={**payload, "stream": True}
                )
                self.assertIn("text/event-stream", response.headers["content-type"])
                chunks = [
                    line[6:]
                    for line in response.text.splitlines()
                    if line.startswith("data: ")
                ]
                self.assertEqual(chunks[-1], "[DONE]")
                self.assertEqual(
                    json.loads(chunks[0])["object"], "chat.completion.chunk"
                )
                self.assertEqual(
                    json.loads(chunks[0])["choices"][0]["delta"]["content"],
                    "Réponse avec preuve",
                )
            with patch(
                "services.orchestrator.chat_api.process",
                side_effect=RuntimeError("private-detail"),
            ):
                response = client.post("/v1/chat/completions", json=payload)
                self.assertEqual(response.status_code, 502)
                self.assertNotIn("private-detail", response.text)
            self.assertEqual(
                client.post("/v1/chat/completions", content="{").status_code, 400
            )
            self.assertEqual(
                client.post("/v1/chat/completions", json={"messages": []}).status_code,
                400,
            )
            self.assertEqual(
                client.post("/v1/chat/completions", content="x" * 200000).status_code,
                413,
            )
            rows = [
                json.loads(line)
                for path in Path(root).glob("*.jsonl")
                for line in path.read_text().splitlines()
            ]
            self.assertEqual(len(rows), 6)
            self.assertEqual(rows[0]["question"], "Bonjour")
            self.assertEqual(rows[2]["erreurs"], ["provider_error"])
            self.assertNotIn("private-detail", json.dumps(rows))
            self.assertGreater(rows[0]["latence_ms"]["total"], 0)
            with patch("services.orchestrator.chat_api.process", new=AsyncMock()):
                response = client.post("/v1/chat/completions", json=payload)
                self.assertEqual(response.status_code, 504)
                self.assertEqual(response.json()["error"]["code"], "request_stopped")

    def test_timeout_cancellation_and_safe_source_html(self) -> None:
        import asyncio

        async def slow(*args: object) -> None:
            await asyncio.sleep(30)
            self.fail("disconnected request was not cancelled")

        payload = {"messages": [{"role": "user", "content": "Bonjour"}]}
        with (
            tempfile.TemporaryDirectory() as root,
            patch.dict(os.environ, {"ATLAS_INTERACTION_DIR": root}),
            TestClient(app) as client,
        ):
            with patch(
                "services.orchestrator.chat_api.process", side_effect=TimeoutError
            ):
                self.assertEqual(
                    client.post("/v1/chat/completions", json=payload).status_code, 504
                )
            with (
                patch("services.orchestrator.chat_api.process", side_effect=slow),
                patch(
                    "starlette.requests.Request.is_disconnected",
                    new=AsyncMock(return_value=True),
                ),
            ):
                self.assertEqual(
                    client.post("/v1/chat/completions", json=payload).status_code, 499
                )
            self.assertEqual(client.get("/sources/bad").status_code, 400)
            with patch(
                "services.orchestrator.chat_api.source",
                new=AsyncMock(
                    return_value={
                        "source": "<script>",
                        "text": "<script>alert(1)</script>",
                    }
                ),
            ):
                response = client.get("/sources/" + "a" * 64)
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("<script>", response.text)
                self.assertIn("&lt;script&gt;", response.text)
            with patch(
                "services.orchestrator.chat_api.source",
                new=AsyncMock(side_effect=ValueError),
            ):
                self.assertEqual(client.get("/sources/" + "a" * 64).status_code, 404)
            rows = [
                json.loads(line)
                for p in Path(root).glob("*.jsonl")
                for line in p.read_text().splitlines()
            ]
            self.assertEqual([r["erreurs"] for r in rows], [["timeout"], ["cancelled"]])
