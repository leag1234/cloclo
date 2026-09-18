"""M24 stack wiring and least-privilege UI connection contract."""

import json
import os
import unittest
from unittest.mock import patch

from services.orchestrator import serving


class TerminalLifecycleTests(unittest.TestCase):
    def test_ui_uses_shared_network_and_runtime_key(self) -> None:
        with (
            patch.dict(os.environ, {"OPEN_TERMINAL_API_KEY": "test-only"}),
            patch(
                "services.orchestrator.terminal_stack.network_gateway",
                return_value="172.30.0.1",
            ),
            patch.object(serving, "docker_run") as run,
        ):
            serving.webui("test-ui", False)
            connection = json.loads(os.environ["TERMINAL_SERVER_CONNECTIONS"])[0]
        options = run.call_args.args[2]
        self.assertEqual(options[options.index("--network") + 1], "atlas-files")
        self.assertNotIn("-p", options)
        self.assertIn("HOST=0.0.0.0", options)
        self.assertIn("OPENAI_API_BASE_URL=http://172.30.0.1:8020/v1", options)
        self.assertIn("TERMINAL_SERVER_CONNECTIONS", options)
        self.assertEqual(connection["url"], "http://open-terminal:8000")
        self.assertEqual(connection["config"]["chat_uploads"], "filesystem")
        self.assertEqual(connection["key"], "test-only")
