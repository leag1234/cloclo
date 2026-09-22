"""M13 synthetic-only transport tests; no cloud or live inference."""

import base64
import io
import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock
from decimal import Decimal
from threading import Thread
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PIL import Image
import imagegen
import aiohttp
from packages.imagegen import ImagePrompt, image_request
from services.orchestrator.imagegen import process_image
from services.orchestrator.interactions import Interaction, write_interaction
from services.orchestrator.model import GatewayModel


def png(size: int = 1024) -> str:
    output = io.BytesIO()
    Image.new("RGB", (size, size), "red").save(output, "PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()


class ImageTests(unittest.IsolatedAsyncioTestCase):
    def test_input_and_intent(self) -> None:
        for text in (
            "",
            " ",
            "x" * 2001,
            "a naked child",
            "photo pornographique",
            "x\x00",
        ):
            with self.subTest(text=text[:20]), self.assertRaises(ValueError):
                ImagePrompt(prompt=text)
        for text in ("génère une image de cube", "Generate an image of a cube"):
            self.assertTrue(image_request(text))
        self.assertFalse(image_request("Décris cette image"))
        self.assertEqual(ImagePrompt(prompt="un cube rouge").prompt, "un cube rouge")

    async def test_budget_precedes_transport(self) -> None:
        with (
            patch.dict(
                os.environ,
                {"ATLAS_IMAGE_GPU_IP": "127.0.0.1", "ATLAS_IMAGE_GPU_EUR_H": "2.01"},
            ),
            patch.object(aiohttp, "ClientSession") as transport,
        ):
            with self.assertRaisesRegex(RuntimeError, "cost_budget"):
                await imagegen.complete({"prompt": "a cube"})
            transport.assert_not_called()

    async def test_real_http_png_boundary(self) -> None:
        import json

        payload = {"image": png(), "seconds": 0.1, "seed": 123, "steps": 4}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                pass

            def do_POST(self) -> None:
                data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                assert data == {"prompt": "Subjects: a cube", "seed": None}
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps(payload).encode())

        # Real local HTTP exercises bounded reads and PNG decoding.
        with ThreadingHTTPServer(("127.0.0.2", 8000), Handler) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with (
                    patch.object(
                        imagegen, "rewrite", AsyncMock(return_value="Subjects: a cube")
                    ),
                    patch.object(imagegen, "reservation", return_value=Decimal("0.01")),
                    patch.dict(
                        os.environ,
                        {
                            "ATLAS_IMAGE_GPU_IP": "127.0.0.2",
                            "ATLAS_IMAGE_GPU_EUR_H": "1.46988",
                        },
                    ),
                ):
                    result = await imagegen.complete({"prompt": "a cube"})
                    self.assertEqual(result["image"], png())
                    self.assertGreater(float(str(result["cost_eur"])), 0)
                    payload["image"] = png(8)
                    with self.assertRaisesRegex(ValueError, "invalid_provider_image"):
                        await imagegen.complete({"prompt": "a cube"})
            finally:
                server.shutdown()
                thread.join()

    async def test_chat_returns_image(self) -> None:
        item = Interaction()
        with patch.object(
            GatewayModel, "post", return_value={"image": png(), "cost_eur": 0.002}
        ) as transport:
            await process_image("génère une image de cube", item, language="fr")
        self.assertEqual(item.task_type, "imagegen")
        self.assertEqual(item.state, "done")
        self.assertNotIn("base64", item.reponse)
        from services.orchestrator.image_store import generated_image

        key = item.reponse.rsplit("/", 1)[1].removesuffix(")")
        self.assertEqual(
            generated_image(key).body, base64.b64decode(png().split(",", 1)[1])
        )
        self.assertTrue(transport.call_args.args[0].endswith("/images/generate"))

    async def test_image_bytes_never_enter_journal(self) -> None:
        item = Interaction(reponse=f"![Image]({png()})", task_type="imagegen")
        with tempfile.TemporaryDirectory() as directory:
            write_interaction(item, Path(directory))
            text = next(Path(directory).glob("*.jsonl")).read_text()
        self.assertNotIn("data:image", text)
        self.assertNotIn(png().split(",", 1)[1], text)
        self.assertIn("[IMAGE]", text)

    async def test_gateway_large_image_keeps_text_limit(self) -> None:
        import json

        body = json.dumps({"image": "x" * 900000}).encode()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                pass

            def do_POST(self) -> None:
                self.rfile.read(int(self.headers["Content-Length"]))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)

        with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_port}"
                result = await GatewayModel.post(url + "/images/generate", {}, 5)
                self.assertEqual(len(str(result["image"])), 900000)
                with self.assertRaisesRegex(ValueError, "gateway_response_limit"):
                    await GatewayModel.post(url + "/agent/complete", {}, 5)
            finally:
                server.shutdown()
                thread.join()
