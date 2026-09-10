"""Bounded SSE decoder; deltas precede the validated terminal result (M11)."""

import json
from typing import Literal

from pydantic import BaseModel, Field

from agent_provider import Completion


class FunctionDelta(BaseModel):
    name: str = Field(default="", max_length=80)
    arguments: str = Field(default="", max_length=16000)


class CallDelta(BaseModel):
    index: int = Field(ge=0, lt=10, strict=True)
    id: str = Field(default="", max_length=200)
    type: Literal["function"] = "function"
    function: FunctionDelta = Field(default_factory=FunctionDelta)


class Delta(BaseModel):
    content: str | None = None
    reasoning: str | None = None
    reasoning_content: str | None = None
    tool_calls: list[CallDelta] = Field(default_factory=list, max_length=10)


class StreamChoice(BaseModel):
    index: Literal[0]
    delta: Delta
    finish_reason: Literal["stop", "tool_calls"] | None = None


class Frame(BaseModel):
    choices: list[StreamChoice] = Field(max_length=1)
    usage: dict[str, object] | None = None


class StreamDecoder:
    def __init__(self) -> None:
        self.buffer = bytearray()
        self.total = 0
        self.text = ""
        self.calls: dict[int, dict[str, str]] = {}
        self.usage: dict[str, object] | None = None
        self.reason: str | None = None
        self.result: dict[str, object] | None = None

    def feed(self, piece: bytes) -> list[dict[str, object]]:
        self.total += len(piece)
        if self.total > 800000 or (self.result is not None and piece.strip()):
            raise ValueError("stream_limit_or_trailing_data")
        self.buffer.extend(piece)
        events: list[dict[str, object]] = []
        while b"\n" in self.buffer:
            line, _, rest = self.buffer.partition(b"\n")
            self.buffer = bytearray(rest)
            line = line.rstrip(b"\r")
            if not line or line.startswith(b":"):
                continue
            if not line.startswith(b"data:"):
                raise ValueError("invalid_sse_field")
            data = line[5:].strip()
            if self.result is not None:
                raise ValueError("trailing_frame")
            if data == b"[DONE]":
                self._done()
                continue
            frame = Frame.model_validate(json.loads(data))
            if frame.usage is not None:
                if self.usage is not None:
                    raise ValueError("duplicate_usage")
                self.usage = frame.usage
            for choice in frame.choices:
                if self.reason is not None:
                    raise ValueError("delta_after_finish")
                delta = choice.delta
                for key, value in (
                    ("content", delta.content),
                    ("reasoning_content", delta.reasoning_content or delta.reasoning),
                ):
                    if value:
                        events.append({"delta": {key: value}})
                        if key == "content":
                            self.text += value
                for call in delta.tool_calls:
                    target = self.calls.setdefault(
                        call.index, {"id": "", "name": "", "arguments": ""}
                    )
                    target["id"] += call.id
                    target["name"] += call.function.name
                    target["arguments"] += call.function.arguments
                    if any(
                        len(target[k]) > n
                        for k, n in (("id", 200), ("name", 80), ("arguments", 16000))
                    ):
                        raise ValueError("tool_limit")
                self.reason = choice.finish_reason
        return events

    def _done(self) -> None:
        calls = [self.calls[i] for i in sorted(self.calls)]
        completion = Completion.model_validate(
            {
                "usage": self.usage,
                "choices": [
                    {
                        "finish_reason": self.reason,
                        "message": {
                            "content": self.text,
                            "tool_calls": [
                                {
                                    "id": c["id"],
                                    "type": "function",
                                    "function": {
                                        "name": c["name"],
                                        "arguments": c["arguments"],
                                    },
                                }
                                for c in calls
                            ],
                        },
                    }
                ],
            }
        )
        if not self.text and not calls:
            raise ValueError("empty_stream")
        if len({c["id"] for c in calls}) != len(calls):
            raise ValueError("duplicate_call")
        if bool(calls) != (self.reason == "tool_calls"):
            raise ValueError("inconsistent_finish")
        self.result = {
            "text": self.text,
            "calls": calls,
            "usage": completion.usage.model_dump(),
        }

    def finish(self) -> None:
        if self.buffer.strip() or self.result is None:
            raise ValueError("incomplete_stream")
