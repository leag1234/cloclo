"""REQ-INF-012/013: project-scoped, disposable GPU lifecycle via Scaleway CLI."""

import fcntl
import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
from typing import Any

TAG = "atlas-m1"
STATE = Path("BRAIN/gpu-root.json")


def call(*args: str) -> Any:
    result = subprocess.run(
        ["scw", *args, "zone=" + os.environ["SCW_DEFAULT_ZONE"], "-o", "json"],
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )
    if result.returncode:
        # Provider output can contain request data; do not leak it into logs.
        raise RuntimeError(f"Scaleway {' '.join(args[:3])}: exit {result.returncode}")
    return json.loads(result.stdout) if result.stdout.strip() else None


def owned(service: str, resource: str) -> list[dict[str, Any]]:
    records = call(
        service, resource, "list", "project-id=" + os.environ["SCW_DEFAULT_PROJECT_ID"]
    )
    return [r for r in records if TAG in r.get("tags", [])]


def single(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    if len(records) > 1:
        raise RuntimeError("Multiple owned resources: manual reconciliation required")
    return records[0] if records else None


def create(service: str, resource: str, *args: str) -> Any:
    result = call(
        service,
        resource,
        "create",
        "project-id=" + os.environ["SCW_DEFAULT_PROJECT_ID"],
        "tags.0=" + TAG,
        *args,
    )
    return result["security_group"] if resource == "security-group" else result


def bootstrap(volume: str, model: str, fresh: bool) -> str:
    device = shlex.quote("/dev/disk/by-id/scsi-0SCW_sbs_volume-" + volume)
    public_key = os.environ.get("GPU_SSH_PUBLIC_KEY", "")
    if public_key and not re.fullmatch(
        r"ssh-ed25519 [A-Za-z0-9+/=]+(?: [^\n]*)?", public_key
    ):
        raise ValueError("Invalid diagnostic public key")
    revision = os.environ.get("LOCAL_MODEL_REVISION", "main")
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", revision):
        raise ValueError("Invalid model revision")
    script = f"""#!/bin/bash
set -Eeuo pipefail
mkdir -p /root/.ssh
printf '%s\\n' {shlex.quote(public_key)} >> /root/.ssh/authorized_keys
udevadm settle
DEV={device}
for i in $(seq 1 60); do [[ -b "$DEV" ]] && break; sleep 2; done
[[ -b "$DEV" ]]
{'if ! blkid "$DEV"; then mkfs.ext4 "$DEV"; fi' if fresh else 'test "$(blkid -s TYPE -o value "$DEV")" = ext4'}
mkdir -p /mnt/weights
mount "$DEV" /mnt/weights
systemctl enable --now docker
nvidia-smi
docker run -d --restart unless-stopped --gpus all --ipc=host --name vllm \\
 -p 8000:8000 -v /mnt/weights:/root/.cache/huggingface \\
 vllm/vllm-openai:v0.10.2 --model {shlex.quote(model)} --revision {shlex.quote(revision)} --served-model-name local \\
 --enable-prefix-caching --max-model-len 8192
"""
    return (
        script.split("docker run -d", 1)[0]
        if os.environ.get("GPU_WORKLOAD") == "image"
        else script
    )


def down() -> None:
    server = single(owned("instance", "server"))
    if server:
        root = server["volumes"]["0"]["id"]
        temporary = STATE.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "id": root,
                    "project": os.environ["SCW_DEFAULT_PROJECT_ID"],
                    "zone": os.environ["SCW_DEFAULT_ZONE"],
                }
            )
        )
        temporary.replace(STATE)
        call(
            "instance",
            "server",
            "terminate",
            server["id"],
            "with-ip=true",
            "with-block=false",
            "--wait",
        )
    if STATE.exists():
        root_state = json.loads(STATE.read_text())
        if (
            root_state["project"] != os.environ["SCW_DEFAULT_PROJECT_ID"]
            or root_state["zone"] != os.environ["SCW_DEFAULT_ZONE"]
        ):
            raise RuntimeError("Cleanup state belongs to another project/zone")
        volumes = call(
            "block",
            "volume",
            "list",
            "project-id=" + os.environ["SCW_DEFAULT_PROJECT_ID"],
        )
        if any(v["id"] == root_state["id"] for v in volumes):
            call("block", "volume", "delete", root_state["id"])
        STATE.unlink()
    for group in owned("instance", "security-group"):
        call("instance", "security-group", "delete", group["id"])
    Path("BRAIN/gpu_ip.txt").unlink(missing_ok=True)
    Path("BRAIN/gateway.env").unlink(missing_ok=True)
    print("[gpu-down] owned GPU, root disk and IP removed; weights retained")


def up() -> None:
    model = os.environ["LOCAL_MODEL"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", model):
        raise ValueError("Invalid LOCAL_MODEL repository identifier")
    client = str(ipaddress.IPv4Address(os.environ["GPU_CLIENT_IP"]))
    if single(owned("instance", "server")) or STATE.exists():
        raise RuntimeError("Run gpu-down before starting a fresh verification cycle")
    catalog = call("instance", "server-type", "list")
    # The image worker uses CPU offload on L4; BF16 weights are not resident.
    # Multiple affordable families avoid dependence on one type's capacity.
    preferences = [
        "L4-1-24G",
        "L4-2-24G",
        "L40S-1-48G",
        "H100-1-80G",
        "L40S-2-48G",
        "H100-SXM-2-80G",
    ]
    affordable = [
        r
        for t in preferences
        for r in catalog
        if r["name"] == t
        and r["hourly_price"]["units"] + r["hourly_price"]["nanos"] / 1e9
        <= float(os.environ["GPU_MAX_EUR_H"])
    ]
    # Creation confirms capacity; never substitute a pricier GPU.
    chosen = next(
        (r for r in affordable if r["availability"] in ("available", "scarce")),
        next(iter(affordable), None),
    )
    if chosen is None:
        raise RuntimeError("No compatible GPU available")
    price = chosen["hourly_price"]["units"] + chosen["hourly_price"]["nanos"] / 1e9
    if price > float(os.environ["GPU_MAX_EUR_H"]):
        raise RuntimeError("Available GPU exceeds recorded hourly budget")
    Path("BRAIN/gpu-cost.json").write_text(json.dumps({"hourly_eur": price}))
    print(
        f"[gpu-up] {chosen['name']} at {price} EUR/h excluding storage/IP", flush=True
    )
    weight = single(owned("block", "volume"))
    fresh = weight is None or "atlas-unformatted" in weight.get("tags", [])
    if weight is None:
        weight = create(
            "block",
            "volume",
            "name=atlas-weights",
            "tags.1=atlas-unformatted",
            "from-empty.size=200GB",
            "perf-iops=5000",
            "--wait",
        )
    group = create(
        "instance", "security-group", "name=atlas-gpu", "inbound-default-policy=drop"
    )
    for port in (22, 8000):
        call(
            "instance",
            "security-group",
            "create-rule",
            "security-group-id=" + group["id"],
            "protocol=TCP",
            "direction=inbound",
            "action=accept",
            "ip-range=" + client + "/32",
            "dest-port-from=" + str(port),
        )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sh") as init:
        init.write(bootstrap(weight["id"], model, fresh))
        init.flush()
        server = create(
            "instance",
            "server",
            "name=atlas-gpu",
            "type=" + chosen["name"],
            "image="
            + os.environ.get("GPU_IMAGE", "8063548b-7ade-4faa-8be1-f48f8d3ba3ea"),
            "root-volume=sbs:80GB:5000",
            "additional-volumes.0=" + weight["id"],
            "security-group-id=" + group["id"],
            "cloud-init=@" + init.name,
            "ip=new",
            "--wait",
        )
    address = str(
        ipaddress.IPv4Address(
            next(ip["address"] for ip in server["public_ips"] if ip["family"] == "inet")
        )
    )
    Path("BRAIN/gpu_ip.txt").write_text(address + "\n")
    Path("BRAIN/gateway.env").write_text(f"LOCAL_API_BASE=http://{address}:8000/v1\n")
    print("[gpu-up] cloud-init submitted; readiness checked by verify-m1", flush=True)


if __name__ == "__main__":
    for key in ("SCW_DEFAULT_PROJECT_ID", "SCW_DEFAULT_ZONE"):
        if not os.environ.get(key):
            raise RuntimeError(f"Missing {key}")
    with Path("BRAIN/gpu.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if sys.argv[1] == "up":
            if single(owned("instance", "server")) or STATE.exists():
                raise RuntimeError("Existing cycle: run gpu-down first")
            try:
                up()
            except (RuntimeError, ValueError, KeyError, subprocess.TimeoutExpired):
                down()
                raise
        elif sys.argv[1] == "down":
            down()
        else:
            project = "project-id=" + os.environ["SCW_DEFAULT_PROJECT_ID"]
            for kind in ("server", "ip"):
                resources = call("instance", kind, "list", project)
                print(json.dumps(resources))
