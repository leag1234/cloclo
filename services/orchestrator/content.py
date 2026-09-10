"""Bounded lexical retrieval over the whole source, with exact Unicode offsets."""

import logging
import math
import re
from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class SelectedPassage:
    text: str
    start: int
    end: int
    examined: int


def select_passages(text: str, query: str, budget: int) -> list[SelectedPassage]:
    if budget <= 0:
        raise ValueError("invalid_content_budget")
    if not text:
        return []
    if len(text.encode()) <= budget:
        return [SelectedPassage(text, 0, len(text), 1)]
    width = min(800, budget)
    windows: list[tuple[int, int, str]] = []
    start = 0
    while start < len(text):
        part = text[start : start + width].encode()[:width].decode("utf-8", "ignore")
        if not part:
            start += 1
            continue
        end = start + len(part)
        windows.append((start, end, part))
        if end == len(text):
            break
        start += max(1, len(part) * 3 // 4)
    terms = set(re.findall(r"\w+", query.casefold()))
    matches = [
        terms.intersection(re.findall(r"\w+", p.casefold())) for _, _, p in windows
    ]
    frequency = Counter(term for match in matches for term in match)
    scores = [
        sum(math.log1p(len(windows) / frequency[t]) for t in match) for match in matches
    ]
    chosen: list[SelectedPassage] = []
    remaining = budget
    for index in sorted(range(len(windows)), key=lambda i: (-scores[i], i)):
        start, end, part = windows[index]
        if any(start < p.end and end > p.start for p in chosen):
            continue
        size = len(part.encode())
        if size > remaining:
            continue
        chosen.append(SelectedPassage(part, start, end, len(windows)))
        remaining -= size
        if not remaining:
            break
    logging.getLogger(__name__).info(
        "content_selected examined=%d selected=%d bytes=%d",
        len(windows),
        len(chosen),
        budget - remaining,
    )
    return sorted(chosen, key=lambda p: p.start)
