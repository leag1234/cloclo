"""Task H structured content contract (REQ-ENG-004, REQ-ENG-007)."""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=4000)]


class ContentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Table(ContentModel):
    headers: tuple[Text, ...] = Field(min_length=1, max_length=8)
    rows: tuple[tuple[Text, ...], ...] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def rectangular(self) -> Self:
        if any(len(row) != len(self.headers) for row in self.rows):
            raise ValueError("table_row_width")
        return self


class Section(ContentModel):
    heading: Text
    paragraphs: tuple[Text, ...] = Field(default=(), max_length=50)
    bullets: tuple[Text, ...] = Field(default=(), max_length=50)
    tables: tuple[Table, ...] = Field(default=(), max_length=10)
    images: tuple[Text, ...] = Field(default=(), max_length=5)

    @model_validator(mode="after")
    def substantive(self) -> Self:
        if not (self.paragraphs or self.bullets or self.tables or self.images):
            raise ValueError("section_body_required")
        return self


class Content(ContentModel):
    title: Text
    sections: tuple[Section, ...] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def printable(self) -> Self:
        for text in self.texts():
            if not text.strip() or any(ord(c) < 32 for c in text):
                raise ValueError("blank_or_control_text")
        if sum(map(len, self.texts())) > 200_000:
            raise ValueError("content_size_limit")
        return self

    def texts(self) -> tuple[str, ...]:
        result = [self.title]
        for section in self.sections:
            result.extend((section.heading, *section.paragraphs, *section.bullets))
            for table in section.tables:
                result.extend(table.headers)
                for row in table.rows:
                    result.extend(row)
        return tuple(result)
