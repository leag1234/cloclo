"""Launcher shutdown retains data and stops only the UI it started."""

from contextlib import nullcontext
import os
import unittest
from unittest.mock import Mock, patch

from services.orchestrator.serving import main


class ServingTests(unittest.TestCase):
    def test_main_cleanup_on_readiness_failure_and_normal_stop(self) -> None:
        event = Mock()
        event.set.side_effect = RuntimeError("signal handler must not acquire locks")
        with (
            patch.dict(
                os.environ,
                {
                    "ESCALATION_MODEL": "test-only",
                    "SCW_GENERATIVE_BASE_URL": "https://example.invalid",
                    "SCW_GENERATIVE_API_KEY": "test-only",
                    "TAVILY_API_KEY": "test-only",
                    "ATLAS_SEARCH_PROVIDER": "tavily",
                },
            ),
            patch(
                "services.orchestrator.serve_owner.ownership",
                return_value=nullcontext(),
            ),
            patch("services.orchestrator.serving.stack"),
            patch(
                "services.orchestrator.terminal_stack.terminal",
                return_value=nullcontext(),
            ),
            patch(
                "services.orchestrator.terminal_stack.loopback_forward",
                return_value=nullcontext(),
            ),
            patch("services.orchestrator.terminal_stack.adapter_socket"),
            patch("services.orchestrator.serving.uvicorn.Server"),
            patch("services.orchestrator.serving.threading.Thread"),
            patch("services.orchestrator.serving.webui"),
            patch("services.orchestrator.serving.configure"),
            patch(
                "services.orchestrator.serving.signal.signal",
                side_effect=lambda sig, handler: handler(sig, None),
            ),
            patch("services.orchestrator.serving.threading.Event", return_value=event),
            patch("services.orchestrator.serving.docker") as docker,
        ):
            docker.side_effect = (
                lambda *args: '[{"NetworkSettings":{"Networks":{"atlas-files":{"IPAddress":"172.30.0.2"}}}}]'
                if args[0] == "inspect"
                else ""
            )
            for error in (None, RuntimeError("service_start_timeout")):
                with patch(
                    "services.orchestrator.serving.wait_http", side_effect=error
                ):
                    if error:
                        with self.assertRaises(RuntimeError):
                            main()
                    else:
                        main()
                docker.assert_called_with("stop", "atlas-chat-ui")
            with patch.dict(os.environ, {"ESCALATION_MODEL": ""}):
                with self.assertRaisesRegex(RuntimeError, "missing_configuration"):
                    main()
