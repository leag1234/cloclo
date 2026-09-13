"""OpenAI-compatible text/image chat; clients cannot alter tool budgets."""

from typing import Literal, Self
from uuid import UUID
from pydantic import ConfigDict, Field, model_validator
from packages.images import VisionInput, VisionMessage

ChatMessage = VisionMessage


class ChatRequest(VisionInput):
    model_config = ConfigDict(extra="ignore", strict=True)
    model: Literal["atlas"] = "atlas"
    project_id: str | None = None
    conversation_id: str | None = None
    stream: bool = False
    reasoning_effort: Literal["none", "low"] = "none"
    seed: int | None = Field(default=None, ge=0, le=2**32 - 1)
    ui_locale: Literal["fr", "de", "es", "it", "en"] = "fr"
    lang: Literal["fr", "de", "es", "it", "en"] = "fr"

    @model_validator(mode="after")
    def valid_project(self) -> Self:
        if (self.project_id is None) != (self.conversation_id is None):
            raise ValueError("project_conversation_required")
        if self.project_id is not None and self.conversation_id is not None:
            UUID(self.project_id)
            UUID(self.conversation_id)
        return self
