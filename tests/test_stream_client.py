"""Streaming keeps the existing pre-I/O reservations, including failed streams."""

from decimal import Decimal
import unittest
from unittest.mock import AsyncMock, patch

from services.orchestrator.loop import Limits, Query, run
from services.orchestrator.model import Configuration, GatewayModel
from test_budgets import Tools


class StreamBudgetTests(unittest.IsolatedAsyncioTestCase):
    def model(self) -> GatewayModel:
        model = GatewayModel(
            "http://127.0.0.1:1",
            Configuration(
                input_eur_per_mtok=Decimal("0.6"),
                output_eur_per_mtok=Decimal("3.6"),
                max_tokens=2048,
            ),
        )
        model.sink = AsyncMock()
        return model

    async def test_budget_refuses_before_stream_io(self) -> None:
        with patch("services.orchestrator.model.receive", new_callable=AsyncMock) as io:
            result = await run(
                Query(question="Bonjour", lang="fr"),
                self.model(),
                Tools(),
                "",
                Limits(cost=Decimal("0")),
            )
            self.assertEqual(result.reason, "cost")
            io.assert_not_awaited()

    async def test_missing_usage_keeps_reservation(self) -> None:
        with patch("services.orchestrator.model.receive", new_callable=AsyncMock) as io:
            io.return_value = {"text": "partial", "calls": []}
            result = await run(
                Query(question="Bonjour", lang="fr"), self.model(), Tools(), ""
            )
            self.assertEqual(result.reason, "provider_error")
            self.assertGreater(result.cost, Decimal("0.007"))
            self.assertLessEqual(result.cost, Decimal("0.05"))

    async def test_reasoning_shares_output_and_phase_is_explicit(self) -> None:
        events: list[dict[str, object]] = []

        async def sink(event: dict[str, object]) -> None:
            events.append(event)

        model = self.model()
        model.sink, model.reasoning_effort = sink, "low"
        with patch("services.orchestrator.model.receive", new_callable=AsyncMock) as io:
            io.return_value = {
                "text": "Bonjour",
                "calls": [],
                "usage": {"prompt_tokens": 20, "completion_tokens": 100},
            }
            result = await run(Query(question="Bonjour", lang="fr"), model, Tools(), "")
            self.assertEqual(result.state, "done")
            self.assertEqual(model.output_tokens, 100)
            self.assertEqual(io.call_args.args[1]["reasoning_effort"], "low")
            self.assertEqual(events[0]["max_output_tokens"], 2048)
            self.assertEqual(events[-1]["phase"], "final")
