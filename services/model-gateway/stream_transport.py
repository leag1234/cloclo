"""Cancellable upstream streaming transport; no retry after emitted deltas."""

from collections.abc import AsyncGenerator
from contextlib import aclosing
import asyncio
import json
import logging
from time import monotonic
import os

import aiohttp
from typing import Literal

from agent_provider import AgentProvider, AgentRequest, classify
from streaming import StreamDecoder
from serverless import ServerlessPolicy


class StreamRequest(AgentRequest):
    reasoning_effort: Literal["none", "low"] = "none"


async def stream(
    provider: AgentProvider, payload: object
) -> AsyncGenerator[dict[str, object], None]:
    request = StreamRequest.model_validate(payload)
    policy = ServerlessPolicy()
    plan = policy.reserve(request.messages, request.tools)
    started = monotonic()
    for index, model in enumerate((plan.primary, plan.fallback)):
        sent = False
        remaining = request.timeout - (monotonic() - started)
        if remaining <= 0:
            raise TimeoutError("timeout")
        allotted = remaining * 0.7 if index == 0 else remaining
        try:
            async with (
                asyncio.timeout(allotted),
                aclosing(attempt(request, model, allotted)) as events,
            ):
                async for event in events:
                    result = event.get("result")
                    if isinstance(result, dict):
                        if request.observe:
                            result["observation"] = {
                                "provider": "escalade",
                                "route": "simple"
                                if classify(request.messages) == "chat_simple"
                                else "complexe",
                                "task_type": plan.task_type,
                                "fallback": bool(index),
                            }
                        usage = result["usage"]
                        logging.getLogger(__name__).info(
                            json.dumps(
                                {
                                    "event": "serverless_stream_usage",
                                    "task_type": plan.task_type,
                                    "tokens": usage,
                                    "fallback": bool(index),
                                    "cost_eur": str(
                                        policy.cost(
                                            model,
                                            usage["prompt_tokens"],
                                            usage["completion_tokens"],
                                        )
                                    ),
                                    "reserved_unknown_eur": str(
                                        plan.primary_bound if index else 0
                                    ),
                                }
                            )
                        )
                        yield event
                        return
                    sent = True
                    yield event
        except (RuntimeError, TimeoutError):
            logging.getLogger(__name__).info(
                json.dumps(
                    {
                        "event": "serverless_stream_failed",
                        "task_type": plan.task_type,
                        "attempt": index + 1,
                        "reserved_eur": str(plan.reserved_eur),
                    }
                )
            )
            if sent or index:
                raise


async def attempt(
    request: StreamRequest, model: str, timeout: float
) -> AsyncGenerator[dict[str, object], None]:
    endpoint = os.environ["SCW_GENERATIVE_BASE_URL"].rstrip("/")
    if not endpoint.startswith("https://"):
        raise ValueError("provider_configuration")
    body = {
        "model": model,
        "messages": request.messages,
        "tools": request.tools,
        **({"tool_choice": "auto"} if request.tools else {}),
        "max_tokens": 2048,
        "temperature": 0,
        "reasoning_effort": request.reasoning_effort,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    decoder = StreamDecoder()
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout), trust_env=False
        ) as session:
            async with session.post(
                endpoint + "/chat/completions",
                json=body,
                headers={
                    "Authorization": "Bearer " + os.environ["SCW_GENERATIVE_API_KEY"]
                },
                allow_redirects=False,
            ) as response:
                if response.status != 200:
                    raise RuntimeError("provider_error")
                async for piece in response.content.iter_chunked(16384):
                    for event in decoder.feed(piece):
                        yield event
        decoder.finish()
        assert decoder.result is not None
        result = decoder.result
        yield {"result": result}
    except (aiohttp.ClientError, ValueError):
        raise RuntimeError("provider_error") from None
