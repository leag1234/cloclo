"""Replay cannot silently accept changed prompts, calls or incomplete records."""

import unittest
import gzip
import json
import tempfile
from pathlib import Path
from decimal import Decimal
from typing import Any
from agent_gate_eval import ReplayModel, ReplayTools, select_cases, load_record
from services.orchestrator.loop import Call


class ReplayTests(unittest.IsolatedAsyncioTestCase):
    def record(self) -> dict[str, Any]:
        return {
            "configuration": {
                "input_eur_per_mtok": "0.6",
                "output_eur_per_mtok": "3.6",
                "max_tokens": 2048,
            },
            "model": [
                {
                    "messages": [{"role": "user", "content": "test"}],
                    "prompt_tokens": 20,
                    "response": {
                        "text": "answer",
                        "calls": [],
                        "usage": {"tokens": 22, "cost": "0.0000192"},
                    },
                }
            ],
            "tools": [
                {
                    "call": {
                        "id": "1",
                        "name": "calculator",
                        "arguments": '{"expr":"1+1"}',
                    },
                    "output": {"value": "2"},
                }
            ],
        }

    async def test_exact_replay_and_usage(self) -> None:
        model = ReplayModel(self.record())
        turn = await model.complete([{"role": "user", "content": "test"}], 1)
        self.assertEqual(turn.text, "answer")
        self.assertEqual(model.prompt_tokens, 20)
        self.assertIsNotNone(turn.usage)
        assert turn.usage is not None
        self.assertEqual(turn.usage.cost, Decimal("0.0000192"))
        tools = ReplayTools(self.record())
        self.assertEqual(
            await tools.execute(Call("1", "calculator", '{"expr":"1+1"}'), 1),
            {"value": "2"},
        )

    async def test_changed_request_is_rejected(self) -> None:
        with self.assertRaisesRegex(AssertionError, "unrecorded_model_request"):
            await ReplayModel(self.record()).complete(
                [{"role": "user", "content": "changed"}], 1
            )
        with self.assertRaisesRegex(AssertionError, "unrecorded_tool_request"):
            await ReplayTools(self.record()).execute(Call("1", "web_search", "{}"), 1)

    def test_only_validated_web_cases_are_executed(self) -> None:
        cases = [
            {"id": "valid", "statut": "valide"},
            {"id": "pending", "statut": "draft"},
            {"id": "expired", "statut": "stale"},
        ]
        self.assertEqual(select_cases("web", cases), [cases[0]])
        self.assertEqual(select_cases("tools", cases), cases)
        with self.assertRaisesRegex(ValueError, "no_validated_web_cases"):
            select_cases("web", cases[1:])

    def test_compressed_recording_preserves_exact_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with gzip.open(path / "case.json.gz", "wt", encoding="utf-8") as stream:
                json.dump(self.record(), stream)
            self.assertEqual(load_record(path, "case"), self.record())
            (path / "invalid.json").write_text("[]")
            with self.assertRaisesRegex(ValueError, "invalid_recording"):
                load_record(path, "invalid")
