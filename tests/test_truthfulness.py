"""Independent hand-written checks for the public truthfulness ruler."""

from collections import Counter
from datetime import date
import json
from pathlib import Path
import unittest
from typing import Any

from evals.truthfulness.score import Case, aggregate, load_cases, score_answer


class TruthfulnessTests(unittest.TestCase):
    def test_hand_written_verdicts(self) -> None:
        fixture = json.loads(Path("tests/truthfulness_answers.json").read_text())
        for row in fixture:
            with self.subTest(row["name"]):
                case = Case.model_validate(row["case"])
                result = score_answer(case, row["answer"])
                for key, expected in row["expected"].items():
                    self.assertEqual(result[key], expected, key)

    def test_dataset_contract(self) -> None:
        cases = load_cases(Path("evals/truthfulness/cases.json"))
        self.assertEqual(len(cases), 40)
        self.assertEqual(len({case.id for case in cases}), 40)
        self.assertEqual(Counter(case.language for case in cases), {"fr": 24, "en": 16})
        self.assertEqual(
            Counter(case.category for case in cases),
            {"stable": 10, "nonexistent": 12, "changing": 10, "adversarial": 8},
        )
        for case in cases:
            if case.category == "nonexistent":
                self.assertEqual(case.expectation, "abstain")
                self.assertTrue(case.verification)
                self.assertFalse(case.expected_facts)
            else:
                self.assertTrue(case.expected_facts)
            for fact in case.expected_facts:
                self.assertTrue(fact.sources)
                for source in fact.sources:
                    self.assertTrue(source.url.startswith("https://"))
                    date.fromisoformat(source.consulted_on)
            self.assertTrue(case.forbidden_claims)

    def test_metrics_keep_denominators_and_failures(self) -> None:
        cases = load_cases(Path("evals/truthfulness/cases.json"))
        stable = cases[0]
        negative = next(case for case in cases if case.category == "nonexistent")
        rows: list[dict[str, Any]] = [
            {
                "id": stable.id,
                "profile": "atlas-qwen",
                "answer": "",
                "error": "http_503",
            },
            {
                "id": negative.id,
                "profile": "atlas-qwen",
                "answer": "I cannot verify this entity.",
                "error": None,
            },
        ]
        result = aggregate(cases, rows)
        metrics = result["profiles"]["atlas-qwen"]["overall"]
        self.assertEqual(metrics["attempted"], 2)
        self.assertEqual(metrics["technical_failures"], 1)
        self.assertEqual(metrics["fact_accuracy"]["value"], 0.0)
        self.assertEqual(metrics["fabrication_rate"]["denominator"], 1)
        self.assertEqual(metrics["correct_abstention_rate"]["value"], 1.0)
        self.assertIsNone(metrics["false_premise_acceptance_rate"]["value"])
        self.assertIn("fr", result["profiles"]["atlas-qwen"]["languages"])
        self.assertIn("stable", result["profiles"]["atlas-qwen"]["categories"])
        self.assertEqual(result["profiles"]["atlas-glm"]["overall"]["attempted"], 0)
        with self.assertRaises(ValueError):
            aggregate(cases, rows + rows)


if __name__ == "__main__":
    unittest.main()
