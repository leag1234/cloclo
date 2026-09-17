"""Remove standalone model planning sentences before streaming any of their bytes."""

import logging

_PREFIXES = (
    "je vais rechercher",
    "je vais consulter",
    "je vais vérifier",
    "je vais verifier",
    "je peux maintenant synthétiser",
    "je peux maintenant synthetiser",
    "j'ai une source détaillée",
    "j’ai une source détaillée",
    "let me verify",
    "let me check",
    "let me search",
    "i will search",
    "i'll search",
    "i will look up",
    "i can now summarize",
)


class NarrationFilter:
    def __init__(self) -> None:
        self.pending = ""
        self.removed: list[str] = []
        self.passing = False
        self.code = False
        self.backticks = 0

    def feed(self, text: str) -> str:
        output = []
        for char in text:
            self.backticks = self.backticks + 1 if char == "`" else 0
            if self.backticks == 3:
                self.code = not self.code
            if self.passing or self.code:
                output.append(char)
                if char in ".!?\n" and not self.code:
                    self.passing = False
                continue
            self.pending += char
            candidate = self.pending.lstrip().lower()
            match = any(candidate.startswith(prefix) for prefix in _PREFIXES)
            possible = any(prefix.startswith(candidate) for prefix in _PREFIXES)
            if match:
                if char in ".!?\n":
                    self.removed.append(self.pending.strip())
                    self.pending = ""
            elif not possible:
                output.append(self.pending)
                self.pending = ""
                self.passing = char not in ".!?\n"
        return "".join(output)

    def finish(self) -> str:
        tail, self.pending = self.pending, ""
        if any(tail.lstrip().lower().startswith(prefix) for prefix in _PREFIXES):
            self.removed.append(tail.strip())
            return ""
        return tail


def clean_answer(text: str, *, allow_empty: bool = False) -> str:
    parser = NarrationFilter()
    answer = parser.feed(text) + parser.finish()
    if parser.removed:
        logging.getLogger(__name__).info(
            "narration_removed sentences=%d", len(parser.removed)
        )
    if text.strip() and not answer.strip() and not allow_empty:
        raise ValueError("empty_content_after_narration")
    return answer.lstrip() if parser.removed else answer
