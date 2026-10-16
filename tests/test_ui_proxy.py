"""The UI relay must stream large uploads and inject the shell on every page load."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import threading
import unittest

from services.orchestrator.terminal_stack import loopback_html_injector

SHELL = b"<html><head><title>x</title></head><body>shell</body></html>"


class Backend(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args: object) -> None:
        pass

    def do_GET(self) -> None:
        body = SHELL if self.path == "/" else b"plain"
        self.send_response(200)
        self.send_header(
            "Content-Type", "text/html" if self.path == "/" else "text/plain"
        )
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(SHELL)))
        self.end_headers()

    def do_POST(self) -> None:
        size = int(self.headers["Content-Length"])
        data = self.rfile.read(size)
        body = str(len(data)).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class UiProxyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.backend = ThreadingHTTPServer(("127.0.0.1", 0), Backend)
        threading.Thread(target=self.backend.serve_forever, daemon=True).start()
        self.addCleanup(self.backend.shutdown)
        context = loopback_html_injector(
            "127.0.0.1:0", ("127.0.0.1", self.backend.server_address[1])
        )
        self.host, self.port = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)

    def request(
        self, method: str, path: str, body: bytes | None = None
    ) -> tuple[int, bytes]:
        connection = http.client.HTTPConnection(self.host, self.port, timeout=10)
        connection.request(method, path, body=body)
        response = connection.getresponse()
        data = response.read()
        connection.close()
        return response.status, data

    def test_large_upload_is_streamed_to_the_backend(self) -> None:
        for size in (10_000, 300_000, 3_000_000):
            status, data = self.request("POST", "/upload", b"x" * size)
            self.assertEqual((status, data), (200, str(size).encode()))

    def test_every_page_load_gets_the_assets(self) -> None:
        for _ in range(3):
            status, data = self.request("GET", "/")
            self.assertEqual(status, 200)
            self.assertIn(b"/static/atlas/chat-ui.js", data)
            self.assertTrue(data.startswith(b"<html><head><title>x</title>"))

    def test_other_responses_and_head_requests_pass_through(self) -> None:
        self.assertEqual(self.request("GET", "/api"), (200, b"plain"))
        status, data = self.request("HEAD", "/")
        self.assertEqual((status, data), (200, b""))


if __name__ == "__main__":
    unittest.main()
