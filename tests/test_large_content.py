"""M10: relevant evidence must survive a large source, including Unicode."""

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, patch

from services.orchestrator.cache import Cache
from services.orchestrator.content import select_passages
from services.orchestrator.tools import Fetch, Runtime


class SelectionTests(unittest.TestCase):
    def test_tail_evidence_and_exact_offsets(self) -> None:
        text = "Routine unrelated information. " * 5000
        text += "\nThe zephyr warranty lasts 73 months.\n"
        result = select_passages(text, "zephyr warranty", 2000)
        self.assertIn("73 months", "".join(p.text for p in result))
        self.assertLessEqual(sum(len(p.text.encode()) for p in result), 2000)
        for passage in result:
            self.assertEqual(text[passage.start : passage.end], passage.text)
        self.assertEqual([p.start for p in result], sorted(p.start for p in result))

    def test_unicode_and_small_budgets(self) -> None:
        text = "预算🙂 été " * 300 + "Garantie spéciale 73 mois."
        for budget in (4, 31, 700, 2000):
            result = select_passages(text, "Garantie spéciale", budget)
            self.assertTrue(result)
            self.assertLessEqual(sum(len(p.text.encode()) for p in result), budget)
            for passage in result:
                self.assertEqual(passage.text, text[passage.start : passage.end])
        with self.assertRaises(ValueError):
            select_passages(text, "q", 0)

    def test_empty_short_and_no_match(self) -> None:
        self.assertEqual(select_passages("", "q", 100), [])
        result = select_passages("short text", "q", 100)
        self.assertEqual("".join(p.text for p in result), "short text")
        self.assertEqual(result, select_passages("short text", "q", 100))
        self.assertTrue(select_passages("Other topic. " * 100, "absent", 100))

    def test_qualified_identifier_outweighs_generic_question_words(self) -> None:
        text = (
            "Documentation source return affect count cancel uncancel. " * 300
            + "\nTask.cancelling(): pending requests = cancel minus uncancel.\n"
        )
        selected = select_passages(
            text,
            "According to documentation what does Task.cancelling() return and how do cancel and uncancel affect count? Cite source.",
            800,
        )
        self.assertIn("pending requests", "".join(p.text for p in selected))

    def test_nonoverlap_determinism_and_examined(self) -> None:
        text = "Other information. " * 1000 + "Needle evidence."
        result = select_passages(text, "Needle", 2000)
        self.assertEqual(result, select_passages(text, "Needle", 2000))
        self.assertGreater(result[0].examined, len(result))
        for left, right in zip(result, result[1:]):
            self.assertLessEqual(left.end, right.start)
        self.assertEqual(select_passages("🙂", "q", 1), [])


class LargeFetchTests(unittest.IsolatedAsyncioTestCase):
    async def test_cache_selection_depends_on_question(self) -> None:
        text = "Albatross permit: 17 days.\n" + "Unrelated content. " * 5000
        text += "\nZephyr warranty: 73 months."
        with tempfile.TemporaryDirectory() as directory:
            runtime = Runtime(Cache(Path(directory) / "cache.sqlite"), Decimal(0))
            with (
                patch.object(
                    runtime.web,
                    "fetch",
                    new=AsyncMock(return_value=("https://example.org/final", b"html")),
                ) as fetch,
                patch("trafilatura.extract", return_value=text),
            ):
                first = await runtime.fetch(
                    Fetch(url="https://example.org", query="Zephyr warranty"), 5
                )
                second = await runtime.fetch(
                    Fetch(url="https://example.org", query="Albatross permit"), 5
                )
            self.assertIn("73 months", str(first["text"]))
            self.assertIn("17 days", str(second["text"]))
            self.assertEqual(fetch.await_count, 1)
            self.assertEqual(first["url"], "https://example.org/final")
            self.assertEqual(first["consulted_at"], second["consulted_at"])
            self.assertIn("passages", first)
            self.assertLessEqual(len(str(first["text"]).encode()), 2000)

    async def test_original_question_used_and_failed_fetch_not_cached(self) -> None:
        text = "Unrelated filler. " * 5000 + "Zephyr warranty: 73 months."
        with tempfile.TemporaryDirectory() as directory:
            runtime = Runtime(
                Cache(Path(directory) / "cache.sqlite"), Decimal(0), "Zephyr warranty"
            )
            with (
                patch.object(
                    runtime.web,
                    "fetch",
                    new=AsyncMock(return_value=("https://example.org", b"html")),
                ),
                patch("trafilatura.extract", side_effect=[None, text]),
            ):
                with self.assertRaisesRegex(ValueError, "extraction_empty"):
                    await runtime.fetch(Fetch(url="https://example.org"), 5)
                output = await runtime.fetch(Fetch(url="https://example.org"), 5)
            self.assertIn("73 months", str(output["text"]))
            self.assertTrue(output["selected"])
            cached = runtime.cache.get(str(output["handle"]))
            assert cached is not None
            self.assertEqual(cached["text"], text)
