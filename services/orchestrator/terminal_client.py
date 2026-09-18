"""Authenticated calls to the contained user-file service, never to arbitrary URLs."""

import asyncio
import base64
import json
import os
from pathlib import PurePosixPath
from typing import Literal
from urllib.parse import quote

import aiohttp
from pydantic import BaseModel, ConfigDict, Field

from services.orchestrator.documents import Attachment, MAX_BYTES


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    command: str = Field(min_length=1, max_length=15000)


class Publish(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    path: str = Field(min_length=1, max_length=1000)
    strategy: Literal["created", "regenerated", "edited_in_place"]


def safe_result(value: dict[str, object]) -> dict[str, object]:
    key = os.environ.get("OPEN_TERMINAL_API_KEY", "")

    def scrub(item: object) -> object:
        if isinstance(item, str):
            return item.replace(key, "[REDACTED]") if key else item
        if isinstance(item, list):
            return [scrub(part) for part in item]
        if isinstance(item, dict):
            return {name: scrub(part) for name, part in item.items()}
        return item

    return {name: scrub(part) for name, part in value.items()}


def output_path(root: str, path: str) -> str:
    target = PurePosixPath(path)
    if (
        not target.is_relative_to(root)
        or ".." in target.parts
        or any(part.startswith(".") for part in target.parts)
        or target.suffix.lower()
        not in {".docx", ".xlsx", ".pptx", ".pdf", ".csv", ".md", ".png"}
    ):
        raise ValueError("output_must_be_document_in_request_directory")
    return str(target)


class TerminalClient:
    def __init__(self, request_id: str) -> None:
        if not request_id.replace("-", "").isalnum():
            raise ValueError("invalid_request_id")
        if os.environ.get("ATLAS_TERMINAL_ENABLED") != "1":
            raise RuntimeError("terminal_unavailable")
        self.root = "/home/user/requests/" + request_id
        self.commands = 0
        self.failed_commands = 0
        self.files: list[str] = []
        self.strategies: list[str] = []

    async def request(
        self,
        method: str,
        path: str,
        timeout: float,
        *,
        payload: object = None,
        params: dict[str, str] | None = None,
        data: aiohttp.FormData | None = None,
    ) -> dict[str, object]:
        key = os.environ.get("OPEN_TERMINAL_API_KEY", "")
        if not key:
            raise RuntimeError("terminal_configuration_missing")
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=max(0.1, timeout)),
            trust_env=False,
            headers={"Authorization": "Bearer " + key},
        ) as client:
            async with client.request(
                method,
                "http://127.0.0.1:8000" + path,
                json=payload,
                data=data,
                params=params,
                allow_redirects=False,
            ) as response:
                if response.status != 200:
                    raise RuntimeError("terminal_http_" + str(response.status))
                raw = bytearray()
                async for part in response.content.iter_chunked(16384):
                    raw.extend(part)
                    if len(raw) > 8 * 1024 * 1024:
                        raise ValueError("terminal_response_exceeds_8388608_bytes")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("invalid_terminal_response")
        return safe_result(value)

    async def upload(self, attachment: Attachment, timeout: float) -> str:
        encoded = attachment.file_data
        if encoded.startswith("data:"):
            header, _, encoded = encoded.partition(",")
            if not header.endswith(";base64"):
                raise ValueError("invalid_attachment_encoding")
        raw = base64.b64decode(encoded, validate=True)
        if not 0 < len(raw) <= MAX_BYTES:
            raise ValueError(f"Attachment bytes {len(raw)}; limit {MAX_BYTES}")
        data = aiohttp.FormData()
        data.add_field(
            "file",
            raw,
            filename=attachment.filename,
            content_type="application/octet-stream",
        )
        result = await self.request(
            "POST", "/files/upload", timeout, params={"directory": self.root}, data=data
        )
        expected = self.root + "/" + attachment.filename
        if result.get("path") != expected or result.get("size") != len(raw):
            raise ValueError("terminal_upload_integrity_failed")
        return expected

    async def initialize(self) -> None:
        await self.request(
            "POST",
            "/files/write",
            5,
            payload={"path": self.root + "/.request", "content": "ATLAS user files"},
        )

    async def publish(
        self, path: str, strategy: str, timeout: float
    ) -> dict[str, object]:
        target = output_path(self.root, path)
        # Reject symlinks before publication; Docker remains the security boundary.
        import shlex

        code = (
            "from pathlib import Path; p=Path("
            + repr(target)
            + "); assert p.is_file() and not p.is_symlink() and p.stat().st_size > 0; print(p.stat().st_size)"
        )
        result = await self.execute("python3 -c " + shlex.quote(code), timeout)
        if result.get("exit_code") != 0:
            return {"error": "output_file_missing_or_invalid"}
        url = "/api/v1/terminals/atlas-files/files/serve/" + quote(
            target.lstrip("/"), safe="/"
        )
        self.files.append(url)
        self.strategies.append(strategy)
        return {
            "download_url": url,
            "filename": PurePosixPath(target).name,
            "strategy": strategy,
        }

    async def execute(self, command: str, timeout: float) -> dict[str, object]:
        self.commands += 1
        result = await self.request(
            "POST",
            "/execute",
            timeout,
            payload={"command": command, "cwd": self.root},
            params={"wait": str(min(timeout, 30))},
        )
        process = result.get("id")
        if result.get("status") != "done":
            if isinstance(process, str):
                await asyncio.shield(
                    self.request(
                        "DELETE",
                        "/execute/" + quote(process, safe=""),
                        5,
                        params={"force": "true"},
                    )
                )
            self.failed_commands += 1
            return {
                "error": "terminal_command_timeout",
                "limit_seconds": min(timeout, 30),
            }
        if result.get("exit_code") != 0:
            self.failed_commands += 1
        if result.get("truncated"):
            return {
                "error": "terminal_output_truncated",
                "detail": "The terminal discarded output. Read the complete document in bounded sections; do not summarize these fragments as the whole.",
            }
        return {
            k: result[k]
            for k in ("status", "exit_code", "output", "truncated")
            if k in result
        }
