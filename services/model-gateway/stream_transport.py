"""Cancellable upstream streaming transport; no retry after emitted deltas."""

from collections.abc import AsyncGenerator
from contextlib import aclosing
import asyncio
import json
import logging
from time import monotonic
import os
from typing import Literal

import aiohttp
from pydantic import ValidationError

from agent_provider import AgentProvider, AgentRequest, classify
from streaming import StreamDecoder
from packages.tool_history import final_messages
from serverless import ServerlessPolicy


class StreamRequest(AgentRequest):
    reasoning_effort: Literal["none", "low", "high"] = "none"


async def stream(
    provider: AgentProvider, payload: object
) -> AsyncGenerator[dict[str, object], None]:
    request = StreamRequest.model_validate(payload)
    if request.profile is not None:
        from quality import stream_quality

        async with aclosing(stream_quality(provider, request)) as events:
            async for event in events:
                yield event
        return
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
    request: AgentRequest, model: str, timeout: float
) -> AsyncGenerator[dict[str, object], None]:
    endpoint = os.environ["SCW_GENERATIVE_BASE_URL"].rstrip("/")
    if not endpoint.startswith("https://"):
        raise ValueError("provider_configuration")
    answer_only = request.profile is not None and request.tool_choice == "none"
    body = {
        "model": model,
        "messages": final_messages(request.messages)
        if answer_only
        else request.messages,
        **(
            {"tools": request.tools, "tool_choice": request.tool_choice}
            if request.tools and not answer_only
            else {}
        ),
        "max_tokens": request.max_tokens,
        "temperature": 0,
        "reasoning_effort": "none",
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    decoder = StreamDecoder(allow_length=request.profile is not None)
    started = monotonic()

    def diagnostic(category: str, **details: object) -> None:
        # Never log provider bodies, exception text, URLs or request content.
        logging.getLogger(__name__).warning(
            json.dumps(
                {
                    "event": "provider_stream_failure",
                    "category": category,
                    "elapsed_seconds": round(monotonic() - started, 3),
                    "received_bytes": decoder.total,
                    "content_chars": len(decoder.text),
                    "reasoning_chars": len(decoder.reasoning),
                    "tool_calls": len(decoder.calls),
                    "finish_reason": decoder.reason,
                    "usage_present": decoder.usage is not None,
                    **details,
                }
            )
        )

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
                    diagnostic("http", status=response.status)
                    raise RuntimeError("provider_error")
                async for piece in response.content.iter_chunked(16384):
                    for event in decoder.feed(piece):
                        yield event
        decoder.finish()
        assert decoder.result is not None
        result = decoder.result
        yield {"result": result}
    except TimeoutError:
        diagnostic("timeout")
        raise
    except aiohttp.ClientError:
        diagnostic("transport")
        raise RuntimeError("provider_error") from None
    except ValueError as exc:
        known = {
            "stream_limit_or_trailing_data",
            "invalid_sse_field",
            "trailing_frame",
            "duplicate_usage",
            "delta_after_finish",
            "tool_limit",
            "output_budget",
            "incomplete_stream",
            "empty_stream",
            "duplicate_call",
            "inconsistent_finish",
            "invalid_reasoning_usage",
        }
        details: dict[str, object] = {}
        if isinstance(exc, ValidationError):
            details["validation_types"] = [
                error["type"]
                for error in exc.errors(
                    include_input=False, include_context=False, include_url=False
                )
            ]
        elif str(exc) in known:
            details["validation_code"] = str(exc)
        diagnostic("validation", **details)
        raise RuntimeError("provider_error") from None
