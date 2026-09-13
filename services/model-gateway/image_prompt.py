"""Rewrite reservation shares the image request's existing cost ceiling."""

from decimal import Decimal
from pathlib import Path

from agent_provider import AgentProvider
from serverless import ServerlessPolicy
from packages.imagegen import ImagePrompt


def messages(prompt: str) -> list[dict[str, object]]:
    return [
        {"role": "system", "content": Path("prompts/image-rewrite.txt").read_text()},
        {"role": "user", "content": prompt},
    ]


def reservation(prompt: str) -> Decimal:
    return ServerlessPolicy().reserve(messages(prompt), []).reserved_eur


async def rewrite(prompt: str, timeout: float) -> str:
    result = await AgentProvider().complete(
        {
            "messages": messages(prompt),
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
