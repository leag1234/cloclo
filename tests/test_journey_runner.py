"""CI reuse cannot accept stale, failed, incomplete or differently scoped evidence."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from journey_runner import CACHE, REPORT, run


class JourneyReuseTests(unittest.TestCase):
    def test_same_inputs_reuse_but_changes_and_other_runs_reexecute(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", directory], check=True)
            (root / ".gitignore").write_text("BRAIN/\n")
            source = root / "source.py"
            source.write_text("first")
            calls = []

            def execute() -> None:
                calls.append(True)
                (root / REPORT).parent.mkdir(parents=True, exist_ok=True)
                (root / REPORT).write_text(
                    json.dumps(
                        {
                            "mode": "replay",
                            **{f"J{n}_check": True for n in range(1, 34)},
                        }
                    )
                )

            run(root, "run-1", execute)
            (root / REPORT).unlink()  # Protected M21 verifier deletes this output.
            run(root, "run-1", execute)
            self.assertEqual(len(calls), 1)
            self.assertTrue((root / REPORT).exists())
            source.write_text("changed")
            run(root, "run-1", execute)
            run(root, "run-2", execute)
            run(root, None, execute)  # Local and live acquisitions never reuse.
            run(root, None, execute)
            self.assertEqual(len(calls), 5)

    def test_failed_or_incomplete_suites_never_create_a_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", directory], check=True)
            (root / ".gitignore").write_text("BRAIN/\n")

            def fail() -> None:
                raise RuntimeError("failed_suite")

            with self.assertRaisesRegex(RuntimeError, "failed_suite"):
                run(root, "run", fail)
            self.assertFalse((root / CACHE).exists())

            def incomplete() -> None:
                (root / REPORT).parent.mkdir(parents=True, exist_ok=True)
                (root / REPORT).write_text(
                    json.dumps({"mode": "replay", "J1_check": True})
                )

            with self.assertRaisesRegex(RuntimeError, "incomplete_ci_journey_evidence"):
                run(root, "run", incomplete)
            self.assertFalse((root / CACHE).exists())
