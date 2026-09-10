"""M7 request constraints are enforced before any provider invocation."""

import unittest
from services.orchestrator.chat_schema import ChatRequest


class ChatSchemaTests(unittest.TestCase):
    def test_request_limits_and_history(self) -> None:
        messages = [
            {"role": "user", "content": "Bonjour"},
            {"role": "assistant", "content": "Salut"},
            {"role": "user", "content": "Traduis cela en allemand."},
        ]
        req = ChatRequest.model_validate(
            {"model": "atlas", "messages": messages, "stream": True, "temperature": 0.2}
        )
        self.assertEqual(len(req.messages), 3)
        self.assertTrue(req.stream)
        for content in ("", " ", "a" * 32001, "control\x00", "\ud800"):
            with (
                self.subTest(content=repr(content[:20])),
                self.assertRaises(ValueError),
            ):
                ChatRequest.model_validate(
                    {"messages": [{"role": "user", "content": content}]}
                )
        payloads: tuple[dict[str, object], ...] = (
            {"messages": []},
            {"messages": messages[:2]},
            {"model": "unknown", "messages": messages},
            {"messages": [{"role": "tool", "content": "unsafe"}]},
            {"messages": [{"role": "user", "content": "x" * 20000}] * 2},
        )
        for payload in payloads:
            with self.assertRaises(ValueError):
                ChatRequest.model_validate(payload)
