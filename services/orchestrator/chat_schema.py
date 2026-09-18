"""OpenAI-compatible text/image chat; clients cannot alter tool budgets."""

from packages.profiles import PROFILES

from typing import Literal, Self
from uuid import UUID
from pydantic import ConfigDict, Field, model_validator
from packages.images import VisionInput, VisionMessage

from services.orchestrator.documents import Attachment

ChatMessage = VisionMessage


class ChatRequest(VisionInput):
    model_config = ConfigDict(extra="ignore", strict=True)
    model: str = PROFILES[0]
    documents: list[Attachment] = Field(default_factory=list, max_length=8)
    project_id: str | None = None
    conversation_id: str | None = None
    stream: bool = False
    reasoning_effort: Literal["none", "low", "high"] = "none"
    max_tokens: int = Field(default=3000, ge=1, le=16000)
    seed: int | None = Field(default=None, ge=0, le=2**32 - 1)
    ui_locale: Literal["fr", "de", "es", "it", "en"] = "fr"
    lang: Literal["fr", "de", "es", "it", "en"] = "fr"

    @property
    def timeout_seconds(self) -> float:
        return 120.0

    @model_validator(mode="after")
    def valid_project(self) -> Self:
        if self.model not in PROFILES:
            raise ValueError("invalid_profile")
        maximum = 3000
        if "max_tokens" not in self.model_fields_set:
            self.max_tokens = maximum
        if self.max_tokens > maximum:
            raise ValueError("output_budget")
        self.reasoning_effort = "none"
        if (self.project_id is None) != (self.conversation_id is None):
            raise ValueError("project_conversation_required")
        if self.project_id is not None and self.conversation_id is not None:
            UUID(self.project_id)
            UUID(self.conversation_id)
        return self
