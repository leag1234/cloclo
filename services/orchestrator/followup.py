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
    if not re.search(r"!\[[^\]]*\]\([^)]*(?:/images/|\[IMAGE\])", previous):
        return None
    question = messages[-1].text
    if not re.search(
        r"(?i)\b(ajout\w*|oubli\w*|même|add|forgot|same|change|remplac\w*)\b", question
    ):
        return None
    from packages.imagegen import image_request

    start = len(messages) - 3
    for index in range(start, -1, -1):
        if messages[index].role == "user" and image_request(messages[index].text):
            start = index
            break
    return "\n".join(m.text for m in messages[start:] if m.role == "user")
