"""M24 public API replay of real provider/tool exchanges and downloaded artifacts."""

from collections.abc import AsyncGenerator
import copy
from dataclasses import asdict
from decimal import Decimal
import gzip
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Any
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from gateway_cpu import CPUModels
from http_gateway import serve
from m24_artifacts import validate
from serverless_support import environment
from services.orchestrator.chat_api import app
from services.orchestrator.chat_pipeline import ChatTools
from services.orchestrator.documents import Attachment
from services.orchestrator.loop import Call, Message
from services.orchestrator.terminal_client import TerminalClient
import stream_transport


def substitute(value: Any, before: str, after: str) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False).replace(before, after))


def main() -> None:
    cases = json.loads(
        gzip.decompress(Path("tests/cassettes/m24.json.gz").read_bytes())
    )
    assert set(cases) == {f"J{number}" for number in range(42, 49)} | {
        "formats_read",
        "formats_write",
    }
    report: dict[str, Any] = {}
    with (
        tempfile.TemporaryDirectory() as root,
        patch.dict(
            os.environ,
            {
                **environment(),
                "GPU_LOCAL": "0",
                "ATLAS_TERMINAL_ENABLED": "1",
                "ATLAS_SEARCH_PROVIDER": "tavily",
                "ATLAS_WEB_CACHE": root + "/cache.sqlite",
                "ATLAS_INTERACTION_DIR": root + "/logs",
            },
        ),
    ):
        gateway = serve(CPUModels(), 0)
        worker = threading.Thread(target=gateway.serve_forever, daemon=True)
        worker.start()
        try:
            with patch.dict(
                os.environ,
                {"ATLAS_GATEWAY_URL": f"http://127.0.0.1:{gateway.server_port}"},
            ):
                for name in sorted(cases):
                    case = cases[name]
                    old_id = case["response"]["id"]
                    current_id = ""
                    streams = [
                        row
                        for row in case["exchanges"]
                        if row["request"].get("kind") != "tool"
                    ]
                    tools = [
                        row
                        for row in case["exchanges"]
                        if row["request"].get("kind") == "tool"
                    ]
                    stream_position = tool_position = 0
                    uploads: list[dict[str, Any]] = []
                    for message in case["request"]["messages"]:
                        if isinstance(message["content"], list):
                            uploads.extend(
                                part["file"]
                                for part in message["content"]
                                if part["type"] == "file"
                            )

                    async def initialize(client: TerminalClient) -> None:
                        nonlocal current_id
                        current_id = client.root.rsplit("/", 1)[-1]

                    async def upload(
                        client: TerminalClient, attachment: Attachment, timeout: float
                    ) -> str:
                        assert attachment.model_dump() in uploads, (
                            "unrecorded_attachment_bytes"
                        )
                        return client.root + "/" + attachment.filename

                    async def stream(
                        request: Any, model: str, timeout: float
                    ) -> AsyncGenerator[dict[str, object], None]:
                        nonlocal stream_position
                        row = streams[stream_position]
                        stream_position += 1
                        actual = {
                            **request.model_dump(exclude={"timeout"}),
                            "provider_model": model,
                        }
                        expected = substitute(row["request"], old_id, current_id)
                        assert actual == expected, (
                            f"unrecorded_m24_provider_request:{name}:{stream_position}"
                        )
                        # Latency is validated from the live request, not replay sleep.
                        # Recorded errors retain their type; no response is invented.
                        for event in substitute(row["response"], old_id, current_id):
                            if "error" in event:
                                if event["error"] == "timeout":
                                    raise TimeoutError("recorded_timeout")
                                raise RuntimeError("recorded_provider_error")
                            yield event["event"]

                    async def execute(
                        runtime: ChatTools, call: Call, timeout: float
                    ) -> Message:
                        nonlocal tool_position
                        row = tools[tool_position]
                        tool_position += 1
                        assert asdict(call) == substitute(
                            row["request"]["call"], old_id, current_id
                        ), "unrecorded_m24_tool_call"
                        recorded = substitute(row["response"], old_id, current_id)
                        assert runtime.terminal is not None
                        runtime.terminal.commands = recorded["commands"]
                        runtime.terminal.failed_commands = recorded["failed_commands"]
                        runtime.terminal.files = recorded["files"]
                        runtime.terminal.strategies = recorded["strategies"]
                        runtime.item.files = recorded["files"]
                        runtime.item.file_strategies = recorded["strategies"]
                        runtime.item.documents = recorded["documents"]
                        runtime.item.erreurs = recorded["errors"]
                        output: Message = recorded["output"]
                        return copy.deepcopy(output)

                    with (
                        patch.object(TerminalClient, "initialize", initialize),
                        patch.object(TerminalClient, "upload", upload),
                        patch.object(
                            TerminalClient,
                            "request",
                            AsyncMock(
                                side_effect=AssertionError("unexpected_terminal_io")
                            ),
                        ),
                        patch.object(ChatTools, "execute", execute),
                        patch.object(stream_transport, "attempt", stream),
                        TestClient(app) as client,
                    ):
                        response = client.post(
                            "/v1/chat/completions", json=case["request"]
                        )
                        assert response.status_code == 200, (
                            name,
                            response.status_code,
                            response.json(),
                        )
                        answer = response.json()
                    assert stream_position == len(streams) and tool_position == len(
                        tools
                    )
                    validate(name, case, answer)
                    assert Decimal(str(answer["atlas"]["cost_eur"])) == Decimal(
                        str(case["response"]["atlas"]["cost_eur"])
                    )
                    report[name] = True
                    print(name, "real exchanges replayed and useful content checked")
        finally:
            gateway.shutdown()
            gateway.server_close()
            worker.join(timeout=10)
    rendering = json.loads(Path("reports/m24-rendering.json").read_text())
    assert (
        rendering["css_sha256"]
        == hashlib.sha256(
            Path("services/orchestrator/chat-ui.css").read_bytes()
        ).hexdigest()
    )
    assert "serif" in rendering["font"] and rendering["gutters"] == "none"
    assert rendering["save"] == "none" and rendering["copy"] == "0"
    for filename, digest in rendering["screenshots"].items():
        assert (
            hashlib.sha256((Path("reports") / filename).read_bytes()).hexdigest()
            == digest
        )
    assert Path("reports/m24-activity-observed.png").is_file()
    activity = json.loads(Path("reports/m24-activity-document.json").read_text())
    assert activity[0]["seconds"] < 2 and activity[0]["text"] != activity[-1]["text"]
    generation = json.loads(Path("reports/m24-activity-generation.json").read_text())
    assert generation[0]["seconds"] < 2
    assert generation[0]["text"] != generation[-1]["text"]
    native = json.loads(Path("reports/m24-native-upload.json").read_text())
    from test_m23_documents import pdf

    assert native["mode"] == "live" and native["original_bytes_preserved"] is True
    assert native["sha256"] == hashlib.sha256(pdf()).hexdigest()
    assert native["bytes"] == len(pdf())
    names = {
        "J42": "J42_pptx_and_pdf",
        "J43": "J43_docx_fixed",
        "J44": "J44_xlsx_sheet_chart",
        "J45": "J45_long_pdf_synthesis",
        "J46": "J46_extraction_failure",
        "J47": "J47_large_attachment",
        "J48": "J48_cpc_search",
    }
    path = Path("BRAIN/eval/journeys.json")
    combined = json.loads(path.read_text()) if path.exists() else {}
    previous = json.loads(Path("BRAIN/eval/m23.json").read_text())
    for number in range(39, 42):
        assert previous[f"J{number}"] is True
        combined[f"J{number}_public_http"] = True
    combined.update({names.get(name, name): value for name, value in report.items()})
    measured = cases["J42"]["response"]
    combined.update(
        mode="replay",
        J49_rendering_proof=True,
        j42_model=measured["atlas"]["provider_model"],
        j42_commands=measured["atlas"]["terminal_commands"],
        j42_failed_commands=measured["atlas"]["terminal_failed_commands"],
        j42_seconds=measured["seconds"],
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(combined, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
