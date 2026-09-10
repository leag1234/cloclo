"""One-command local CPU stack; cloud provisioning is deliberately absent."""

import os
import signal
import subprocess
import threading
import time
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

import uvicorn
from gateway_cpu import CPUModels
from http_gateway import serve

from services.retrieval.pipeline import ingest
from services.retrieval.search import Gateway
from services.retrieval.store import Store

WEBUI_IMAGE = "ghcr.io/open-webui/open-webui:v0.11.3@sha256:41daa0cf2561a5d4c8d1ff31ee2a98d93ab4d3ac2605cac69366ff6a3374a933"


def docker(*args: str) -> str:
    result = subprocess.run(["docker", *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("docker_operation_failed:" + args[0])
    return result.stdout.strip()


def docker_run(name: str, image: str, options: list[str]) -> None:
    docker("run", "--rm", "-d", "--name", name, *options, image)


def webui(name: str, persistent: bool) -> None:
    options = ["--network", "host", "--env-file", "infra/chat-ui.env"]
    if persistent:
        options.extend(["-v", "atlas-chat-ui:/app/backend/data"])
    docker_run(name, WEBUI_IMAGE, options)


def wait_http(url: str, timeout: float = 120) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError):
            time.sleep(0.2)
    raise RuntimeError("service_start_timeout")


@contextmanager
def stack(name: str = "atlas-chat", persistent: bool = True) -> Iterator[None]:
    servers: list[uvicorn.Server] = []
    threads: list[threading.Thread] = []
    database = name + "-db"
    started = False
    gateway = None
    try:
        volume = (
            ["-v", "atlas-chat-index:/var/lib/postgresql/data"] if persistent else []
        )
        docker_run(
            database,
            "pgvector/pgvector:pg16",
            ["-e", "POSTGRES_HOST_AUTH_METHOD=trust", "-p", "127.0.0.1::5432", *volume],
        )
        started = True
        port = docker("port", database, "5432").rsplit(":", 1)[1]
        os.environ["ATLAS_RETRIEVAL_DSN"] = (
            f"host=127.0.0.1 port={port} user=postgres dbname=postgres connect_timeout=2"
        )
        for attempt in range(60):
            if (
                subprocess.run(
                    ["docker", "exec", database, "pg_isready", "-U", "postgres"],
                    capture_output=True,
                ).returncode
                == 0
            ):
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("database_start_timeout")
        gateway = serve(CPUModels(), 8010)
        thread = threading.Thread(target=gateway.serve_forever, daemon=True)
        thread.start()
        threads.append(thread)
        os.environ["ATLAS_GATEWAY_URL"] = "http://127.0.0.1:8010"
        store = Store(os.environ["ATLAS_RETRIEVAL_DSN"])
        store.initialize()
        ingest(Path("corpus"), store, Gateway(os.environ["ATLAS_GATEWAY_URL"]))
        for app, port_number in (
            ("services.retrieval.api:app", 8011),
            ("services.orchestrator.chat_api:app", 8020),
        ):
            server = uvicorn.Server(
                uvicorn.Config(
                    app,
                    host="127.0.0.1",
                    port=port_number,
                    log_level="error",
                    access_log=False,
                )
            )
            servers.append(server)
            thread = threading.Thread(target=server.run, daemon=True)
            thread.start()
            threads.append(thread)
        wait_http("http://127.0.0.1:8011/openapi.json")
        wait_http("http://127.0.0.1:8020/v1/models")
        if not all(server.started for server in servers):
            raise RuntimeError("service_bind_failed")
        yield
    finally:
        for server in servers:
            server.should_exit = True
        if gateway is not None:
            gateway.shutdown()
            gateway.server_close()
        for thread in threads:
            thread.join(timeout=10)
        if started:
            docker("stop", database)


def main() -> None:
    for key in (
        "ESCALATION_MODEL",
        "SCW_GENERATIVE_BASE_URL",
        "SCW_GENERATIVE_API_KEY",
    ):
        if not os.environ.get(key):
            raise RuntimeError("missing_configuration:" + key)
    stopping = False

    def stop_requested(signum: int, frame: object) -> None:
        nonlocal stopping
        stopping = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop_requested)
    with stack():
        launched = False
        try:
            webui("atlas-chat-ui", True)
            launched = True
            wait_http("http://127.0.0.1:3000")
            print(
                "ATLAS prêt : http://localhost:3000 (tunnel SSH), GPU_LOCAL="
                + os.environ.get("GPU_LOCAL", "0"),
                flush=True,
            )
            while not stopping:
                time.sleep(0.2)
        finally:
            if launched:
                docker("stop", "atlas-chat-ui")


if __name__ == "__main__":
    main()
