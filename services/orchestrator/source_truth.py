"""Citation provenance uses retrieved tool results, never assistant history."""

import re

URL = re.compile(r"https?://[^\s<>\"'()\]]+")


def urls(text: str) -> set[str]:
    return {match.rstrip(".,;:)]}>'\"") for match in URL.findall(text)}


def without_unretrieved(text: str, retrieved: set[str]) -> str:
    def replace(match: re.Match[str]) -> str:
        value = match[0].rstrip(".,;:)]}>'\"")
        return match[0] if value in retrieved else "[unverified source]"

    text = URL.sub(replace, text)
    if not retrieved:
        # Do not let a remembered reference impersonate a consulted document.
        text = re.sub(
            r"(?im)^.*(?:consult[eé]\w* le|consulted (?:on|at)|accessed on|^sources?\s*:).*(?:\n|$)",
            "",
            text,
        )
    return text


def inline_source_markers(text: str, retrieved: list[str]) -> str:
    """Turn retrieved web URLs into compact Markdown links Open WebUI renders."""
    numbers = {url: index for index, url in enumerate(dict.fromkeys(retrieved), 1)}

    def markdown(match: re.Match[str]) -> str:
        url = match.group(1).rstrip(".,;:)]}>'\"")
        return f"[{numbers[url]}]({url})" if url in numbers else match.group(0)

    text = re.sub(r"\[[^\]]+\]\((https?://[^\s)]+)\)", markdown, text)

    def bare(match: re.Match[str]) -> str:
        url = match[0].rstrip(".,;:)]}>'\"")
        tail = match[0][len(url) :]
        return f"[{numbers[url]}]({url}){tail}" if url in numbers else match[0]

    rendered = re.sub(r"(?<!\]\()https?://[^\s<>\"'()\]]+", bare, text)
    return rendered


def source_footer(retrieved: list[str], language: str) -> str:
    """Expose the actual retrieval trail separately from the model's citations."""
    import json
    from pathlib import Path

    if not retrieved:
        return ""
    labels = json.loads(Path("prompts/activity-labels.json").read_text())
    labels = labels.get(language, labels["en"])
    return (
        "\n\n<details>\n<summary>"
        + str(labels["web_search"])
        + " / "
        + str(labels["web_fetch"])
        + "</summary>\n\n"
        + "\n".join("- <" + url + ">" for url in dict.fromkeys(retrieved))
        + "\n</details>"
    )
