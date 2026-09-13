"""M13 input contract and minimal illicit-content filter."""

import re
from pydantic import Field, field_validator
from packages.images import Strict
from services.guardrails.input_filter import validate_input


class ImagePrompt(Strict):
    seed: int | None = Field(default=None, ge=0, le=2**32 - 1)
    prompt: str = Field(min_length=1, max_length=2000, pattern=r"\S")

    @field_validator("prompt")
    @classmethod
    def allowed(cls, value: str) -> str:
        validate_input(value)
        # PoC deliberately refuses all explicit sexual imagery, including minors.
        if re.search(
            r"(?i)\b(porn\w*|nud[ei]\w*|naked|sex\w*|nu[es]?|viol|rape|gore)\b", value
        ):
            raise ValueError("image_content_refused")
        return value


def image_request(text: str) -> bool:
    return bool(
        re.match(
            r"(?i)^\s*(?:génère|générer|genere|crée|cree|generate|create|draw)(?:[ -]moi)?\s+(?:(?:une?|an?|the)\s+)?(?:image|picture|illustration|photo)\b",
            text,
        )
    )
