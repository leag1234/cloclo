"""Server-side eligibility for the owner's file-production request allowance."""

import re
import unicodedata


def produces_file(text: str) -> bool:
    text = "".join(
        c
        for c in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(c)
    )
    if re.search(r"\b(dessine\w*|zeichne\w*|dibuja\w*)\b", text):
        return True
    artifact = re.search(
        r"\b(pdf|docx|xlsx|pptx|csv|document|presentation|diaporama|slides?"
        r"|spreadsheet|tableur|fichier|file|datei|dokument|prasentation"
        r"|tabellenkalkulation|archivo|documento|presentacion|foglio|presentazione"
        r"|image|imagen|immagine|bild)\b",
        text,
    )
    action = re.search(
        r"\b(cre\w*|gener\w*|produ\w*|export\w*|convert\w*|transform\w*"
        r"|make|build|write|prepare|fais|fait\w*|redig\w*|prepar\w*"
        r"|erstell\w*|schreib\w*|erstelle|haz|scrivi|disegn\w*|draw)\b",
        text,
    )
    return artifact is not None and (
        action is not None
        or (
            len(text.split()) <= 4
            and not re.search(
                r"\b(what|why|how|explain|means|was|ist|comment|pourquoi|que)\b", text
            )
        )
    )
