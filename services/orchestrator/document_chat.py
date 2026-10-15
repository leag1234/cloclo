"""Attachment-only generation, sharing the gateway's request and recovery ledger."""

import asyncio
from decimal import Decimal
import json
import os
from pathlib import Path
import time

from packages.evidence import estimated_tokens
from packages.language import language_instruction
from services.orchestrator.chat_schema import ChatRequest
from services.orchestrator.content import hierarchical_summary
from services.orchestrator.documents import DocumentError, extract_document
from services.orchestrator.interactions import Interaction
from services.orchestrator.model import GatewayError, GatewayModel
from services.orchestrator.stream_client import sink_context


async def process_documents(request: ChatRequest, item: Interaction) -> None:
    started = time.monotonic()
    item.task_type = "document"
    image_count = sum(len(message.images) for message in request.messages)
    if image_count:
        raise GatewayError(
            "mixed_attachment_types",
            400,
            f"This document request contains {image_count} photos; supported photo count with documents: 0. Send photos separately.",
        )
    sink = sink_context.get()
    if sink:
        await sink({"phase": "reading_document"})
    from services.orchestrator.attachment_reading import (
        document_status,
        failure_notice,
        reading_progress,
    )

    failures: list[dict[str, object]] = []
    sources: list[dict[str, object]] = []
    for attachment in request.documents:
        try:
            document = await asyncio.to_thread(extract_document, attachment)
        except DocumentError as exc:
            item.documents.append(
                {
                    "filename": attachment.filename,
                    "size": exc.size,
                    "encoded_characters": len(attachment.file_data),
                    "pages": exc.pages,
                    "extracted_characters": exc.characters,
                    "hierarchical_synthesis": False,
                    "error": str(exc),
                }
            )
            failures.append({"filename": attachment.filename, "errors": [str(exc)]})
            sources.append(
                {
                    "filename": attachment.filename,
                    "text": "",
                    "pages": exc.pages,
                    "errors": [str(exc)],
                }
            )
            continue
        if document.errors:
            failures.append(
                {"filename": document.filename, "errors": list(document.errors)}
            )
        sources.append(
            {
                "filename": document.filename,
                "text": document.text,
                "pages": document.pages,
                "errors": list(document.errors),
            }
        )
        item.documents.append(
            {
                "filename": document.filename,
                "size": document.size,
                "pages": document.pages,
                "extracted_characters": len(document.text),
                "hierarchical_synthesis": False,
                "error": "; ".join(document.errors),
            }
        )
    notice = failure_notice(failures, request.lang)
    pages, failed_pages = reading_progress(sources)
    if sink:
        await sink(
            {
                "phase": "document_read",
                "description": document_status(pages, failed_pages, request.lang),
            }
        )
    if not any(source["text"] for source in sources):
        item.reponse, item.state = notice, "done"
        if sink:
            await sink({"delta": {"content": notice}})
        return
    model = await GatewayModel.connect(
        os.environ.get("ATLAS_GATEWAY_URL", "http://127.0.0.1:8010"),
        local_enabled=False,
    )
    model.configure_quality(request.model, request.max_tokens, has_attachments=True)
    model.tools = []
    model.observing = True
    model.sink = sink
    instructions = (
        Path("prompts/chat.txt").read_text()
        + Path("prompts/documents.txt").read_text()
        # Failed extraction needs a model-visible language cue for the remaining
        # readable attachments. Successful legacy requests retain their cassette bytes.
        + (language_instruction(request.lang) if notice else "")
    )
    history: list[dict[str, object]] = [
        {"role": m.role, "content": m.text} for m in request.messages
    ]
    model_sources: list[dict[str, object]] = [
        {"filename": str(source["filename"]), "text": str(source["text"])}
        for source in sources
    ]
    messages: list[dict[str, object]] = [
        {"role": "system", "content": instructions},
        {
            "role": "user",
            "content": json.dumps(
                {"untrusted_attachments": model_sources}, ensure_ascii=False
            ),
        },
        *history,
    ]
    # Context estimation decides hierarchy only; it never authorizes spending.
    # The gateway independently reserves the conservative byte-based cost bound.
    measured = (
        estimated_tokens(
            json.dumps({"messages": messages, "tools": []}, ensure_ascii=False)
        )
        + 256
        + request.max_tokens
    )
    source_texts: list[str] = []
    for source in sources:
        text = source["text"]
        assert isinstance(text, str)
        source_texts.append(text)
    if measured > 262144 or sum(len(text.encode()) for text in source_texts) > 524288:
        if sink:
            await sink({"phase": "synthesizing_document"})
        for source, metadata in zip(model_sources, item.documents, strict=True):
            text = source["text"]
            assert isinstance(text, str)
            source["text"], _, _ = hierarchical_summary(text, request.messages[-1].text)
            metadata["hierarchical_synthesis"] = True
        messages[1]["content"] = json.dumps(
            {"hierarchical_attachment_evidence": model_sources}, ensure_ascii=False
        )
    if sink:
        await sink({"phase": "synthesizing_document"})
    item.cout_eur = 0.30
    try:
        if model.estimate(messages).cost > Decimal("0.30"):
            raise GatewayError(
                "cost_budget", 413, "Document request reservation exceeds 0.30 EUR"
            )
        result = await model.complete(
            messages, max(0, request.timeout_seconds - (time.monotonic() - started))
        )
        if result.calls or not result.text.strip():
            raise GatewayError(
                "invalid_document_answer",
                502,
                "The provider returned no complete document answer",
            )
        item.reponse, item.state = (
            result.text + ("\n\n" + notice if notice else ""),
            "done",
        )
        if notice and sink:
            await sink({"delta": {"content": "\n\n" + notice}})
        if any(metadata.get("hierarchical_synthesis") for metadata in item.documents):
            labels = json.loads(Path("prompts/activity-labels.json").read_text())
            synthesis_notice = (
                "\n\n" + labels.get(request.lang, labels["en"])["synthesized"]
            )
            item.reponse += synthesis_notice
            if sink:
                await sink({"delta": {"content": synthesis_notice}})
        item.cout_eur = float(model.spent)
    finally:
        item.tokens = {"in": model.input_tokens, "out": model.output_tokens}
        item.provider_model = model.provider_model
        item.latence_ms["generation"] = model.generation_ms
        if model.observations:
            item.modele_utilise = model.observations[-1].provider
            item.route_decision = model.observations[0].route
