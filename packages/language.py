"""Choose localized UI text from the actual question, with a conservative fallback."""

import importlib
import re


def question_language(text: str, fallback: str = "fr") -> str:
    if not re.search(r"[^\W\d_]", text):
        return fallback
    detector = importlib.import_module("langdetect")
    detector.DetectorFactory.seed = 0
    scores = detector.detect_langs(text)
    return str(scores[0].lang) if scores[0].prob >= 0.8 else fallback
