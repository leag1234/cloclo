"""Model-selected generation finishes on the same request ledger and deadline."""

from decimal import Decimal
from pathlib import Path
from time import monotonic

from pydantic import BaseModel, ConfigDict, Field, field_validator
from packages.imagegen import ImagePrompt
from services.orchestrator.chat_schema import ChatRequest
from services.orchestrator.followup import image_iteration
from services.orchestrator.imagegen import process_image
from services.orchestrator.interactions import Interaction
from services.orchestrator.loop import Message, Result
from services.orchestrator.stream_client import sink_context


class GenerateImage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    prompt: str = Field(min_length=1, max_length=2000, pattern=r"\S")

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        return ImagePrompt(prompt=value).prompt


def declaration() -> Message:
    return {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": Path("prompts/image-tool.txt").read_text(),
            "parameters": GenerateImage.model_json_schema(),
        },
    }


async def finish(
    request: ChatRequest, item: Interaction, result: Result, prompt: str, started: float
) -> None:
    # Selection is model-owned; the original request is user-owned. A model
    # paraphrase must not silently discard constraints before the image rewriter.
    iteration = image_iteration(request.messages)
    prompt = (
        " ".join(iteration.splitlines()) if iteration else request.messages[-1].text
    )
    try:
        await process_image(
            prompt,
            item,
            request.seed,
            language=request.lang,
            budget=max(
                Decimal(0),
                min(
                    Decimal("0.05"),
                    Decimal("0.30") - result.cost,
                ),
            ),
            timeout=max(0, min(120, request.timeout_seconds - (monotonic() - started))),
        )
        sink = sink_context.get()
        if sink:
            await sink({"phase": "tool_finished", "tool": "generate_image", "ok": True})
    finally:
        item.cout_eur += float(result.cost)
