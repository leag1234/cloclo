"""Keep the real native UI alive through every external verifier assertion."""

from collections.abc import Iterator
from contextlib import contextmanager

from services.orchestrator.serving import docker, wait_http, webui


@contextmanager
def native_ui(name: str) -> Iterator[None]:
    started = False
    try:
        webui(name, False)
        started = True
        wait_http("http://127.0.0.1:3000")
        yield
    finally:
        if started:
            docker("stop", name)
