"""Attachment-only generation, sharing the gateway's request and recovery ledger."""

import asyncio
from decimal import Decimal
import json
import os
from pathlib import Path
import time

from packages.evidence import estimated_tokens
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
    sources = []
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
            raise GatewayError(
                "document_extraction_failed", 422, attachment.filename + ": " + str(exc)
            ) from None
        sources.append({"filename": document.filename, "text": document.text})
        item.documents.append(
            {
                "filename": document.filename,
                "size": document.size,
                "pages": document.pages,
                "extracted_characters": len(document.text),
                "hierarchical_synthesis": False,
            }
        )
    model = await GatewayModel.connect(
        os.environ.get("ATLAS_GATEWAY_URL", "http://127.0.0.1:8010"),
        local_enabled=False,
    )
    model.configure_quality(request.model, request.max_tokens, has_attachments=True)
    model.tools = []
    model.observing = True
    model.sink = sink
    instructions = (
        Path("prompts/chat.txt").read_text() + Path("prompts/documents.txt").read_text()
    )
    history: list[dict[str, object]] = [
        {"role": m.role, "content": m.text} for m in request.messages
    ]
    messages: list[dict[str, object]] = [
        {"role": "system", "content": instructions},
        {
            "role": "user",
            "content": json.dumps(
                {"untrusted_attachments": sources}, ensure_ascii=False
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
    if measured > 262144:
        for source, metadata in zip(sources, item.documents, strict=True):
            source["text"], _, _ = hierarchical_summary(
                source["text"], request.messages[-1].text
            )
            metadata["hierarchical_synthesis"] = True
        messages[1]["content"] = json.dumps(
            {"hierarchical_attachment_evidence": sources}, ensure_ascii=False
        )
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
        item.reponse, item.state = result.text, "done"
        item.cout_eur = float(model.spent)
    except GatewayError:
        raise
    except (RuntimeError, ValueError) as exc:
        raise GatewayError(
            "document_generation_failed",
            502,
            f"Document generation failed: {measured} estimated input/output tokens; "
            f"context limit 262144 tokens, request cost limit 0.30 EUR, "
            f"elapsed {time.monotonic() - started:.1f}s of {request.timeout_seconds:.0f}s. "
            "The full attachment was extracted; no corpus retrieval was used.",
        ) from exc
    finally:
        item.tokens = {"in": model.input_tokens, "out": model.output_tokens}
        item.provider_model = model.provider_model
        item.latence_ms["generation"] = model.generation_ms
        if model.observations:
            item.modele_utilise = model.observations[-1].provider
            item.route_decision = model.observations[0].route
