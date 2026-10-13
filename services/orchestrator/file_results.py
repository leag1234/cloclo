"""Render verified publication URLs and explicit transformation declarations."""

import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import unquote, urlsplit


def inline_fallback(text: str, language: str) -> str:
    notices = {
        "fr": "Aucun fichier n'a pu être publié. Le contenu ci-dessus est la solution de secours en texte.",
        "de": "Keine Datei konnte veröffentlicht werden. Der obige Inhalt dient als Ersatz in Textform.",
        "es": "No se pudo publicar ningún archivo. El contenido anterior es la alternativa en texto.",
        "it": "Nessun file è stato pubblicato. Il contenuto sopra è l'alternativa in testo.",
        "en": "No file was produced for download. The content above is the inline fallback.",
    }
    return text + "\n\n" + notices[language]


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
