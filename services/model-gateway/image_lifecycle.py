"""Bounded image-worker startup reuses the disposable, trapped GPU launcher."""

import asyncio
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request

from packages.configuration import IMAGE_REQUIRED_ENV, require_env
from packages.limits import ProviderLimitError


def ready() -> bool:
    try:
        address = (
            os.environ.get("ATLAS_IMAGE_GPU_IP")
            or Path("BRAIN/gpu_ip.txt").read_text().strip()
        )
        ipaddress.IPv4Address(address)
        with urllib.request.urlopen(
            f"http://{address}:8000/health", timeout=1
        ) as response:
            return bool(response.status == 200)
    except (OSError, ValueError, urllib.error.URLError):
        return False


def start_worker() -> None:
    """Serialize startup; the launcher owns cleanup and its maximum lifetime."""
    require_env(IMAGE_REQUIRED_ENV)
    directory = Path("BRAIN")
    directory.mkdir(exist_ok=True)
    with (directory / "image-start.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if (directory / "gpu_ip.txt").exists():
            return  # A separately launched cycle is still starting; never replace it.
        state = directory / "image-start.json"
        if state.exists():
            previous = json.loads(state.read_text())
            try:
                pid = int(previous["pid"])
                os.kill(pid, 0)
                state_code = (
                    Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1].split()[0]
                )
                if state_code != "Z":
                    return
            except (ProcessLookupError, FileNotFoundError):
                pass
        # Startup is infrastructure work, separate from inference (contract M13).
        # Reserve the launcher's worst-case lifetime under the milestone ceiling.
        ledger = directory / "image-start-budget.json"
        reserved = (
            float(json.loads(ledger.read_text())["reserved_eur"])
            if ledger.exists()
            else 0.0
        )
        reservation = 2.0  # 1 h at the enforced 2 EUR/h maximum, rounded upwards.
        if reserved + reservation > 30:
            raise ProviderLimitError(
                "image_start_budget_exceeded",
                int((reserved + reservation) * 1000000),
                30000000,
                "microEUR",
            )
        ledger.write_text(json.dumps({"reserved_eur": reserved + reservation}))
        with (directory / "STATUS.md").open("a") as status:
            status.write(
                "\nImage worker on-demand launch: <=2 EUR/h, reserved 2 EUR within 30 EUR startup envelope; cleanup owned by infra/imagegen.sh.\n"
            )
        with (directory / "JOURNAL.md").open("a") as journal:
            journal.write(
                "\nRISK: on-demand image worker launch; <=2 EUR/h, trapped cleanup, reserved startup cost recorded.\n"
            )
        with (directory / "image-start.log").open("ab") as log:
            process = subprocess.Popen(
                [
                    "timeout",
                    "--signal=TERM",
                    "--kill-after=120",
                    "3300",
                    "bash",
                    "infra/imagegen.sh",
                    "serve",
                ],
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        state.write_text(json.dumps({"pid": process.pid, "started": time.time()}))


async def ensure_worker(timeout: float) -> None:
    if not 0 <= timeout <= 895:
        raise ProviderLimitError(
            "invalid_startup_timeout", int(timeout * 1000), 895000, "milliseconds"
        )
    if await asyncio.to_thread(ready):
        return
    await asyncio.to_thread(start_worker)
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        if await asyncio.to_thread(ready):
            return
        await asyncio.sleep(1)
    raise TimeoutError(
        f"image_worker_start_timeout: {timeout:.0f} seconds, limit {timeout:.0f} seconds"
    )
