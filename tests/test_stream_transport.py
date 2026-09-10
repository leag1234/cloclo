"""Transport uses real recorded frames, yields before completion, closes on cancel."""

from collections.abc import AsyncIterator
from contextlib import aclosing
import os
import unittest
from unittest.mock import patch

from agent_provider import AgentProvider
from serverless_support import environment
from serverless import ServerlessPolicy
from test_streaming_decoder import frame, end


class Content:
    closed = False

    async def iter_chunked(self, size: int) -> AsyncIterator[bytes]:
        yield frame({"content": "Bonjour"})
        yield end()


class Response:
    status = 200
    content = Content()

    async def __aenter__(self) -> "Response":
        return self

    async def __aexit__(self, *args: object) -> None:
        self.content.closed = True


class Session:
    def __init__(self, **kwargs: object) -> None:
        self.response = Response()
        self.response.content = Content()
        self.body: object = None

    async def __aenter__(self) -> "Session":
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    def post(self, url: str, **kwargs: object) -> Response:
        self.body = kwargs["json"]
        return self.response


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_progress_and_close_before_terminal(self) -> None:
        session = Session()
        with (
            patch.dict(
                os.environ,
                environment(),
            ),
            patch("stream_transport.aiohttp.ClientSession", return_value=session),
        ):
            provider = AgentProvider()
            async with aclosing(
                provider.stream(
                    {
                        "messages": [{"role": "user", "content": "Bonjour"}],
                        "tools": [{}],
                        "timeout": 5.0,
                        "local_enabled": False,
                        "reasoning_effort": "low",
                    }
                )
            ) as events:
                self.assertEqual(
                    await events.__anext__(), {"delta": {"content": "Bonjour"}}
                )
                self.assertFalse(session.response.content.closed)
            # Closing outer iterator must close the inner HTTP context too.
            self.assertTrue(session.response.content.closed)
            assert isinstance(session.body, dict)
            self.assertEqual(session.body["max_tokens"], 2048)
            self.assertEqual(session.body["reasoning_effort"], "low")

    async def test_terminal_usage_is_validated(self) -> None:
        session = Session()
        with (
            patch.dict(
                os.environ,
                environment(),
            ),
            patch("stream_transport.aiohttp.ClientSession", return_value=session),
        ):
            events = [
                x
                async for x in AgentProvider().stream(
                    {
                        "messages": [{"role": "user", "content": "Bonjour"}],
                        "tools": [{}],
                        "timeout": 5.0,
                        "observe": True,
                    }
                )
            ]
            self.assertIn("result", events[-1])
            self.assertTrue(session.response.content.closed)

    async def test_task_routing_and_budget_before_transport(self) -> None:
        session = Session()
        with (
            patch.dict(os.environ, environment()),
            patch(
                "stream_transport.aiohttp.ClientSession", return_value=session
            ) as client,
        ):
            request = dict(
                messages=[{"role": "user", "content": "Write Python code"}],
                tools=[{}],
                timeout=5.0,
                observe=True,
                local_enabled=False,
            )
            events = [event async for event in AgentProvider().stream(request)]
            assert isinstance(session.body, dict)
            self.assertEqual(session.body["model"], ServerlessPolicy().models["code"])
            result = events[-1]["result"]
            assert isinstance(result, dict)
            self.assertEqual(result["observation"]["task_type"], "code")
            client.reset_mock()
            request["messages"] = [{"role": "user", "content": "x" * 300000}]
            with self.assertRaises(ValueError):
                _ = [event async for event in AgentProvider().stream(request)]
            client.assert_not_called()

    async def test_fallback_only_before_emission(self) -> None:
        from stream_transport import StreamRequest

        for emitted in (False, True):
            attempts: list[str] = []

            async def upstream(
                request: StreamRequest, model: str, timeout: float
            ) -> AsyncIterator[dict[str, object]]:
                attempts.append(model)
                if len(attempts) == 1:
                    if emitted:
                        yield {"delta": {"content": "first"}}
                    raise RuntimeError("provider_error")
                yield {
                    "result": {
                        "text": "ok",
                        "calls": [],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                    }
                }

            with (
                patch.dict(os.environ, environment()),
                patch("stream_transport.attempt", upstream),
            ):
                payload = dict(
                    messages=[{"role": "user", "content": "Hello"}],
                    tools=[{}],
                    timeout=5.0,
                    observe=True,
                )
                if emitted:
                    with self.assertRaises(RuntimeError):
                        _ = [e async for e in AgentProvider().stream(payload)]
                    self.assertEqual(len(attempts), 1)
                else:
                    result = [e async for e in AgentProvider().stream(payload)][-1][
                        "result"
                    ]
                    assert isinstance(result, dict)
                    self.assertTrue(result["observation"]["fallback"])
                    policy = ServerlessPolicy()
                    self.assertEqual(
                        attempts, [policy.models["text"], policy.models["code"]]
                    )
