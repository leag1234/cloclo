"""Launcher shutdown retains data and stops only the UI it started."""

import os
import unittest
from unittest.mock import Mock, patch

from services.orchestrator.serving import main


class ServingTests(unittest.TestCase):
    def test_main_cleanup_on_readiness_failure_and_normal_stop(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "ESCALATION_MODEL": "test-only",
                    "SCW_GENERATIVE_BASE_URL": "https://example.invalid",
                    "SCW_GENERATIVE_API_KEY": "test-only",
                },
            ),
            patch("services.orchestrator.serving.stack"),
            patch("services.orchestrator.serving.webui"),
            patch("services.orchestrator.serving.signal.signal"),
            patch("services.orchestrator.serving.threading.Event", return_value=Mock()),
            patch("services.orchestrator.serving.docker") as docker,
        ):
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
