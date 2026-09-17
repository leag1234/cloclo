"""Run journeys once per unchanged CI input set; every verifier still checks them."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from collections.abc import Callable


REPORT = Path("BRAIN/eval/journeys.json")
CACHE = Path("BRAIN/eval/journeys-ci-cache.json")


def valid_report(report: object) -> bool:
    if not isinstance(report, dict) or report.get("mode") != "replay":
        return False
    numbers = set()
    for name, value in report.items():
        match = re.match(r"^J(\d+)_", name)
        if match and 1 <= int(match[1]) <= 33:
            if value is not True:
                return False
            numbers.add(int(match[1]))
    return numbers == set(range(1, 34))


def fingerprint(root: Path, run_id: str) -> str:
    paths = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        text=True,
    ).splitlines()
    digest = hashlib.sha256(run_id.encode())
    for name in sorted(set(paths)):
        path = root / name
        digest.update(name.encode() + b"\0")
        digest.update(path.read_bytes() if path.is_file() else b"deleted")
    return digest.hexdigest()


def run(root: Path, run_id: str | None, execute: Callable[[], None]) -> None:
    key = fingerprint(root, run_id) if run_id else None
    cache, target = root / CACHE, root / REPORT
    if key and cache.exists():
        try:
            saved = json.loads(cache.read_text())
        except (ValueError, OSError):
            saved = None
        if (
            isinstance(saved, dict)
            and saved.get("key") == key
            and valid_report(saved.get("report"))
        ):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(saved["report"], ensure_ascii=False, indent=2))
            print(
                "Reusing complete journey evidence for unchanged inputs in this CI run."
            )
            return
    cache.unlink(missing_ok=True)
    execute()
    report = json.loads(target.read_text())
    if run_id and not valid_report(report):
        raise RuntimeError("incomplete_ci_journey_evidence")
    if key and fingerprint(root, run_id or "") == key:
        cache.write_text(json.dumps({"key": key, "report": report}, ensure_ascii=False))


def main() -> None:
    acquisition = any(
        os.environ.get(name)
        for name in (
            "JOURNEYS_LIVE",
            "JOURNEYS_REFRESH",
            "JOURNEYS_RESUME",
            "M20_LIVE",
            "M20_REFRESH",
            "M20_RESUME",
            "M21_LIVE",
            "M21_RESUME",
        )
    )
    run_id = None
    if (
        os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("GITHUB_RUN_ID")
        and not acquisition
    ):
        environment = {
            key: value
            for key, value in os.environ.items()
            if key.startswith(("ATLAS_", "M20_", "M21_", "JOURNEYS_"))
            and not any(
                secret in key for secret in ("KEY", "TOKEN", "SECRET", "PASSWORD")
            )
        }
        run_id = json.dumps(
            [
                os.environ["GITHUB_RUN_ID"],
                os.environ.get("GITHUB_RUN_ATTEMPT"),
                sys.version,
                environment,
            ],
            sort_keys=True,
        )

    def execute() -> None:
        for script in ("journey_server", "m20_gate", "m21_gate"):
            subprocess.run([sys.executable, "tests/" + script + ".py"], check=True)

    run(Path.cwd(), run_id, execute)


if __name__ == "__main__":
    main()
