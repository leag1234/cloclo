"""Useful-content assertions on real authenticated M24 download recordings."""

import base64
import io
import re
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from docx import Document
from pypdf import PdfReader
from PIL import Image
from packages.evidence import estimated_tokens
from services.orchestrator.documents import Attachment, extract_document


def validate(name: str, case: dict[str, Any], answer: dict[str, Any]) -> None:
    text = answer["choices"][0]["message"]["content"]
    tools = [
        row["request"]["call"]["name"]
        for row in case["exchanges"]
        if row["request"].get("kind") == "tool"
    ]
    assert "rag_search" not in tools, "documents_must_not_query_corpus"
    assert len(tools) <= 10
    assert case["response"]["seconds"] <= 120
    attached = any(
        isinstance(m["content"], list)
        and any(p["type"] == "file" for p in m["content"])
        for m in case["request"]["messages"]
    )
    assert 0 < answer["atlas"]["cost_eur"] <= (0.30 if attached else 0.10)
    artifacts = {
        artifact["url"].rsplit(".", 1)[-1]: base64.b64decode(
            artifact["bytes"], validate=True
        )
        for artifact in case["artifacts"]
    }
    for artifact in case["artifacts"]:
        assert artifact["status"] == 200
        # IDs are substituted during replay; the filename and authenticated route remain.
        filename = artifact["url"].rsplit("/", 1)[-1]
        assert filename in text and "/api/v1/terminals/atlas-files/files/serve/" in text
    if name == "J42":
        assert set(artifacts) == {"pptx", "pdf"}
        with ZipFile(io.BytesIO(artifacts["pptx"])) as archive:
            slides = [
                n
                for n in archive.namelist()
                if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)
            ]
            assert len(slides) >= 4
            contents = [
                " ".join(ET.fromstring(archive.read(n)).itertext()) for n in slides
            ]
            assert len(set(contents)) >= 4 and all(
                content.strip() for content in contents
            )
            assert "murena" in " ".join(contents).lower()
        pdf = PdfReader(io.BytesIO(artifacts["pdf"]))
        assert len(pdf.pages) == len(slides)
        assert "murena" in " ".join(page.extract_text() for page in pdf.pages).lower()
    elif name == "J43":
        document = Document(io.BytesIO(artifacts["docx"]))
        paragraphs = " ".join(p.text for p in document.paragraphs)
        assert "employés travaillent" in paragraphs and "outils adaptés" in paragraphs
        assert (
            "avons terminé" in paragraphs
            and "résultats sont satisfaisants" in paragraphs
        )
        assert (
            sum(
                p.style is not None and p.style.name.startswith("Heading")
                for p in document.paragraphs
            )
            >= 2
        )
        with ZipFile(io.BytesIO(artifacts["docx"])) as archive:
            assert b"TOC" in archive.read("word/document.xml")
        assert re.search(r"régénéré|regenerated|en place|in place", text, re.I)
    elif name == "J44":
        parts = case["request"]["messages"][0]["content"]
        original = base64.b64decode(
            next(p["file"]["file_data"] for p in parts if p["type"] == "file")
        )
        with (
            ZipFile(io.BytesIO(artifacts["xlsx"])) as archive,
            ZipFile(io.BytesIO(original)) as before,
        ):
            assert archive.read("xl/worksheets/sheet1.xml") == before.read(
                "xl/worksheets/sheet1.xml"
            ), "original_sheet_changed"
            charts = [
                n
                for n in archive.namelist()
                if re.fullmatch(r"xl/charts/chart\d+\.xml", n)
            ]
            assert charts and "Comparaison" in archive.read(charts[0]).decode()
            sheet = ET.fromstring(archive.read("xl/worksheets/sheet2.xml"))
            ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            rows = [
                ["".join(c.itertext()) for c in row.findall("s:c", ns)]
                for row in sheet.findall(".//s:row", ns)
            ]
            total = next(row for row in rows if "Total" in row)
            assert "200" in total and "260" in total and "60" in total, (
                "incorrect_march_totals"
            )
    elif name in {"J45", "J47"}:
        assert "730" in text and "19" in text
        assert re.search(r"report|postpon", text, re.I)
        if name == "J45":
            assert "note.txt" in text and "60" in text
        else:
            parts = case["request"]["messages"][0]["content"]
            attachment = next(p["file"] for p in parts if p["type"] == "file")
            extracted = extract_document(Attachment.model_validate(attachment))
            assert estimated_tokens(extracted.text) >= 175000
            assert str(extracted.pages) in text
    elif name == "J46":
        assert re.search(r"mot de passe|password|chiffr", text, re.I)
        assert re.search(r"ne peux pas|impossible|cannot|illisible", text, re.I)
    elif name == "J48":
        assert "web_search" in tools and "web_fetch" not in tools
        assert re.search(r"https?://[^\s)]*(?:cpcwiki|cpctech)[^\s)]*", text, re.I), (
            "missing_cpc_citation"
        )
        assert re.search(r"consult|2026-09-18", text, re.I)
        # Measured CPC timings: https://www.cpctech.cpcwiki.de/docs/instrtim.html
        assert re.search(r"OUTI[^\n]{0,100}\b5\s*(?:[µμu]s|microsecond)", text, re.I)
        assert re.search(r"OTIR[^\n]{0,120}\b6\s*(?:[µμu]s|microsecond)", text, re.I)
    elif name == "formats_read":
        for filename, count in {
            "lettre.odt": 37,
            "inventaire.ods": 43,
            "diapos.odp": 59,
            "diapos.pptx": 59,
            "stock.csv": 61,
            "notes.md": 71,
            "note.txt": 83,
        }.items():
            assert re.search(
                re.escape(filename) + r"[^\n]*\b" + str(count) + r"\b", text
            ), "missing_format_content"
        assert "Inventaire" in text and "Quantit" in text
    elif name == "formats_write":
        assert set(artifacts) == {"csv", "md", "png"}
        for extension in ("csv", "md"):
            content = artifacts[extension].decode("utf-8-sig")
            assert all(str(number) in content for number in (10, 15, 25))
        with Image.open(io.BytesIO(artifacts["png"])) as graph:
            assert graph.format == "PNG" and graph.width >= 320 and graph.height >= 200
            assert len(set(graph.convert("RGB").getdata())) > 100
    else:
        raise AssertionError("unknown_m24_journey")
