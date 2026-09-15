"""Classify transformations only when a previous assistant answer exists."""

import re

from services.orchestrator.chat_schema import ChatMessage


def is_followup(messages: list[ChatMessage]) -> bool:
    if len(messages) < 2 or messages[-2].role != "assistant":
        return False
    text = messages[-1].text.strip()
    return bool(
        re.fullmatch(
            r"(?is)(?:plus court|shorter|en allemand|in German|en anglais)[.!?]*",
            text,
        )
        or (
            re.search(
                r"(?i)\b(tradui\w*|translat\w*|résum\w*|summari[sz]\w*|reformul\w*|rewrite)\b",
                text,
            )
            and re.search(
                r"(?i)\b(ta réponse|votre réponse|ce que tu|précédent\w*|ça|cela|that|it|your answer|previous)\b",
                text,
            )
        )
    )


def image_iteration(messages: list[ChatMessage]) -> str | None:
    if len(messages) < 3 or messages[-2].role != "assistant":
        return None
    previous = messages[-2].text
    image = r"!\[[^\]]*\]\([^)]*(?:/images/|\[IMAGE\])"
    if not re.search(image, previous):
        return None
    question = messages[-1].text
    change = r"(?i)\b(ajout\w*|oubli\w*|même|add|forgot|same|change|remplac\w*)\b"
    if not re.search(change, question):
        return None
    start = len(messages) - 3
    while (
        start >= 2
        and messages[start].role == "user"
        and re.search(change, messages[start].text)
        and messages[start - 1].role == "assistant"
        and re.search(image, messages[start - 1].text)
    ):
        start -= 2
    return "\n".join(m.text for m in messages[start:] if m.role == "user")
