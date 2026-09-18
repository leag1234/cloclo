"""Bounded extraction of complete attachments; no URL or corpus lookup."""

import base64
import binascii
from dataclasses import dataclass
import io
from pathlib import Path
import zipfile

from docx import Document
from pydantic import BaseModel, ConfigDict, Field
from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_BYTES = 16 * 1024 * 1024
MAX_TEXT = 4 * 1024 * 1024


class DocumentError(ValueError):
    def __init__(
        self, message: str, *, size: int = 0, pages: int = 0, characters: int = 0
    ) -> None:
        super().__init__(message)
        self.size, self.pages, self.characters = size, pages, characters


class Attachment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    filename: str = Field(min_length=1, max_length=255, pattern=r"^[^/\\\x00-\x1f]+$")
    file_data: str = Field(min_length=1, max_length=22370000, repr=False)


@dataclass(frozen=True)
class Extracted:
    filename: str
    size: int
    pages: int
    text: str


def extract_document(attachment: Attachment) -> Extracted:
    encoded = attachment.file_data
    if encoded.startswith("data:"):
        prefix, sep, encoded = encoded.partition(",")
        if not sep or not prefix.endswith(";base64"):
            raise DocumentError("Document must contain base64 bytes, not a URL")
    if len(encoded) > (MAX_BYTES + 2) // 3 * 4:
        raise DocumentError(
            f"Document encoded bytes: {len(encoded)}; limit {(MAX_BYTES + 2) // 3 * 4}"
        )
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise DocumentError("Document contains invalid base64 bytes") from None
    if not 0 < len(raw) <= MAX_BYTES:
        raise DocumentError(f"Document bytes: {len(raw)}; allowed 1–{MAX_BYTES}")
    extension = Path(attachment.filename).suffix.lower()
    pages = characters = 0
    try:
        if extension == ".pdf":
            reader = PdfReader(io.BytesIO(raw), strict=True)
            if reader.is_encrypted:
                raise DocumentError(
                    "Password-protected PDF: provide an unencrypted document"
                )
            pages = len(reader.pages)
            if pages > 1000:
                raise DocumentError(f"Document pages: {pages}; limit 1000")
            parts = []
            characters = 0
            for index, page in enumerate(reader.pages, 1):
                text = page.extract_text() or ""
                if not text.strip():
                    raise DocumentError(
                        f"PDF page {index}/{pages} has no text layer; OCR is required"
                    )
                characters += len(text)
                if characters > MAX_TEXT:
                    raise DocumentError(
                        f"Extracted characters: {characters}; limit {MAX_TEXT}"
                    )
                parts.append(f"[Page {index}]\n{text}")
            text = "\n\n".join(parts)
        elif extension == ".docx":
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                expanded = sum(info.file_size for info in archive.infolist())
                if expanded > MAX_BYTES * 4:
                    raise DocumentError(
                        f"Expanded document bytes: {expanded}; limit {MAX_BYTES * 4}"
                    )
            document = Document(io.BytesIO(raw))
            # Walk paragraphs and tables in document order, retaining all cell text.
            text = "\n".join(
                "".join(element.text or "" for element in node.xpath(".//w:t"))
                for node in document.element.body
                if node.tag.endswith(("}p", "}tbl"))
            )
        elif extension in {".txt", ".md", ".csv"}:
            text = raw.decode("utf-8-sig")
        else:
            raise DocumentError(
                "Unsupported document type; allowed PDF, DOCX, TXT, MD, CSV"
            )
    except DocumentError as exc:
        exc.size, exc.pages, exc.characters = len(raw), pages, characters
        raise
    except (ValueError, OSError, KeyError, zipfile.BadZipFile, PdfReadError):
        raise DocumentError(
            "Document extraction failed; provide a valid PDF, DOCX or UTF-8 text file",
            size=len(raw),
            pages=pages,
            characters=characters,
        ) from None
    if not text.strip():
        raise DocumentError(
            "Document contains 0 extracted characters; minimum 1 required",
            size=len(raw),
            pages=pages,
        )
    if len(text) > MAX_TEXT:
        raise DocumentError(f"Extracted characters: {len(text)}; limit {MAX_TEXT}")
    return Extracted(attachment.filename, len(raw), pages, text)
