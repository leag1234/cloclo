"""The journey classifier rejects English and ignores code blocks."""

import unittest
from journey_language import matches


class LanguageTests(unittest.TestCase):
    def test_french_english_and_code(self) -> None:
        self.assertTrue(
            matches("Dans cette image, il y a un carré rouge et un cercle bleu.", "fr")
        )
        self.assertFalse(
            matches("The image shows a red square and a blue circle.", "fr")
        )
        self.assertTrue(
            matches("The image shows a red square and a blue circle.", "en")
        )
        self.assertTrue(
            matches(
                "La capitale de la France est Paris.\n```The image shows a red square.```",
                "fr",
            )
        )
        self.assertFalse(matches("```La capitale de la France est Paris.```", "fr"))
