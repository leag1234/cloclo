"""Image selection cannot reset the parent request's money or time allowance."""

from decimal import Decimal
import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

import imagegen
from services.orchestrator.chat_pipeline import ChatTools, process
from services.orchestrator.chat_schema import ChatMessage, ChatRequest
from services.orchestrator.interactions import Interaction
from services.orchestrator.loop import Call, Reservation, Turn
from services.orchestrator.model import Configuration, GatewayModel
from test_imagegen import png


class ImageToolBudgetTests(unittest.IsolatedAsyncioTestCase):
    async def test_decision_and_image_share_one_budget(self) -> None:
        for spent in (Decimal("0.07"), Decimal("0.10")):
            model = GatewayModel(
                "http://unused",
                Configuration(
                    input_eur_per_mtok=Decimal(0),
                    output_eur_per_mtok=Decimal(0),
                    max_tokens=100,
                ),
            )
            decision = AsyncMock(
                return_value=Turn(
                    "",
                    (
                        Call(
                            "image",
                            "generate_image",
                            json.dumps({"prompt": "dessine-moi un mouton"}),
                        ),
                    ),
                    Reservation(10, spent),
                )
            )
            image = AsyncMock(return_value={"image": png(), "cost_eur": 0.001})
            item = Interaction()
            with (
                patch.object(GatewayModel, "connect", AsyncMock(return_value=model)),
                patch.object(
                    model,
                    "estimate",
                    Mock(return_value=Reservation(100, Decimal("0.10"))),
                ),
                patch.object(model, "complete", decision),
                patch.object(GatewayModel, "post", image),
            ):
                request = ChatRequest(
                    messages=[ChatMessage(role="user", content="dessine-moi un mouton")]
                )
                if spent == Decimal("0.10"):
                    with self.assertRaisesRegex(RuntimeError, "cost_budget"):
                        await process(request, item)
                    image.assert_not_awaited()
                    self.assertEqual(item.cout_eur, 0.10)
                else:
                    await process(request, item)
                    payload = image.call_args.args[1]
                    self.assertEqual(Decimal(payload["max_cost_eur"]), Decimal("0.03"))
                    self.assertLess(payload["timeout"], 120)
                    self.assertEqual(payload["lang"], "fr")
                    self.assertAlmostEqual(item.cout_eur, 0.071)
            self.assertEqual(decision.await_count, 1)

    async def test_selected_model_image_uses_parent_deadline_and_operation_cap(
        self,
    ) -> None:
        from services.orchestrator.image_tool import finish
        from services.orchestrator.loop import Result

        request = ChatRequest(
            model="atlas-glm",
            messages=[ChatMessage(role="user", content="dessine-moi un mouton")],
        )
        item = Interaction()
        with (
            patch("services.orchestrator.image_tool.monotonic", return_value=30.0),
            patch(
                "services.orchestrator.image_tool.process_image", AsyncMock()
            ) as generate,
        ):
            await finish(request, item, Result(cost=Decimal("0.02")), "a sheep", 10.0)
        self.assertEqual(generate.call_args.kwargs["budget"], Decimal("0.05"))
        self.assertEqual(generate.call_args.kwargs["timeout"], 100.0)
        self.assertEqual(item.cout_eur, 0.02)

    async def test_rewrite_reservation_must_fit_remaining_budget(self) -> None:
        with (
            patch.dict(
                "os.environ",
                {"ATLAS_IMAGE_GPU_IP": "127.0.0.1", "ATLAS_IMAGE_GPU_EUR_H": "1.46988"},
            ),
            patch.object(imagegen, "reservation", return_value=Decimal("0.01")),
            patch.object(imagegen, "rewrite", AsyncMock()) as rewrite,
        ):
            with self.assertRaisesRegex(RuntimeError, "cost_budget"):
                await imagegen.generate({"prompt": "a cube", "max_cost_eur": "0.005"})
            rewrite.assert_not_awaited()

    async def test_invalid_or_disabled_image_tool_never_selects_generation(
        self,
    ) -> None:
        for enabled, arguments in [
            (False, {"prompt": "a cube"}),
            (True, {"prompt": "a cube", "seed": 1}),
            (True, {"prompt": ""}),
        ]:
            tools = ChatTools(Interaction(), allow_image=enabled)
            result = await tools.execute(
                Call("image", "generate_image", json.dumps(arguments)), 10
            )
            self.assertIn("error", result)
            self.assertIsNone(tools.image_prompt)
