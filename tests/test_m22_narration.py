"""M22 narration must never reach streamed or stored answer content."""

import unittest
from services.orchestrator.narration import NarrationFilter, clean_answer


class NarrationTests(unittest.TestCase):
    def test_chunk_boundaries_and_activity(self) -> None:
        source = "Je vais rechercher des informations. Let me verify the date. Le prix est 135 USD."
        for size in range(1, len(source)):
            parser = NarrationFilter()
            output = "".join(
                parser.feed(source[i : i + size]) for i in range(0, len(source), size)
            )
            output += parser.finish()
            self.assertEqual(output.strip(), "Le prix est 135 USD.")
            self.assertEqual(len(parser.removed), 2)

    def test_substantive_quoted_and_code_text_preserved(self) -> None:
        for text in (
            "Je vais à Paris demain.",
            "Let me explain the calculation: 2 + 2 = 4.",
            "> Je vais rechercher des informations.",
            "```text\nLet me verify the date.\n```",
            "Il a dit « Je vais rechercher ».",
            "Le prix est 135.50 USD.",
        ):
            self.assertEqual(clean_answer(text), text)

    def test_empty_narration_is_not_success(self) -> None:
        with self.assertRaisesRegex(ValueError, "empty_content_after_narration"):
            clean_answer(
                "Je vais consulter une source. Je peux maintenant synthétiser."
            )
