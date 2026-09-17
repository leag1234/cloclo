"""Mandatory discovery uses the same loop quotas as model-selected research."""

import json
import re
import unicodedata
from urllib.parse import urlsplit

from services.orchestrator.loop import Call


def required_research(question: str, language: str) -> tuple[Call, ...]:
    normalized = "".join(
        c
        for c in unicodedata.normalize("NFD", question.casefold())
        if not unicodedata.combining(c)
    )
    # Internal evidence must be retrieved in scope before any public research;
    # the model handles mixed requests under the existing internal-first policy.
    if re.search(
        r"\b(internal|interne|internen?|interna|interno|confidentiel|confidential|confidencial|vertraulich)\b",
        normalized,
    ):
        return ()
    urls = re.findall(r'https?://[^\s<>"\']+', question)
    practical = re.search(
        r"\b(comment|how|wie|como|come)\b.{0,80}\b(fabriqu\w*|constru\w*|build|make|bau\w*|camera|appareil)\b|\b(compar\w*|recommend\w*|recommand\w*|empfehl\w*|consigli\w*)\b",
        normalized,
    )
    temporal = re.search(
        r"\b(ipo|pdg|ceo|prix|price|costs?|coute|tarif\w*|prezzo|precio|preis|disponib\w*|available|verfugbar|latest|current|actuel\w*|derniere? version|neueste\w*|aujourd.hui|today|heute)\b|\b(qui|who|wer)\b.{0,60}\b(dirige|runs|leads|chef|leitet|fuhrt|president)\b|\b(is|est|ist)\b.{0,80}\b(public|cotee?|still|encore|noch)\b",
        normalized,
    )
    if urls and practical:
        url = urls[0].rstrip(".,;!?")
        topic = urlsplit(url).path.rsplit("/", 1)[-1].replace("-", " ")
        query = topic + " practical how to tutorial"
        return (
            Call(
                "required-source",
                "web_fetch",
                json.dumps({"url": url, "query": question}),
            ),
            Call(
                "required-subject",
                "web_search",
                json.dumps({"query": query[:500], "lang": language}),
            ),
        )
    explicit = re.search(
        r"\b(recherch\w*|search|suche|busca|cerca)\b.{0,60}\b(web|internet|sources?)\b",
        normalized,
    )
    if temporal or explicit:
        if re.search(r"\bipo\b", normalized):
            question += " offer price opening price"
        return (
            Call(
                "required-current",
                "web_search",
                json.dumps({"query": question[:500], "lang": language}),
            ),
        )
    return ()
