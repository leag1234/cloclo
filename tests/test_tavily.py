"""Search content, provider quota separation and safe failures (M24/D8)."""

from collections.abc import AsyncIterator
from decimal import Decimal
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from services.orchestrator.cache import Cache
from services.orchestrator.tools import Fetch, Runtime, Search


class TavilyTests(unittest.IsolatedAsyncioTestCase):
    async def test_content_reused_without_fetch_and_provider_key_not_cached(
        self,
    ) -> None:
        async def pieces(size: int) -> AsyncIterator[bytes]:
            yield json.dumps(
                {
                    "results": [
                        {
                            "title": "CPC timing",
                            "url": "https://example.org/timing",
                            "content": "Machine-specific timing evidence.",
                        }
                    ]
                }
            ).encode()

        response = MagicMock(status=200)
        response.content.iter_chunked = pieces
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=response)
        session = MagicMock()
        session.post.return_value = context
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=session)
        with (
            tempfile.TemporaryDirectory() as root,
            patch.dict(
                os.environ,
                {
                    "ATLAS_SEARCH_PROVIDER": "tavily",
                    "TAVILY_API_KEY": "test-only-secret",
                },
            ),
            patch(
                "services.orchestrator.tools.aiohttp.ClientSession", return_value=client
            ),
        ):
            cache = Cache(Path(root) / "cache.sqlite")
            runtime = Runtime(cache, Decimal(0))
            request = Search(query="CPC timings", lang="fr")
            result = await runtime.search(request, 1)
            self.assertEqual(result["provider"], "tavily")
            self.assertIn("Machine-specific", str(result))
            self.assertNotIn("test-only-secret", str(result))
            again = await runtime.search(request, 1)
            self.assertEqual(result, again)
            self.assertEqual(session.post.call_count, 1)
            self.assertEqual(
                session.post.call_args.kwargs["json"]["api_key"], "test-only-secret"
            )
            with patch.object(
                runtime.web,
                "fetch",
                new=AsyncMock(side_effect=AssertionError("must not refetch")),
            ) as fetch:
                page = await runtime.fetch(Fetch(url="https://example.org/timing"), 1)
            self.assertIn("Machine-specific", str(page))
            fetch.assert_not_awaited()
            self.assertNotIn(b"test-only-secret", cache.path.read_bytes())

    async def test_provider_failure_and_unknown_switch_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            runtime = Runtime(Cache(Path(root) / "cache.sqlite"), Decimal(0))
            with (
                patch.dict(os.environ, {"ATLAS_SEARCH_PROVIDER": "unknown"}),
                patch(
                    "services.orchestrator.tools.aiohttp.ClientSession",
                    side_effect=AssertionError("network must not be called"),
                ),
            ):
                with self.assertRaisesRegex(ValueError, "invalid_search_provider"):
                    await runtime.search(Search(query="x", lang="en"), 1)

    async def test_monthly_provider_quotas_are_independent(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            cache = Cache(Path(root) / "cache.sqlite")
            for _ in range(900):
                cache.reserve_search()
            with self.assertRaisesRegex(ValueError, "quota_exceeded"):
                cache.reserve_search()
            cache.reserve_search("tavily")

    async def test_failed_search_stops_before_memory_answer(self) -> None:
        from services.orchestrator.chat_pipeline import ChatTools
        from services.orchestrator.interactions import Interaction
        from services.orchestrator.loop import Call
        from services.orchestrator.model import GatewayError

        with (
            tempfile.TemporaryDirectory() as root,
            patch.dict(
                os.environ,
                {
                    "ATLAS_SEARCH_PROVIDER": "tavily",
                    "ATLAS_WEB_CACHE": root + "/cache.sqlite",
                },
            ),
        ):
            item = Interaction()
            tools = ChatTools(item)
            with patch.object(
                Runtime,
                "execute",
                new=AsyncMock(return_value={"error": "quota_exceeded"}),
            ):
                with self.assertRaisesRegex(
                    GatewayError, "search_unavailable"
                ) as caught:
                    await tools.execute(
                        Call("search", "web_search", '{"query":"CPC","lang":"fr"}'), 1
                    )
            self.assertIn("quota exhausted", caught.exception.detail)
            self.assertIn("quota_exceeded", item.erreurs)

    async def test_http_quota_failure_and_oversize_response(self) -> None:
        from services.orchestrator.loop import Call

        cases = [
            (429, b"provider-private-detail", "quota_exceeded"),
            (401, b"provider-private-detail", "search_unavailable"),
            (200, b'{"results": "wrong"}', "invalid_search_response"),
            (200, b"x" * 2000001, "response_too_large"),
        ]
        for status, body, expected in cases:

            async def pieces(size: int) -> AsyncIterator[bytes]:
                yield body

            response = MagicMock(status=status)
            response.content.iter_chunked = pieces
            context = MagicMock()
            context.__aenter__ = AsyncMock(return_value=response)
            session = MagicMock()
            session.post.return_value = context
            client = MagicMock()
            client.__aenter__ = AsyncMock(return_value=session)
            with (
                self.subTest(status=status, expected=expected),
                tempfile.TemporaryDirectory() as root,
                patch.dict(
                    os.environ,
                    {
                        "ATLAS_SEARCH_PROVIDER": "tavily",
                        "TAVILY_API_KEY": "test-only-secret",
                    },
                ),
                patch(
                    "services.orchestrator.tools.aiohttp.ClientSession",
                    return_value=client,
                ),
            ):
                runtime = Runtime(Cache(Path(root) / "cache.sqlite"), Decimal(0))
                result = await runtime.execute(
                    Call("search", "web_search", '{"query":"CPC","lang":"en"}'), 1
                )
                self.assertEqual(result, {"error": expected})
