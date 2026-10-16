"""Validated, deterministic PPTX delivery; the model never writes executable code."""

import asyncio
from decimal import Decimal
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import time

from pydantic import ValidationError

from packages.doc_render import PresentationOutline, render, verify
from services.orchestrator.chat_schema import ChatRequest
from services.orchestrator.interactions import Interaction
from services.orchestrator.loop import Message, Result
from services.orchestrator.model import GatewayError, GatewayModel
from services.orchestrator.terminal_client import TerminalClient


OUTLINE_INSTRUCTION = """
For this PPTX request, return ONLY a JSON object with this exact shape:
{"title":"...","slides":[{"title":"...","bullets":["..."],"notes":"...","table":{"headers":["..."],"rows":[["..."]]}]}
`notes` and `table` are optional. Include no Markdown, code, tool calls, file claims,
or extra keys. Write all user-visible text in the request language.
"""


def requested_topic_words(question: str) -> set[str]:
    ignored = {
        "about",
        "avec",
        "create",
        "cree",
        "crée",
        "dans",
        "downloadable",
        "faire",
        "fais",
        "from",
        "make",
        "pdf",
        "presentation",
        "présentation",
        "pptx",
        "slides",
        "sur",
        "the",
        "une",
        "with",
    }
    return {
        word.casefold()
        for word in re.findall(r"[\w/]+", question, flags=re.UNICODE)
        if len(word) >= 3 and word.casefold() not in ignored
    }


def outline_markdown(text: str) -> str:
    """Readable fallback for an outline that could not become a file (D4)."""
    try:
        data = json.loads(text)
    except ValueError:
        return text
    if not isinstance(data, dict) or not isinstance(data.get("slides"), list):
        return text
    lines = ["# " + str(data.get("title", "")).strip()]
    for slide in data["slides"]:
        if not isinstance(slide, dict):
            continue
        lines += ["", "## " + str(slide.get("title", "")).strip()]
        lines += ["- " + str(b).strip() for b in slide.get("bullets", []) or []]
    return "\n".join(lines).strip()


def parse_outline(text: str, question: str) -> PresentationOutline:
    """Validate untrusted model JSON and require the requested subject in the deck."""
    data = json.loads(text)
    outline = PresentationOutline.model_validate(data)
    deck_text = " ".join(outline.content().texts()).casefold()
    # Requests carry filler words (pronouns, "downloadable"); the deck only has
    # to be about the subject, so one requested topic word is enough.
    words = requested_topic_words(question)
    if words and not any(word in deck_text for word in words):
        raise ValueError("requested_topic_words_missing:" + ",".join(sorted(words)))
    return outline


async def repair_outline(
    model: GatewayModel,
    request: ChatRequest,
    result: Result,
    reason: str,
    started: float,
) -> Result | None:
    """Exactly one bounded answer-only repair call for invalid structured output."""
    remaining = request.timeout_seconds - (time.monotonic() - started) - 30
    available = max(Decimal(0), Decimal("0.30") - result.cost)
    if remaining <= 0 or available <= 0:
        return None
    saved_tools, saved_choice, saved_sink = (
        model.tools,
        model.required_file_tool,
        model.sink,
    )
    model.tools, model.required_file_tool, model.sink = [], None, None
    try:
        model.spent = max(model.spent, result.cost)
        model.delivery_reserve = Decimal(0)
        messages: list[Message] = [
            {"role": "user", "content": request.messages[-1].text},
            {"role": "assistant", "content": result.text},
            {
                "role": "system",
                "content": OUTLINE_INSTRUCTION
                + "\nYour prior output was invalid ("
                + reason
                + "). Replace it with valid JSON only.",
            },
        ]
        async with asyncio.timeout(remaining):
            turn = await model.complete(messages, remaining)
        cost = turn.usage.cost if turn.usage else available
        return Result(
            text=turn.text,
            state="done",
            cost=result.cost + cost,
            tool_calls=result.tool_calls,
        )
    except (GatewayError, RuntimeError, TimeoutError):
        return None
    finally:
        model.tools, model.required_file_tool, model.sink = (
            saved_tools,
            saved_choice,
            saved_sink,
        )
        model.delivery_reserve = Decimal(0)


async def deliver_presentation(
    model: GatewayModel,
    request: ChatRequest,
    item: Interaction,
    result: Result,
    terminal: TerminalClient,
    started: float,
    formats: tuple[str, ...],
) -> Result | None:
    """Build, reopen, check and publish a PPTX; return None for D5 inline fallback."""
    try:
        outline = parse_outline(result.text, request.messages[-1].text)
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        repaired = await repair_outline(
            model, request, result, type(exc).__name__, started
        )
        if repaired is None:
            item.erreurs.append("presentation_outline_invalid")
            return None
        try:
            outline = parse_outline(repaired.text, request.messages[-1].text)
            result = repaired
        except (json.JSONDecodeError, ValidationError, ValueError):
            # The failed repair was still a provider call and must reach the ledger.
            result.cost = repaired.cost
            item.erreurs.append("presentation_outline_invalid_after_repair")
            return None
    remaining = request.timeout_seconds - (time.monotonic() - started)
    if remaining <= 0:
        item.erreurs.append("presentation_render_timeout")
        return None
    try:
        with TemporaryDirectory(prefix="atlas-pptx-") as directory:
            content = outline.content()
            for suffix in ("pptx", "pdf"):
                if suffix not in formats:
                    continue
                path = Path(directory) / ("presentation." + suffix)
                render(content, path, image_root=Path(directory))
                verified = verify(
                    path,
                    expected=content,
                    expected_count=len(outline.slides),
                    require_pagination=True,
                )
                if verified.count != len(outline.slides) or any(
                    not slide.strip() for slide in verified.text
                ):
                    raise ValueError("presentation_verification_failed")
                uploaded = await terminal.upload_generated(
                    path.name, path.read_bytes(), min(30, remaining)
                )
                published = await terminal.publish(
                    uploaded, "created", min(30, remaining)
                )
                if "error" in published:
                    raise ValueError("presentation_publish_failed")
    except (OSError, ValueError, TimeoutError):
        item.erreurs.append("presentation_build_or_publish_failed")
        return None
    return result
