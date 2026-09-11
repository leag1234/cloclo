"""Isolated real HTTP stack; external provider exchanges are recorded only here."""

import copy
import asyncio
import logging
import gzip
import json
import os
from contextlib import ExitStack
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any
from unittest.mock import patch
from uuid import UUID

from agent_provider import AgentProvider
from vision import VisionProvider
import imagegen
import stream_transport
from serverless_support import environment
from services.orchestrator.serving import stack
from services.orchestrator.tools import Runtime

ARCHIVE = Path("tests/cassettes/journeys.json.gz")


def main() -> None:
    logger = logging.getLogger("services.orchestrator.loop")
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.INFO)
    live = os.environ.get("JOURNEYS_LIVE") == "1"
    refresh = os.environ.get("JOURNEYS_REFRESH") == "1"
    previous = json.loads(gzip.decompress(ARCHIVE.read_bytes())) if not live else []
    saved_image = next((r for r in previous if r["kind"] == "image"), None)
    rows: list[dict[str, Any]] = [] if live or refresh else previous
    position = 0

    def recording() -> bool:
        return live or refresh

    def replay(kind: str, request: object) -> Any:
        nonlocal position
        row = rows[position]
        position += 1
        if row["kind"] != kind or row["request"] != request:
            raise AssertionError(f"unrecorded_journey_exchange:{position}:{kind}")
        return copy.deepcopy(row["response"])

    def record(kind: str, request: object, response: object) -> None:
        rows.append(
            copy.deepcopy({"kind": kind, "request": request, "response": response})
        )
        encoded = json.dumps(rows, ensure_ascii=False).encode()
        assert not any(
            value.encode() in encoded
            for key, value in os.environ.items()
            if len(value) >= 8
            and any(word in key for word in ("KEY", "SECRET", "TOKEN", "PASSWORD"))
        )
        ARCHIVE.write_bytes(gzip.compress(encoded, mtime=0))

    def wrap(cls: Any, name: str, kind: str) -> Any:
        original = getattr(cls, name)

        async def transport(self: Any, request: Any, *args: Any) -> Any:
            value = request.model_dump() if hasattr(request, "model_dump") else request
            if isinstance(value, dict):
                value = {k: v for k, v in value.items() if k != "timeout"}
            if not recording():
                result = replay(kind, value)
                if isinstance(result, dict) and result.get("recorded_timeout") is True:
                    raise TimeoutError
                return result
            try:
                result = await original(self, request, *args)
            except (TimeoutError, asyncio.CancelledError):
                record(kind, value, {"recorded_timeout": True})
                raise
            record(kind, value, result)
            return result

        return patch.object(cls, name, transport)

    original_stream = stream_transport.attempt

    async def stream(request: Any, model: str, timeout: float) -> Any:
        payload = request.model_dump(exclude={"timeout"})
        if not recording():
            for event in replay("stream", payload):
                yield event
            return
        events = []
        async for event in original_stream(request, model, timeout):
            events.append(event)
            if "result" in event:
                record("stream", payload, events)
            yield event

    original_image = imagegen.generate

    async def generate(request: Any) -> Any:
        if not recording():
            return replay("image", request)
        if refresh:
            assert saved_image and saved_image["request"] == request
            result = copy.deepcopy(saved_image["response"])
        else:
            result = await original_image(request)
        record("image", request, result)
        return result

    with tempfile.TemporaryDirectory() as directory, ExitStack() as contexts:
        contexts.enter_context(
            patch.dict(
                os.environ,
                {
                    **({} if live or refresh else environment()),
                    "GPU_LOCAL": "0",
                    "ATLAS_PROJECT_DB": directory + "/projects.sqlite",
                    "ATLAS_WEB_CACHE": directory + "/web.sqlite",
                    "ATLAS_INTERACTION_DIR": directory + "/interactions",
                },
            )
        )
        contexts.enter_context(
            patch(
                "services.retrieval.projects.uuid4",
                side_effect=(UUID(int=n) for n in range(1, 100)),
            )
        )
        for cls, name, kind in (
            (AgentProvider, "_complete", "complete"),
            (VisionProvider, "post", "vision"),
            (Runtime, "search", "search"),
            (Runtime, "fetch", "fetch"),
        ):
            contexts.enter_context(wrap(cls, name, kind))
        contexts.enter_context(patch.object(stream_transport, "attempt", stream))
        contexts.enter_context(patch.object(imagegen, "generate", generate))
        contexts.enter_context(stack("atlas-m17-test", False))
        completed = subprocess.run(
            [sys.executable, "tests/journeys/chat.py"], check=False
        )
        if completed.returncode:
            raise SystemExit(completed.returncode)
        if not live and not refresh and position != len(rows):
            raise AssertionError("unused_journey_exchanges")


if __name__ == "__main__":
    main()
