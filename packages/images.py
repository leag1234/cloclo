"""M12 validated image messages shared by the adapter and gateway boundary."""

import base64
import io
import re
from typing import Annotated, Literal, Self

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from services.guardrails.input_filter import validate_input


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def image_info(url: str) -> dict[str, int | str]:
    prefix, _, encoded = url.partition(",")
    formats = {"data:image/png;base64": "PNG", "data:image/jpeg;base64": "JPEG"}
    if prefix not in formats or len(encoded) > 2796204:
        raise ValueError("invalid_image")
    uniform: str | None = None
    try:
        raw = base64.b64decode(encoded, validate=True)
        if not raw or len(raw) > 2 * 1024 * 1024:
            raise ValueError("image_size_exceeded")
        with Image.open(io.BytesIO(raw), formats=[formats[prefix]]) as im:
            width, height = im.size
            if not (0 < width <= 4096 and 0 < height <= 4096):
                raise ValueError("image_dimensions_exceeded")
            if width * height > 16000000 or getattr(im, "n_frames", 1) != 1:
                raise ValueError("image_dimensions_exceeded")
            im.verify()
        with Image.open(io.BytesIO(raw), formats=[formats[prefix]]) as im:
            im.load()  # Header validation alone misses a truncated JPEG raster.
            # A solid image has an exact, deterministic color measurement. This
            # avoids asking a vision model to infer color from featureless patches.
            if "A" not in im.getbands():
                colors = im.convert("RGB").getcolors(maxcolors=1)
                if colors and isinstance(colors[0][1], tuple):
                    uniform = ",".join(str(component) for component in colors[0][1])
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError("invalid_image") from exc
    metadata: dict[str, int | str] = {
        "format": formats[prefix],
        "width": width,
        "height": height,
        "bytes": len(raw),
    }
    if uniform is not None:
        metadata["uniform_rgb"] = uniform
    return metadata


class ImageURL(Strict):
    url: str = Field(max_length=2796300, repr=False)
    detail: Literal["auto", "low", "high"] = Field(
        default="auto", exclude_if=lambda value: value == "auto"
    )

    @field_validator("url")
    @classmethod
    def valid_image(cls, value: str) -> str:
        image_info(value)
        return value


class TextPart(Strict):
    type: Literal["text"]
    text: str = Field(min_length=1, max_length=200000, pattern=r"\S")
    _safe_text = field_validator("text")(validate_input)


class ImagePart(Strict):
    type: Literal["image_url"]
    image_url: ImageURL


class VisionMessage(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    role: Literal["system", "user", "assistant"]
    content: str | list[Annotated[TextPart | ImagePart, Field(discriminator="type")]]

    @model_validator(mode="before")
    @classmethod
    def strip_legacy_images(cls, value: object) -> object:
        if isinstance(value, dict) and value.get("role") == "assistant":
            content = value.get("content")
            if isinstance(content, str):
                value = {
                    **value,
                    "content": re.sub(
                        r"data:image/[^,\s]+,[A-Za-z0-9+/=]+", "[IMAGE]", content
                    ),
                }
        return value

    @model_validator(mode="after")
    def valid_content(self) -> Self:
        if isinstance(self.content, str):
            if not self.content.strip() or len(self.content) > 200000:
                raise ValueError("invalid_text")
            validate_input(self.content)
        elif not 1 <= len(self.content) <= 16 or self.role != "user":
            raise ValueError("invalid_parts")
        return self

    @property
    def text(self) -> str:
        if isinstance(self.content, str):
            return self.content
        return "\n".join(p.text for p in self.content if isinstance(p, TextPart))

    @property
    def images(self) -> list[dict[str, int | str]]:
        if isinstance(self.content, str):
            return []
        return [
            image_info(p.image_url.url)
            for p in self.content
            if isinstance(p, ImagePart)
        ]


class VisionInput(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    messages: list[VisionMessage] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def valid_history(self) -> Self:
        if self.messages[-1].role != "user" or not self.messages[-1].text.strip():
            raise ValueError("last_message_must_have_user_text")
        if sum(len(m.text) for m in self.messages) > 600000:
            raise ValueError("context_exceeded")
        images = [im for m in self.messages for im in m.images]
        if len(images) > 4 or sum(int(im["bytes"]) for im in images) > 4 * 1024 * 1024:
            raise ValueError("image_size_exceeded")
        if sum(int(im["width"]) * int(im["height"]) for im in images) > 16000000:
            raise ValueError("image_dimensions_exceeded")
        return self
