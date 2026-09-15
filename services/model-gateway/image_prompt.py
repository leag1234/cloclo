"""Rewrite reservation shares the image request's existing cost ceiling."""

from decimal import Decimal
import json
from pathlib import Path

from agent_provider import AgentProvider
from serverless import ServerlessPolicy
from packages.imagegen import ImagePrompt


def messages(prompt: str, language: str = "") -> list[dict[str, object]]:
    return [
        {
            "role": "system",
            "content": Path("prompts/image-rewrite.txt").read_text()
            + "\n"
            + json.dumps({"source_language": language, "output_language": "en"}),
        },
        {"role": "user", "content": prompt},
    ]


def reservation(prompt: str, language: str = "") -> Decimal:
    return ServerlessPolicy().reserve(messages(prompt, language), []).reserved_eur


async def rewrite(prompt: str, timeout: float, language: str = "") -> str:
    result = await AgentProvider().complete(
        {
            "messages": messages(prompt, language),
            "tools": [],
            "local_enabled": False,
            "timeout": timeout,
        }
    )
    text = result.get("text")
    if not isinstance(text, str) or any(
        label not in text for label in ("Subjects:", "Attributes:", "Scene:", "Style:")
    ):
        raise ValueError("invalid_image_prompt")
    return ImagePrompt(prompt=text).prompt
