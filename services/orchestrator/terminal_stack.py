"""Local user-file container with host-installed, fail-closed network containment."""

from contextlib import contextmanager
from collections.abc import Iterator
import json
import os
import socket
import subprocess
import select
import socketserver
import threading

import uvicorn

NETWORK = "atlas-files"
IMAGE = "ghcr.io/open-webui/open-terminal@sha256:3d52176700f2442e20556ef129ae980613389be773e269cf7fa0118f3b55669d"


@contextmanager
def loopback_forward(
    binding: str, target: tuple[str, int]
) -> Iterator[tuple[str, int]]:
    """Publish an internal bridge API without giving it an outbound route."""
    host, port = binding.rsplit(":", 1)
    if host != "127.0.0.1":
        raise ValueError("terminal_requires_loopback")
    stopping = threading.Event()

    class Handler(socketserver.BaseRequestHandler):
        def handle(self) -> None:
            try:
                with socket.create_connection(target, timeout=5) as remote:
                    peers = {self.request: remote, remote: self.request}
                    while peers and not stopping.is_set():
                        readable, _, _ = select.select(list(peers), [], [], 0.2)
                        for source in readable:
                            data = source.recv(65536)
                            if data:
                                peers[source].sendall(data)
                            else:
                                peers.pop(source).shutdown(socket.SHUT_WR)
            except OSError:
                # Closing both sockets exposes a transport failure to the caller.
                self.request.close()

    class Server(socketserver.ThreadingTCPServer):
        daemon_threads = True
        allow_reuse_address = True

    with Server((host, int(port)), Handler) as server:
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            yield str(server.server_address[0]), int(server.server_address[1])
        finally:
            stopping.set()
            server.shutdown()
            worker.join(timeout=5)


def command(*args: str) -> str:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("terminal_setup_failed:" + args[0])
    return result.stdout.strip()


def network_gateway() -> str:
    value = json.loads(command("docker", "network", "inspect", NETWORK))[0]
    if (
        not value.get("Internal")
        or value.get("Labels", {}).get("atlas.owner") != "files"
    ):
        raise RuntimeError("terminal_network_owner_mismatch")
    return str(value["IPAM"]["Config"][0]["Gateway"])


def firewall(pid: str, family: str, *args: str) -> str:
    prefix = [] if os.geteuid() == 0 else ["sudo", "-n"]
    return command(*prefix, "nsenter", "-t", pid, "-n", family, *args)


def contain(name: str) -> None:
    pid = command("docker", "inspect", "--format", "{{.State.Pid}}", name)
    for family in ("iptables", "ip6tables"):
        # The API is held behind a startup latch until BOTH families are closed.
        # No new outbound connection is allowed, including Docker's DNS proxy.
        firewall(pid, family, "-P", "OUTPUT", "DROP")
        firewall(pid, family, "-F", "OUTPUT")
        firewall(
            pid,
            family,
            "-A",
            "OUTPUT",
            "-m",
            "conntrack",
            "--ctstate",
            "ESTABLISHED,RELATED",
            "-j",
            "ACCEPT",
        )
        firewall(pid, family, "-A", "OUTPUT", "-j", "REJECT")
        rules = firewall(pid, family, "-S", "OUTPUT")
        if "-P OUTPUT DROP" not in rules or "-A OUTPUT -j REJECT" not in rules:
            raise RuntimeError("terminal_containment_unverified")
    command("docker", "exec", name, "touch", "/tmp/atlas-network-ready")


def adapter_socket(port: int) -> socket.socket:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((network_gateway(), port))
    listener.listen(128)
    listener.setblocking(False)
    return listener


@contextmanager
def terminal(name: str, binding: str) -> Iterator[None]:
    from services.orchestrator.serving import wait_http

    if not os.environ.get("OPEN_TERMINAL_API_KEY", "").strip():
        raise RuntimeError("missing_configuration: OPEN_TERMINAL_API_KEY")
    exists = command(
        "docker",
        "network",
        "ls",
        "--filter",
        "name=^" + NETWORK + "$",
        "--format",
        "{{.Name}}",
    )
    if not exists:
        command(
            "docker",
            "network",
            "create",
            "--internal",
            "--label",
            "atlas.owner=files",
            NETWORK,
        )
    network_gateway()
    existing = command(
        "docker",
        "ps",
        "-a",
        "--filter",
        "name=^/" + name + "$",
        "--format",
        "{{.Names}}",
    )
    if existing:
        details = json.loads(command("docker", "inspect", name))[0]
        if details["Config"].get("Labels", {}).get("atlas.owner") != "files":
            raise RuntimeError("terminal_container_owner_mismatch")
        command("docker", "rm", "-f", name)
    started = False
    try:
        command(
            "docker",
            "run",
            "-d",
            "--name",
            name,
            "--label",
            "atlas.owner=files",
            "--network",
            NETWORK,
            "--network-alias",
            "open-terminal",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--read-only",
            "--memory",
            "2g",
            "--cpus",
            "2",
            "--pids-limit",
            "128",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=128m,uid=1000,gid=1000",
            "-v",
            "atlas-terminal-files:/home/user",
            "-e",
            "OPEN_TERMINAL_API_KEY",
            "-e",
            "OPEN_TERMINAL_EXECUTE_TIMEOUT=30",
            "--entrypoint",
            "/bin/sh",
            IMAGE,
            "-c",
            "while ! test -f /tmp/atlas-network-ready; do sleep 0.1; done; exec python3 -m open_terminal run --host 0.0.0.0 --port 8000",
        )
        started = True
        contain(name)
        details = json.loads(command("docker", "inspect", name))[0]
        address = details["NetworkSettings"]["Networks"][NETWORK]["IPAddress"]
        with loopback_forward(binding, (address, 8000)):
            try:
                wait_http("http://" + binding + "/docs", 30)
            except RuntimeError:
                logs = subprocess.run(
                    ["docker", "logs", name], capture_output=True, text=True
                )
                detail = (logs.stdout + logs.stderr).replace(
                    os.environ["OPEN_TERMINAL_API_KEY"], "[REDACTED]"
                )
                raise RuntimeError("terminal_start_failed: " + detail[-2000:]) from None
            yield
    finally:
        if started and command(
            "docker",
            "ps",
            "-a",
            "--filter",
            "name=^/" + name + "$",
            "--format",
            "{{.Names}}",
        ):
            command("docker", "stop", name)
            command("docker", "rm", name)


@contextmanager
def user_interface(name: str, persistent: bool) -> Iterator[None]:
    """Expose the native UI and adapter on the contained user-file network."""
    from services.orchestrator.serving import docker, wait_http, webui

    listener = adapter_socket(8020)
    adapter = uvicorn.Server(
        uvicorn.Config(
            "services.orchestrator.chat_api:app", log_level="error", access_log=False
        )
    )
    worker = threading.Thread(
        target=lambda: adapter.run(sockets=[listener]), daemon=True
    )
    worker.start()
    started = False
    try:
        webui(name, persistent)
        started = True
        details = json.loads(docker("inspect", name))[0]
        address = details["NetworkSettings"]["Networks"][NETWORK]["IPAddress"]
        with loopback_forward("127.0.0.1:3000", (address, 3000)):
            wait_http("http://127.0.0.1:3000")
            yield
    finally:
        if started:
            docker("stop", name)
        adapter.should_exit = True
        worker.join(timeout=10)
        listener.close()
