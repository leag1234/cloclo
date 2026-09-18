"""One-command local CPU stack; cloud provisioning is deliberately absent."""

import os
import json
import signal
import subprocess
import threading
import time
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

from packages.configuration import CHAT_REQUIRED_ENV, require_env
from services.orchestrator.webui import configure

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
    existing = docker(
        "ps", "-a", "--filter", "name=^/" + name + "$", "--format", "{{.Names}}"
    )
    if existing:
        actual = docker("inspect", "--format", "{{.Config.Image}}", name)
        if actual != image:
            raise RuntimeError("container_owner_mismatch")
        try:
            docker("rm", "-f", name)
        except RuntimeError:
            # --rm may already be removing a gracefully stopped container.
            deadline = time.monotonic() + 5
            while docker(
                "ps", "-a", "--filter", "name=^/" + name + "$", "--format", "{{.Names}}"
            ):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.1)
    docker("run", "--rm", "-d", "--name", name, *options, image)


def webui(name: str, persistent: bool) -> None:
    from services.orchestrator.terminal_stack import NETWORK, network_gateway

    gateway = network_gateway()
    os.environ["TERMINAL_SERVER_CONNECTIONS"] = json.dumps(
        [
            {
                "id": "atlas-files",
                "url": "http://open-terminal:8000",
                "key": os.environ["OPEN_TERMINAL_API_KEY"],
                "auth_type": "bearer",
                "config": {"chat_uploads": "filesystem"},
                "enabled": True,
            }
        ]
    )
    options = [
        "--network",
        NETWORK,
        "--env-file",
        "infra/chat-ui.env",
        "-e",
        "HOST=0.0.0.0",
        "-e",
        "TERMINAL_SERVER_CONNECTIONS",
        "-e",
        f"OPENAI_API_BASE_URL=http://{gateway}:8020/v1",
        "-e",
        f"ATLAS_ADAPTER_URL=http://{gateway}:8020",
    ]
    options.extend(
        [
            "-v",
            str(Path("services/orchestrator/chat-ui.css").resolve())
            + ":/app/backend/open_webui/static/custom.css:ro",
        ]
    )
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
        except (URLError, TimeoutError, ConnectionError):
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


def run() -> None:
    require_env(CHAT_REQUIRED_ENV)
    os.environ.setdefault("ATLAS_SEARCH_PROVIDER", "tavily")
    require_env(
        ("TAVILY_API_KEY",)
        if os.environ["ATLAS_SEARCH_PROVIDER"] == "tavily"
        else ("SERPAPI_API_KEY",)
    )
    os.environ["ATLAS_IMAGE_ON_DEMAND"] = "1"
    stopping = False

    def stop_requested(signum: int, frame: object) -> None:
        nonlocal stopping
        stopping = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop_requested)
    from services.orchestrator.terminal_stack import terminal, user_interface

    # Open Terminal owns only user files; its loopback publisher is not a host mount.
    with terminal("atlas-open-terminal", "127.0.0.1:8000"), stack():
        os.environ["ATLAS_TERMINAL_ENABLED"] = "1"
        try:
            with user_interface("atlas-chat-ui", True):
                configure()
                print(
                    "ATLAS ready: http://localhost:3000 (SSH tunnel), GPU_LOCAL="
                    + os.environ.get("GPU_LOCAL", "0"),
                    flush=True,
                )
                while not stopping:
                    time.sleep(0.2)
        finally:
            os.environ.pop("ATLAS_TERMINAL_ENABLED", None)


def main() -> None:
    from services.orchestrator.serve_owner import ownership

    with ownership():
        run()


if __name__ == "__main__":
    main()
