"""Resolve conversation language independently of model output and UI labels."""

import importlib
import json
from pathlib import Path
import re
from collections.abc import Sequence
import unicodedata

from packages.images import VisionMessage

LANGUAGES = ("fr", "de", "es", "it", "en")


def detected_language(text: str) -> str | None:
    normalized = "".join(
        c
        for c in unicodedata.normalize("NFKD", text.lower())
        if not unicodedata.combining(c)
    )
    if re.search(r"\b(decris|genere|dessine|voudrais|bonjour|francais)\b", normalized):
        return "fr"
    if re.match(r"\s*i would like\b", normalized):
        return "en"
    if not re.search(r"[^\W\d_]", text):
        return None
    detector = importlib.import_module("langdetect")
    detector.DetectorFactory.seed = 0
    try:
        scores = detector.detect_langs(text)
    except detector.lang_detect_exception.LangDetectException:
        return None
    language = str(scores[0].lang)
    return language if scores[0].prob >= 0.8 and language in LANGUAGES else None


def question_language(text: str, fallback: str) -> str:
    return detected_language(text) or fallback


def conversation_language(messages: Sequence[VisionMessage], locale: str) -> str:
    if locale not in LANGUAGES:
        raise ValueError("unsupported_language")
    history: str | None = None
    for message in messages[:-1]:
        if message.role == "user":
            history = detected_language(message.text) or history
    if history is None:
        for message in messages[:-1]:
            if message.role == "assistant":
                history = detected_language(message.text) or history
    current = messages[-1].text
    if len(re.findall(r"\b[\w'-]+\b", current)) < 5 and history is not None:
        return history
    return question_language(current, history or locale)


def language_instruction(language: str) -> str:
    if language not in LANGUAGES:
        raise ValueError("unsupported_language")
    instructions = json.loads(Path("prompts/language.json").read_text())
    return str(instructions[language])
