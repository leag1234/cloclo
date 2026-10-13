"""B2: recovery asks the model for real files and preserves honest inline content."""

from decimal import Decimal
import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from services.orchestrator.chat_pipeline import process
from services.orchestrator.chat_schema import ChatRequest
from services.orchestrator.interactions import Interaction
from services.orchestrator.loop import Call, Message, Reservation, Result, Turn
from services.orchestrator.model import Configuration, GatewayError, GatewayModel
from services.orchestrator.terminal_client import TerminalClient


class PresentationRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_loop_executes_only_model_selected_creation_and_publication(
        self,
    ) -> None:
        model = GatewayModel(
            "http://127.0.0.1",
            Configuration(
                input_eur_per_mtok=Decimal("1"),
                output_eur_per_mtok=Decimal("1"),
                max_tokens=2048,
                gateway_reserves_quality=True,
            ),
        )
        inline = "Le tri sépare le verre, le papier et les déchets organiques."
        command = "python3 build_slides.py --content '" + inline + "'"
        turns = [
            Turn(inline),
            Turn(
                "",
                (
                    Call(
                        "model-create",
                        "terminal_command",
                        json.dumps({"command": command}),
                    ),
                    Call(
                        "model-publish",
                        "publish_document",
                        '{"path":"tri.pptx","strategy":"created"}',
                    ),
                ),
            ),
            Turn("La présentation sur le tri est disponible."),
        ]
        messages_seen = []

        async def complete(messages: list[Message], timeout: float) -> Turn:
            messages_seen.append(messages)
            model.spent += Decimal("0.01")
            turn = turns.pop(0)
            return Turn(turn.text, turn.calls, Reservation(1, Decimal("0.01")))

        async def publish(
            client: TerminalClient, path: str, strategy: str, timeout: float
        ) -> dict[str, object]:
            url = "/api/v1/terminals/atlas-files/files/serve/request/" + path
            client.files.append(url)
            client.strategies.append(strategy)
            return {"download_url": url}

        with (
            tempfile.TemporaryDirectory() as root,
            patch.dict(
                os.environ,
                {"ATLAS_TERMINAL_ENABLED": "1", "ATLAS_WEB_CACHE": root + "/cache"},
            ),
            patch.object(GatewayModel, "connect", AsyncMock(return_value=model)),
            patch.object(model, "complete", complete),
            patch.object(TerminalClient, "initialize", AsyncMock()),
            patch.object(
                TerminalClient, "execute", AsyncMock(return_value={"exit_code": 0})
            ) as execute,
            patch.object(TerminalClient, "publish", publish),
        ):
            item = Interaction()
            await process(
                ChatRequest.model_validate(
                    {
                        "messages": [
                            {
                                "role": "user",
                                "content": "Crée une présentation PPTX sur le tri.",
                            }
                        ]
                    }
                ),
                item,
            )
        execute.assert_awaited_once()
        assert execute.await_args is not None
        self.assertEqual(execute.await_args.args[0], command)
        self.assertEqual(len(messages_seen), 3)
        self.assertIn({"role": "assistant", "content": inline}, messages_seen[1])
        self.assertEqual(len(item.files), 1)
        self.assertIn(item.files[0], item.reponse)
        self.assertAlmostEqual(item.cout_eur, 0.03)
        self.assertNotIn("solution de secours", item.reponse)

    async def recover(
        self,
        language: str = "fr",
        second: Result | GatewayError | None = None,
        cost: Decimal = Decimal("0.04"),
    ) -> tuple[Interaction, AsyncMock, str]:
        model = GatewayModel(
            "http://127.0.0.1",
            Configuration(
                input_eur_per_mtok=Decimal("1"),
                output_eur_per_mtok=Decimal("1"),
                max_tokens=2048,
            ),
        )
        request = ChatRequest.model_validate(
            {"messages": [{"role": "user", "content": "Create a PPTX and PDF"}]}
        )
        # Long, distinctive answer content must survive without truncation or filler.
        inline = "\n".join(f"Section {n}: αβγ {language}" for n in range(800))
        runner = AsyncMock(
            side_effect=[
                Result(text=inline, state="done", cost=cost, tool_calls=4),
                second
                if second is not None
                else Result(text="", state="stopped", reason="cost"),
            ]
        )
        with (
            tempfile.TemporaryDirectory() as root,
            patch.dict(
                os.environ,
                {"ATLAS_TERMINAL_ENABLED": "1", "ATLAS_WEB_CACHE": root + "/cache"},
            ),
            patch.object(GatewayModel, "connect", AsyncMock(return_value=model)),
            patch.object(TerminalClient, "initialize", AsyncMock()),
            patch("services.orchestrator.chat_pipeline.run", runner),
            patch(
                "services.orchestrator.chat_pipeline.conversation_language",
                return_value=language,
            ),
        ):
            item = Interaction()
            await process(request, item)
        return item, runner, inline

    async def test_recovery_invokes_model_without_placeholder_script(self) -> None:
        _, runner, inline = await self.recover()
        self.assertEqual(runner.await_count, 2)
        recovery = runner.await_args_list[1]
        self.assertFalse(recovery.kwargs.get("initial_calls"))
        self.assertIn(
            {"role": "assistant", "content": inline}, recovery.kwargs["history"]
        )
        model = recovery.args[1]
        self.assertEqual(
            {tool["function"]["name"] for tool in model.tools},
            {"terminal_command", "publish_document"},
        )
        self.assertEqual(recovery.args[0].lang, "fr")
        self.assertIn("terminal_command", recovery.args[3])
        self.assertIn("publish_document", recovery.args[3])

    async def test_inline_fallback_keeps_real_answer_and_request_language(self) -> None:
        for language, notice in (
            ("fr", "Aucun fichier"),
            ("de", "Keine Datei"),
            ("es", "ningún archivo"),
            ("it", "Nessun file"),
            ("en", "No file was produced"),
        ):
            with self.subTest(language=language):
                item, _, inline = await self.recover(language)
                self.assertIn(inline, item.reponse)
                self.assertIn(notice, item.reponse)
                self.assertEqual(item.files, [])
                self.assertEqual(item.state, "done")
                self.assertNotIn("Requested presentation", item.reponse)
                if language != "en":
                    self.assertNotIn("No file was produced", item.reponse)

    async def test_recovery_uses_remaining_cost_tools_and_original_deadline(
        self,
    ) -> None:
        item, runner, _ = await self.recover(
            second=Result(text="Recovery answer", state="done", cost=Decimal("0.02"))
        )
        first, recovery = runner.await_args_list
        self.assertEqual(recovery.args[4].cost, Decimal("0.26"))
        self.assertEqual(recovery.args[4].tool_calls, 6)
        self.assertLessEqual(recovery.args[4].wall_clock, first.args[4].wall_clock)
        self.assertAlmostEqual(item.cout_eur, 0.06)

    async def test_exhausted_budget_keeps_content_without_retry(self) -> None:
        item, runner, inline = await self.recover(cost=Decimal("0.30"))
        self.assertEqual(runner.await_count, 1)
        self.assertIn(inline, item.reponse)
        self.assertIn("Aucun fichier", item.reponse)

    async def test_recovery_provider_failure_preserves_real_content(self) -> None:
        item, runner, inline = await self.recover(
            second=GatewayError("provider_error", 502, "Provider failed")
        )
        self.assertEqual(runner.await_count, 2)
        self.assertIn(inline, item.reponse)
        self.assertIn("Aucun fichier", item.reponse)
        self.assertIn("provider_error", item.erreurs)
        self.assertEqual(item.files, [])

    async def test_unpublished_recovery_link_never_replaces_real_content(self) -> None:
        item, _, inline = await self.recover(
            second=Result(
                text="Your file exists: [presentation.pdf](sandbox:/presentation.pdf)",
                state="done",
            )
        )
        self.assertIn(inline, item.reponse)
        self.assertNotIn("sandbox:", item.reponse)
        self.assertNotIn("Your file exists", item.reponse)
        self.assertEqual(item.files, [])


class PreservedPresentationTests(unittest.TestCase):
    def test_published_bytes_survive_harness_cleanup(self) -> None:
        from pathlib import Path
        from m26_live import preserve_files

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            url = "/api/v1/terminals/atlas-files/files/serve/request/slides.pdf"
            raw = b"published document bytes"
            with patch("daily_probe.download", return_value=raw) as download:
                artifacts = preserve_files(root, "J54", [url])
            download.assert_called_once_with(url)
            self.assertEqual(Path(artifacts[0]["path"]).read_bytes(), raw)
            self.assertEqual(artifacts[0]["bytes"], len(raw))

    def test_copy_failure_is_recorded_without_claiming_a_file_exists(self) -> None:
        from pathlib import Path
        from m26_live import preserve_files

        with tempfile.TemporaryDirectory() as directory:
            with patch("daily_probe.download", side_effect=OSError("unavailable")):
                artifacts = preserve_files(Path(directory), "J54", ["missing.pdf"])
            self.assertEqual(artifacts[0]["copy_error"], "OSError")
            self.assertNotIn("path", artifacts[0])
