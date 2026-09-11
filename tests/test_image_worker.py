"""The worker HTTP protocol runs with a model double confined to this test."""

import json
import importlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread
import unittest
from unittest.mock import MagicMock, patch
from urllib.request import Request, urlopen
from PIL import Image
import image_worker


class WorkerTests(unittest.TestCase):
    def test_worker_loads_pipeline_and_serves_png(self) -> None:
        ready = Event()
        servers: list[ThreadingHTTPServer] = []
        modules = MagicMock()
        modules.FluxPipeline.from_pretrained.return_value.to.return_value.return_value.images = [
            Image.new("RGB", (512, 512), "red")
        ]

        def server(
            address: object, handler: type[BaseHTTPRequestHandler]
        ) -> ThreadingHTTPServer:
            result = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            servers.append(result)
            ready.set()
            return result

        with (
            patch.object(importlib, "import_module", return_value=modules),
            patch.object(image_worker, "ThreadingHTTPServer", side_effect=server),
        ):
            thread = Thread(target=image_worker.main, daemon=True)
            thread.start()
            self.assertTrue(ready.wait(5))
            try:
                url = f"http://127.0.0.1:{servers[0].server_port}"
                with urlopen(url + "/health", timeout=5) as response:
                    self.assertEqual(response.status, 200)
                with urlopen(
                    Request(url + "/generate", data=b'{"prompt":"a cube"}'), timeout=5
                ) as response:
                    result = json.load(response)
                self.assertTrue(result["image"].startswith("data:image/png;base64,"))
                modules.FluxPipeline.from_pretrained.return_value.to.assert_called_once_with(
                    "cuda"
                )
            finally:
                servers[0].shutdown()
                thread.join(5)
                servers[0].server_close()
