"""Fixed sandbox reader: bounded source extraction and M10 evidence selection."""

import base64
import io
import json
from pathlib import Path
import posixpath
import re
import zipfile
from xml.etree import ElementTree as ET

MAX_BYTES = 16 * 1024 * 1024
MAX_TEXT = 4 * 1024 * 1024
INLINE_BYTES = 7900
# Attached documents reach the model with about 30k tokens of context (owner decision 2026-10-15).
DOCUMENT_CONTEXT_BYTES = 120_000


def xml(archive: zipfile.ZipFile, name: str) -> ET.Element:
    return ET.fromstring(archive.read(name))


def tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def office_parts(raw: bytes, extension: str) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if sum(info.file_size for info in archive.infolist()) > MAX_BYTES * 4:
            raise ValueError("expanded_size_limit")
        if extension == ".docx":
            body = xml(archive, "word/document.xml")
            return [
                "".join(node.text or "" for node in part.iter() if tag(node) == "t")
                for part in body.iter()
                if tag(part) == "p"
            ]
        base = "xl" if extension == ".xlsx" else "ppt"
        main = "workbook" if extension == ".xlsx" else "presentation"
        relationships = {
            node.attrib["Id"]: posixpath.normpath(
                posixpath.join(base, node.attrib["Target"])
            ).lstrip("/")
            for node in xml(archive, f"{base}/_rels/{main}.xml.rels")
            if node.attrib.get("TargetMode") != "External"
        }
        ordered = [
            node
            for node in xml(archive, f"{base}/{main}.xml").iter()
            if tag(node) == ("sheet" if extension == ".xlsx" else "sldId")
        ]
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared = [
                "".join(n.text or "" for n in node.iter() if tag(n) == "t")
                for node in xml(archive, "xl/sharedStrings.xml")
            ]
        parts = []
        for index, entry in enumerate(ordered, 1):
            relation = next(v for k, v in entry.attrib.items() if k.endswith("}id"))
            part = xml(archive, relationships[relation])
            if extension == ".pptx":
                parts.append(
                    f"[Slide {index}]\n"
                    + "\n".join(n.text or "" for n in part.iter() if tag(n) == "t")
                )
                continue
            rows = []
            for row in part.iter():
                if tag(row) != "row":
                    continue
                cells = []
                for cell in row:
                    value = "".join(
                        n.text or "" for n in cell.iter() if tag(n) in {"v", "t"}
                    )
                    if cell.attrib.get("t") == "s" and value:
                        value = shared[int(value)]
                    formula = next((n.text for n in cell if tag(n) == "f"), None)
                    if formula:
                        value = (
                            "="
                            + formula
                            + (" (cached: " + value + ")" if value else "")
                        )
                    cells.append(cell.attrib.get("r", "") + ": " + value)
                rows.append("\t".join(cells))
            parts.append("[Sheet: " + entry.attrib["name"] + "]\n" + "\n".join(rows))
        return parts


def failure_reason(exc: Exception) -> str:
    # Third-party exception strings may include document bytes or sensitive paths.
    message = str(exc)
    if re.fullmatch(
        r"terminal_(?:http_[0-9]{3}|configuration_missing|unavailable|command_timeout|output_truncated)",
        message,
    ):
        return message + " (" + type(exc).__name__ + ")"
    reasons = {
        "FileNotFoundError": "File not found",
        "PermissionError": "File access denied",
        "UnicodeDecodeError": "Text is not valid UTF-8",
        "PdfReadError": "Document extraction failed: invalid PDF structure",
        "PdfStreamError": "Invalid PDF stream",
        "BadZipFile": "Invalid Office archive",
        "ParseError": "Invalid Office XML",
        "ModuleNotFoundError": "Required reader library is unavailable",
        "KeyError": "Required document structure is missing",
        "IndexError": "Invalid document reference",
        "StopIteration": "Required document relationship is missing",
    }
    return (
        reasons.get(type(exc).__name__, "Document extraction failed")
        + " ("
        + type(exc).__name__
        + ")"
    )


def extract_bytes(
    raw: bytes, extension: str, ocr_pages: dict[int, str] | None = None
) -> tuple[str, int, list[str]]:
    errors: list[str] = []
    pages = 0
    if not 0 < len(raw) <= MAX_BYTES:
        return "", pages, [f"Document bytes: {len(raw)}; allowed 1-{MAX_BYTES}"]
    parts: list[str] = []
    if extension == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(raw), strict=True)
        if reader.is_encrypted:
            return (
                "",
                pages,
                ["Password-protected PDF: provide an unencrypted document"],
            )
        pages = len(reader.pages)
        if pages > 1000:
            return "", pages, [f"Document pages: {pages}; limit 1000"]
        characters = 0
        for index, page in enumerate(reader.pages, 1):
            try:
                text = page.extract_text() or ""
            except Exception as exc:
                errors.append(f"Page {index}: " + failure_reason(exc))
                continue
            if not text.strip() and ocr_pages and ocr_pages.get(index, "").strip():
                text = ocr_pages[index]
            if not text.strip():
                errors.append(
                    f"PDF page {index}/{pages} has no text layer; OCR is required (not available)"
                )
                continue
            characters += len(text)
            if characters > MAX_TEXT:
                errors.append(
                    f"Extracted text limit {MAX_TEXT} characters reached at page {index}; remaining pages were not read"
                )
                break
            parts.append(f"[Page {index}]\n{text}")
    elif extension in {".docx", ".xlsx", ".pptx"}:
        parts = office_parts(raw, extension)
    elif extension in {".txt", ".md", ".csv"}:
        parts = [raw.decode("utf-8-sig")]
    else:
        errors.append(
            "Unsupported document type; allowed PDF, DOCX, XLSX, PPTX, TXT, MD, CSV"
        )
    text = "\n\n".join(parts)
    if len(text) > MAX_TEXT:
        text = text[:MAX_TEXT]
        errors.append(
            f"Extracted text limit {MAX_TEXT} characters reached; remaining text was not read"
        )
    if not text.strip() and not errors:
        errors.append("Document contains no readable text")
    return text, pages, errors


def read_attachment(path: Path, question: str) -> dict[str, object]:
    result: dict[str, object] = {
        "filename": path.name,
        "size": 0,
        "pages": 0,
        "text": "",
        "errors": [],
        "hierarchical_synthesis": False,
        "extracted_characters": 0,
    }
    try:
        with path.open("rb") as source:
            raw = source.read(MAX_BYTES + 1)
        result["size"] = len(raw)
        text, pages, errors = extract_bytes(raw, path.suffix.lower())
        result.update(pages=pages, errors=errors, extracted_characters=len(text))
        if len(text.encode()) > INLINE_BYTES:
            from services.orchestrator.content import hierarchical_summary

            text, _, sections = hierarchical_summary(text, question)
            result.update(hierarchical_synthesis=True, sections_examined=sections)
        result["text"] = text
    except Exception as exc:
        result["errors"] = [failure_reason(exc)]
    return result


def main(path: str, question: str) -> None:
    target = Path(path).resolve()
    root = Path.cwd().resolve()
    if (
        any(part.startswith(".") for part in target.parts)
        or not (target.is_relative_to(root) or target.is_relative_to("/home/user"))
        or (
            target.is_relative_to("/home/user/requests")
            and not target.is_relative_to(root)
        )
    ):
        result: dict[str, object] = {
            "filename": Path(path).name,
            "text": "",
            "errors": ["Attachment path is outside the permitted upload area"],
        }
    else:
        result = read_attachment(target, question)
    errors = result.get("errors")
    if isinstance(errors, list) and len(errors) > 8:
        result["errors"] = errors[:8] + [
            f"{len(errors) - 8} additional page extraction failures; those pages were not read"
        ]
    # Base64 bounds JSON expansion for arbitrary control characters in source text.
    result["text_base64"] = base64.b64encode(str(result.pop("text")).encode()).decode()
    print(json.dumps(result, ensure_ascii=False))


ODF_EXTENSIONS = {".odt", ".ods", ".odp"}


def odf_parts(raw: bytes, extension: str) -> list[str]:
    """Text of an OpenDocument file in document order: paragraphs, table rows, slides."""
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        expanded = sum(info.file_size for info in archive.infolist())
        if expanded > MAX_BYTES * 4:
            raise ValueError(
                f"Expanded document bytes: {expanded}; limit {MAX_BYTES * 4}"
            )
        root = ET.fromstring(archive.read("content.xml"))
    ns = {
        "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
        "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
        "draw": "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0",
    }

    def flat(node: ET.Element) -> str:
        return "".join(node.itertext()).strip()

    parts: list[str] = []
    if extension == ".ods":
        for sheet in root.iter("{%s}table" % ns["table"]):
            parts.append(f"[Sheet: {sheet.get('{%s}name' % ns['table'], '')}]")
            for row in sheet.iter("{%s}table-row" % ns["table"]):
                cells = [
                    flat(cell) for cell in row.iter("{%s}table-cell" % ns["table"])
                ]
                if any(cells):
                    parts.append(" | ".join(cells).rstrip(" |"))
    elif extension == ".odp":
        for index, page in enumerate(root.iter("{%s}page" % ns["draw"]), 1):
            parts.append(f"[Slide {index}]")
            for paragraph in page.iter():
                if paragraph.tag in (
                    "{%s}p" % ns["text"],
                    "{%s}h" % ns["text"],
                ) and flat(paragraph):
                    parts.append(flat(paragraph))
    else:
        for node in root.iter():
            if node.tag in ("{%s}p" % ns["text"], "{%s}h" % ns["text"]) and flat(node):
                parts.append(flat(node))
    return parts
