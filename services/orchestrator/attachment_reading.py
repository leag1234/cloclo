"""Read announced sandbox files before generation using fixed repository code."""

import asyncio
import base64
from functools import lru_cache
from html.parser import HTMLParser
import io
import json
from pathlib import Path, PurePosixPath
import re
import shlex
import time
import zipfile

from services.orchestrator.chat_schema import ChatRequest
from services.orchestrator.interactions import Interaction
from services.orchestrator.terminal_client import TerminalClient


class FileTags(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.paths: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        path = attributes.get("url") or attributes.get("path")
        if tag == "file" and attributes.get("type") == "filesystem" and path:
            if path not in self.paths:
                self.paths.append(path)


def announced_paths(request: ChatRequest) -> list[str]:
    parser = FileTags()
    for message in request.messages:
        if message.role == "user":
            for block in re.findall(
                r"<attached_files>(.*?)</attached_files>", message.text, re.S
            ):
                parser.feed(block)
    return parser.paths


@lru_cache(maxsize=1)
def reader_archive() -> str:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for package in ("packages", "services", "services/orchestrator"):
            archive.writestr(package + "/__init__.py", "")
        for name in (
            "packages/attachment_reader.py",
            "packages/evidence.py",
            "services/orchestrator/content.py",
        ):
            archive.writestr(name, Path(name).read_bytes())
    return base64.b64encode(buffer.getvalue()).decode()


def reader_command(path: str, question: str) -> str:
    # Only fixed code executes; filenames and the question are Python string data.
    code = (
        "import base64,sys,tempfile; from pathlib import Path; "
        "temp=tempfile.TemporaryDirectory(dir='.'); "
        "bundle=Path(temp.name)/'reader.zip'; "
        f"bundle.write_bytes(base64.b64decode({reader_archive()!r})); "
        "sys.path.insert(0,str(bundle)); "
        "from packages.attachment_reader import main; "
        f"main({path!r},{question!r}); temp.cleanup()"
    )
    return "python3 -c " + shlex.quote(code)


def decode_output(output: dict[str, object]) -> dict[str, object]:
    if output.get("error") or output.get("exit_code") != 0:
        return {
            "text": "",
            "errors": [str(output.get("error", "Attachment reader process failed"))],
        }
    chunks = output.get("output")
    if not isinstance(chunks, list):
        raise ValueError("invalid_attachment_reader_output")
    encoded = "".join(
        str(part.get("data", ""))
        for part in chunks
        if isinstance(part, dict) and part.get("type") == "output"
    )
    result = json.loads(encoded)
    if not isinstance(result, dict) or not isinstance(result.get("errors"), list):
        raise ValueError("invalid_attachment_reader_output")
    result["text"] = base64.b64decode(result.pop("text_base64"), validate=True).decode()
    return result


async def read_announced(
    request: ChatRequest,
    item: Interaction,
    terminal: TerminalClient | None,
    terminal_error: str = "",
    read_document_bytes: bool = False,
) -> list[dict[str, object]]:
    from packages.file_intent import requests_file_delivery
    from packages.language import user_prose

    from packages.attachment_reader import INLINE_BYTES
    from services.orchestrator.content import hierarchical_summary
    from services.orchestrator.documents import DocumentError, extract_document

    sources: list[dict[str, object]] = []
    if read_document_bytes:
        for attachment in request.documents:
            source: dict[str, object] = {
                "filename": attachment.filename,
                "text": "",
                "errors": [],
            }
            try:
                document = await asyncio.to_thread(extract_document, attachment)
                text = document.text
                hierarchical = len(text.encode()) > INLINE_BYTES
                if hierarchical:
                    text, _, _ = hierarchical_summary(
                        text, user_prose(request.messages[-1].text)
                    )
                source.update(
                    text=text,
                    errors=list(document.errors),
                    pages=document.pages,
                    size=document.size,
                    extracted_characters=len(document.text),
                    hierarchical_synthesis=hierarchical,
                )
            except DocumentError as exc:
                source["errors"] = [str(exc)]
            sources.append(source)
            record_source(item, source)
    deadline = time.monotonic() + request.timeout_seconds
    paths = announced_paths(request)
    for index, path in enumerate(paths):
        announced_source: dict[str, object] = {
            "filename": PurePosixPath(path).name,
            "text": "",
            "errors": [],
        }
        if index + len(request.documents) >= 8:
            announced_source["errors"] = [
                "Attachment count exceeds the limit of 8; file was not read"
            ]
        elif terminal is None:
            announced_source["errors"] = [
                terminal_error or "Attachment sandbox is unavailable"
            ]
        elif not PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts:
            announced_source["errors"] = ["Invalid attachment path"]
        else:
            try:
                announced_source.update(
                    decode_output(
                        await terminal.execute(
                            reader_command(path, user_prose(request.messages[-1].text)),
                            max(0.1, deadline - time.monotonic()),
                        )
                    )
                )
            except (ValueError, RuntimeError, OSError) as exc:
                from packages.attachment_reader import failure_reason

                announced_source["errors"] = [failure_reason(exc)]
        sources.append(announced_source)
        record_source(item, announced_source)
    if sources and not requests_file_delivery(request.messages[-1].text):
        item.task_type = "document"
    return sources


def record_source(item: Interaction, source: dict[str, object]) -> None:
    item.documents.append(
        {
            **{
                k: v
                for k, v in source.items()
                if k != "text" and isinstance(v, (str, int, bool))
            },
            "error": error_text(source),
        }
    )


def error_text(source: dict[str, object]) -> str:
    errors = source.get("errors")
    return "; ".join(str(e) for e in errors) if isinstance(errors, list) else ""


def failure_notice(sources: list[dict[str, object]], lang: str) -> str:
    labels = json.loads(Path("packages/attachment-messages.json").read_text())
    return "\n\n".join(
        labels.get(lang, labels["en"]).format(
            filename=source["filename"],
            reason=error_text(source),
        )
        for source in sources
        if source.get("errors")
    )
