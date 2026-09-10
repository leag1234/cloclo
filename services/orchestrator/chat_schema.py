"""Text-only OpenAI-compatible chat input; clients cannot alter tool budgets."""

from typing import Literal, Self
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from services.guardrails.input_filter import validate_input


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=32000, pattern=r"\S")
    _safe_content = field_validator("content")(validate_input)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    model: Literal["atlas"] = "atlas"
    messages: list[ChatMessage] = Field(min_length=1, max_length=100)
    stream: bool = False
    lang: Literal["fr", "de", "es", "it", "en"] = "fr"

    @model_validator(mode="after")
    def valid_history(self) -> Self:
        if self.messages[-1].role != "user":
            raise ValueError("last_message_must_be_user")
        if sum(len(m.content) for m in self.messages) > 32000:
            raise ValueError("context_exceeded")
        return self
