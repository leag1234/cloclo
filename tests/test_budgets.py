"""Integration of model/tool I/O and all four hard request limits."""

import asyncio
import unittest
from decimal import Decimal
from collections.abc import Callable

from services.orchestrator.loop import (
    Call,
    Limits,
    Message,
    Query,
    Reservation,
    Turn,
    run,
)


class Model:
    def __init__(self, name: str = "calculator", repeat: bool = False) -> None:
        self.calls = 0
        self.name, self.repeat = name, repeat
        self.delay = 0.0
        self.cancelled = False

    def estimate(self, messages: list[Message]) -> Reservation:
        return Reservation(10, Decimal("0.01"))

    async def complete(self, messages: list[Message], timeout: float) -> Turn:
        try:
            await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        self.calls += 1
        return Turn(
            "",
            (
                Call(
                    str(self.calls),
                    self.name,
                    '{"expr":"' + str(1 if self.repeat else self.calls) + '"}',
                ),
            ),
        )


class Tools:
    def __init__(self) -> None:
        self.calls = 0

    def estimate(self, call: Call) -> Reservation:
        return Reservation(0, Decimal(0))

    async def execute(self, call: Call, timeout: float) -> Message:
        self.calls += 1
        return {"value": "1"}


class BudgetTests(unittest.IsolatedAsyncioTestCase):
    async def test_four_budgets(self) -> None:
        for limits, reason, count in [
            (Limits(tokens=15), "tokens", 1),
            (Limits(tool_calls=1), "tool_calls", 1),
            (Limits(wall_clock=0), "wall_clock", 0),
            (Limits(cost=Decimal("0.015")), "cost", 1),
        ]:
            with self.subTest(reason=reason):
                tools = Tools()
                result = await run(
                    Query(question="test", lang="fr"), Model(), tools, "", limits
                )
                self.assertEqual((result.state, result.reason), ("stopped", reason))
                self.assertEqual(tools.calls, count)
                self.assertIn(reason, result.text)
                self.assertLessEqual(result.cost, limits.cost)
                self.assertLessEqual(result.tokens, limits.tokens)

    async def test_inflight_timeout(self) -> None:
        model = Model()
        model.delay = 1
        tools = Tools()
        result = await run(
            Query(question="test", lang="de"), model, tools, "", Limits(wall_clock=0.01)
        )
        self.assertEqual(result.reason, "wall_clock")
        self.assertTrue(model.cancelled)
        self.assertEqual(tools.calls, 0)

    async def test_repeat(self) -> None:
        tools = Tools()
        result = await run(
            Query(question="test", lang="en"), Model(repeat=True), tools, ""
        )
        self.assertEqual(result.reason, "loop_detected")
        self.assertEqual(tools.calls, 2)

    async def test_search_limit(self) -> None:
        tools = Tools()
        result = await run(
            Query(question="test", lang="it"), Model("web_search"), tools, ""
        )
        self.assertEqual(result.reason, "search_limit")
        self.assertEqual(tools.calls, 3)

    def test_invalid_limits(self) -> None:
        constructors: list[Callable[[], Limits]] = [
            lambda: Limits(tokens=16385),
            lambda: Limits(cost=Decimal("-1")),
            lambda: Limits(wall_clock=121),
            lambda: Limits(tool_calls=11),
        ]
        for construct in constructors:
            with self.assertRaises(ValueError):
                construct()

    async def test_fetch_limit(self) -> None:
        class Free(Model):
            def estimate(self, messages: list[Message]) -> Reservation:
                return Reservation(1, Decimal(0))

        model = Free("web_fetch")
        tools = Tools()
        result = await run(Query(question="test", lang="fr"), model, tools, "")
        self.assertEqual((result.reason, tools.calls), ("fetch_limit", 8))

    async def test_usage_reconciliation_and_provider_violation(self) -> None:
        class Metered(Model):
            async def complete(self, messages: list[Message], timeout: float) -> Turn:
                if self.calls:
                    return Turn("answer", usage=Reservation(2, Decimal("0.001")))
                self.calls += 1
                return Turn(
                    "",
                    (Call("1", "calculator", '{"expr":"1"}'),),
                    Reservation(2, Decimal("0.001")),
                )

        result = await run(
            Query(question="test", lang="fr"),
            Metered(),
            Tools(),
            "",
            Limits(tokens=12, cost=Decimal("0.011")),
        )
        self.assertEqual(
            (result.state, result.tokens, result.cost), ("done", 4, Decimal("0.002"))
        )

        class Violation(Model):
            async def complete(self, messages: list[Message], timeout: float) -> Turn:
                return Turn("answer", usage=Reservation(11, Decimal("0.01")))

        result = await run(Query(question="test", lang="fr"), Violation(), Tools(), "")
        self.assertEqual(result.reason, "provider_error")
