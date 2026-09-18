"""Render verified publication URLs and explicit transformation declarations."""

import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import unquote, urlsplit


def render_files(
    text: str, files: list[str], strategies: list[str], language: str
) -> str:
    return canonical_links(text, files) + file_footer(files, strategies, language)


def file_footer(files: list[str], strategies: list[str], language: str) -> str:
    labels = json.loads(Path("prompts/file-strategies.json").read_text())
    localized = labels.get(language, labels["en"])
    text = ""
    for url, strategy in zip(files, strategies, strict=True):
        filename = unquote(PurePosixPath(url).name)
        text += f"\n\n[{filename}]({url}) — {localized[strategy]}."
    return text


def canonical_links(text: str, files: list[str]) -> str:
    for url in files:
        filename = unquote(PurePosixPath(url).name)

        def canonical(match: re.Match[str]) -> str:
            target = unquote(PurePosixPath(urlsplit(match[2]).path).name)
            return f"[{match[1]}]({url})" if target == filename else match[0]

        # A model may turn a relative UI URL into an invented external host.
        text = re.sub(r"\[([^\]]+)\]\(([^\s)]+)\)", canonical, text)
    return text
