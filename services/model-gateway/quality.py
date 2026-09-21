"""M21 profiles share one ledger and at most one affordable recovery attempt."""

from collections.abc import AsyncGenerator
from contextlib import aclosing
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING
import json
import asyncio
import copy
import logging
from time import monotonic
from pathlib import Path

from agent_provider import AgentProvider, AgentRequest, Usage, classify
from packages.context_limit import ContextExceeded
from provider_retry import RetryLedger, TransientProviderError, retry_stream
from packages.limits import LimitError, ProviderLimitError

from packages.tool_history import (
    final_messages,
    is_history_answer,
    possible_history_answer,
)
from packages.profiles import PROFILES
from packages.evidence import estimated_tokens
from packages.images import image_info
from serverless import ServerlessPolicy, classify_task


def input_bound(
    messages: list[dict[str, object]], tools: list[dict[str, object]]
) -> int:
    normalized = copy.deepcopy(messages)
    pixel_tokens = count = byte_count = pixels = 0
    for message in normalized:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "image_url":
                continue
            image = part.get("image_url")
            if not isinstance(image, dict) or not isinstance(image.get("url"), str):
                raise ValueError("invalid_image")
            info = image_info(image["url"])
            width, height = int(info["width"]), int(info["height"])
            pixel_tokens += ((width + 15) // 16 + 1) * ((height + 15) // 16) + 1
            count += 1
            byte_count += int(info["bytes"])
            pixels += width * height
            image["url"] = "[image]"
    for measured, maximum, unit in (
        (count, 4, "images"),
        (byte_count, 4 * 1024 * 1024, "bytes"),
        (pixels, 16000000, "pixels"),
    ):
        if measured > maximum:
            raise LimitError("image_size_exceeded", measured, maximum, unit)
    # Reserve the larger representation before I/O, including answer-only JSON
    # escaping. Tool schemas are retained in this bound even if not transmitted.
    return (
        max(
            len(
                json.dumps(
                    {"messages": value, "tools": tools}, ensure_ascii=False
                ).encode()
            )
            for value in (normalized, final_messages(normalized))
        )
        + 256
        + pixel_tokens
        + (1024 if count else 0)
    )


async def complete(provider: AgentProvider, request: AgentRequest) -> dict[str, object]:
    async with aclosing(stream_quality(provider, request)) as events:
        async for event in events:
            result = event.get("result")
            if isinstance(result, dict):
                return result
    raise RuntimeError("provider_response_invalid")


async def stream_quality(
    provider: AgentProvider, request: AgentRequest
) -> AsyncGenerator[dict[str, object], None]:
    from stream_transport import attempt

    policy = ServerlessPolicy()
    task = classify_task(request.messages)
    role = (
        "vision"
        if task == "vision"
        else policy.public_profiles.get(request.profile or "", task)
    )
    primary = policy.models[role]
    fallback_role = policy.config[role]["fallback"]
    budget = Decimal(request.budget_eur or "0.10")
    incoming = input_bound(request.messages, request.tools)
    spent = Decimal(0)
    prompt_tokens = completion_tokens = trace_tokens = answer_tokens = 0
    retry_completion_tokens = 0
    reasoning = ""
    estimated = retried = fallback = False
    started = monotonic()
    current = request
    model = primary
    # A large evidence input can exceed the primary's conservative reservation
    # even when the configured alternate can answer within the same ledger.
    alternate = policy.models[fallback_role]
    if policy.cost(model, incoming, 1) > budget:
        selected = None
        if policy.cost(alternate, incoming, 1) <= budget:
            selected = fallback_role
        elif task != "vision":
            # Preserve complete attachment context when both configured expert
            # roles exceed the cap. Only already configured public text roles are
            # eligible; no input sampling or larger cost allowance is permitted.
            affordable_roles = [
                candidate
                for candidate in dict.fromkeys(policy.public_profiles.values())
                if incoming + 1
                <= policy.config[candidate]["capabilities"][policy.models[candidate]][
                    "context"
                ]
                and policy.cost(policy.models[candidate], incoming, 1) <= budget
            ]
            if affordable_roles:
                selected = min(
                    affordable_roles,
                    key=lambda candidate: policy.cost(
                        policy.models[candidate], incoming, request.max_tokens
                    ),
                )
                fallback_role = policy.config[selected]["fallback"]
        if selected is not None:
            role, model = selected, policy.models[selected]
            fallback = True
            logging.getLogger(__name__).info(
                json.dumps(
                    {"event": "quality_affordable_alternate", "budget_eur": str(budget)}
                )
            )
    # Research is optional once another selection turn plus the full-context
    # answer no longer fit. Keep all acquired evidence and the selected effort.
    # File operations are the requested deliverable, so an answer-only turn
    # cannot substitute for them. Each attempt still reserves its full bound
    # below; lacking funds must stop explicitly rather than promise a file.
    file_tools = any(
        isinstance(function := tool.get("function"), dict)
        and function.get("name") in {"terminal_command", "publish_document"}
        for tool in request.tools
    )
    evidence_without_tools = not request.tools and any(
        message.get("role") == "tool" for message in request.messages
    )
    if evidence_without_tools or (
        request.tools
        and not file_tools
        and (
            policy.cost(model, incoming, request.max_tokens)
            + policy.cost(model, incoming, 3000)
            > budget
        )
    ):
        request = request.model_copy(
            update={
                "tool_choice": "none",
                # Research finalization presupposes acquired evidence. Before
                # any tool result, preserve the original task and disposition.
                "messages": [
                    *request.messages,
                    *(
                        [
                            {
                                "role": "system",
                                "content": Path(
                                    "prompts/budget-answer.txt"
                                ).read_text(),
                            }
                        ]
                        if any(m.get("role") == "tool" for m in request.messages)
                        else []
                    ),
                ],
            }
        )
        current = request
        incoming = input_bound(request.messages, request.tools)
        logging.getLogger(__name__).info(
            json.dumps({"event": "quality_answer_budget", "remaining_eur": str(budget)})
        )
    for index in range(2):
        remaining = request.timeout - (monotonic() - started)
        if remaining <= 0:
            raise TimeoutError("timeout")
        # Retain room for one bounded recovery, not all future tool turns.
        # Actual cost is reserved immediately before each transport call.
        recovery = (
            policy.cost(policy.models[fallback_role], incoming, 1000)
            if index == 0
            else Decimal(0)
        )
        if (
            index == 0
            and request.profile == PROFILES[0]
            and recovery + policy.cost(model, incoming, current.max_tokens)
            > budget - spent
        ):
            recovery = Decimal(0)
        if recovery + policy.cost(model, incoming, 1) > budget - spent:
            recovery = Decimal(0)
        if (
            index
            or policy.cost(model, incoming, current.max_tokens)
            > budget - spent - recovery
        ):
            available = budget - spent - recovery - policy.cost(model, incoming, 0)
            price = policy.cost(model, 0, 1)
            affordable = (
                int((available / price).to_integral_value(rounding=ROUND_FLOOR))
                if price
                else 3000
            )
            if affordable < 1:
                raise ProviderLimitError(
                    "cost_budget",
                    int(
                        (policy.cost(model, incoming, 1) * 1_000_000).to_integral_value(
                            rounding=ROUND_CEILING
                        )
                    ),
                    int(
                        ((budget - spent) * 1_000_000).to_integral_value(
                            rounding=ROUND_FLOOR
                        )
                    ),
                    "microEUR",
                )
            current = request.model_copy(
                update={
                    "max_tokens": min(
                        3000 if index else request.max_tokens, affordable
                    ),
                    "reasoning_effort": "none" if index else request.reasoning_effort,
                }
            )
        reserved = policy.cost(model, incoming, current.max_tokens)
        if spent + reserved > budget:
            raise ProviderLimitError(
                "cost_budget",
                int(
                    ((spent + reserved) * 1_000_000).to_integral_value(
                        rounding=ROUND_CEILING
                    )
                ),
                int((budget * 1_000_000).to_integral_value(rounding=ROUND_FLOOR)),
                "microEUR",
            )
        capabilities = policy.config[role]["capabilities"][model]
        if incoming + current.max_tokens > capabilities["context"]:
            raise ContextExceeded(
                incoming + current.max_tokens, capabilities["context"]
            )
        visible_content = False
        buffered: list[dict[str, object]] = []
        prefix = ""
        prefix_open = True
        partial_reasoning = ""
        result: dict[str, object] | None = None
        # Reserve time for recovery, still under the original request deadline.
        allotted = remaining * 0.8 if index == 0 else remaining
        retry_ledger = RetryLedger()
        try:
            async with (
                asyncio.timeout(allotted),
                aclosing(
                    retry_stream(
                        attempt,
                        current,
                        model,
                        allotted,
                        budget - spent,
                        incoming,
                        retry_ledger,
                    )
                ) as events,
            ):
                async for event in events:
                    terminal = event.get("result")
                    if isinstance(terminal, dict):
                        result = terminal
                        break
                    delta = event.get("delta")
                    if isinstance(delta, dict):
                        if isinstance(delta.get("reasoning_content"), str):
                            partial_reasoning += str(delta["reasoning_content"])
                    if isinstance(delta, dict) and delta.get("content"):
                        if current.max_tokens < request.max_tokens:
                            buffered.append(event)
                            continue
                        if prefix_open:
                            prefix += str(delta["content"])
                            buffered.append(event)
                            if possible_history_answer(prefix):
                                continue
                            prefix_open = False
                            for pending_event in buffered:
                                yield pending_event
                            buffered.clear()
                            visible_content = True
                            continue
                        visible_content = True
                    yield event
            if result is None:
                raise RuntimeError("provider_response_invalid")
        except ProviderLimitError:
            raise
        except (RuntimeError, TimeoutError) as exc:
            spent += retry_ledger.spent
            prompt_tokens += retry_ledger.prompt_tokens
            completion_tokens += retry_ledger.completion_tokens
            retry_completion_tokens += retry_ledger.completion_tokens
            failed_usage = (
                exc.usage if isinstance(exc, TransientProviderError) else None
            )
            if failed_usage is not None:
                if (
                    failed_usage.prompt_tokens > incoming
                    or failed_usage.completion_tokens > current.max_tokens
                ):
                    raise RuntimeError("provider_usage_exceeds_reservation") from None
                spent += policy.cost(
                    model, failed_usage.prompt_tokens, failed_usage.completion_tokens
                )
                prompt_tokens += failed_usage.prompt_tokens
                completion_tokens += failed_usage.completion_tokens
                retry_completion_tokens += failed_usage.completion_tokens
                estimated |= retry_ledger.estimated
            else:
                spent += reserved
                prompt_tokens += incoming
                completion_tokens += current.max_tokens
                estimated = True
            # Keep the trace actually shown before an interrupted attempt.
            # Its token count is estimated; unknown billing stays fully reserved.
            reasoning += partial_reasoning
            trace_tokens += estimated_tokens(partial_reasoning)
            logging.getLogger(__name__).warning(
                json.dumps(
                    {
                        "event": "quality_attempt_failed",
                        "category": "timeout"
                        if isinstance(exc, TimeoutError)
                        else "provider",
                        "attempt": index + 1,
                        "elapsed_seconds": round(monotonic() - started, 3),
                        "reserved_unknown_eur": str(spent),
                        "final_usage_measured": failed_usage is not None,
                        "visible_content": visible_content,
                    }
                )
            )
            if index or visible_content:
                raise
            role = fallback_role
            model = policy.models[role]
            fallback = True
            retried = False
            yield {"phase": "reasoning_fallback" if retried else "provider_fallback"}
            continue
        spent += retry_ledger.spent
        prompt_tokens += retry_ledger.prompt_tokens
        completion_tokens += retry_ledger.completion_tokens
        retry_completion_tokens += retry_ledger.completion_tokens
        estimated |= retry_ledger.estimated
        usage = Usage.model_validate(result["usage"])
        if (
            usage.prompt_tokens > incoming
            or usage.completion_tokens > current.max_tokens
        ):
            raise RuntimeError("provider_usage_exceeds_reservation")
        spent += policy.cost(model, usage.prompt_tokens, usage.completion_tokens)
        prompt_tokens += usage.prompt_tokens
        completion_tokens += usage.completion_tokens
        trace = str(result.get("reasoning", ""))
        reasoning += trace
        count = result.get("reasoning_tokens")
        if type(count) is not int:
            estimated |= bool(trace)
            count = (
                max(
                    0,
                    usage.completion_tokens
                    - estimated_tokens(str(result.get("text", ""))),
                )
                if trace
                else 0
            )
        trace_tokens += count
        answer_tokens += usage.completion_tokens - count
        malformed_arguments = False
        calls = result.get("calls")
        if isinstance(calls, list):
            for call in calls:
                if isinstance(call, dict):
                    try:
                        arguments = json.loads(str(call.get("arguments", "")))
                        malformed_arguments |= not isinstance(arguments, dict)
                    except ValueError:
                        malformed_arguments = True
        if malformed_arguments:
            logging.getLogger(__name__).warning(
                json.dumps({"event": "invalid_tool_arguments", "attempt": index + 1})
            )
            if index or visible_content:
                raise RuntimeError("invalid_tool_arguments")
        malformed = is_history_answer(str(result.get("text", "")))
        if malformed:
            logging.getLogger(__name__).warning(
                json.dumps(
                    {
                        "event": "unexpected_tool_history_answer",
                        "content_chars": len(str(result.get("text", ""))),
                        "completion_tokens": usage.completion_tokens,
                        "attempt": index + 1,
                    }
                )
            )
            if index or visible_content:
                raise RuntimeError("unexpected_tool_history_answer")
        incomplete = result.get("finish_reason") == "length"
        if incomplete:
            logging.getLogger(__name__).warning(
                json.dumps(
                    {
                        "event": "provider_output_incomplete",
                        "finish_reason": "length",
                        "completion_tokens": usage.completion_tokens,
                        "max_tokens": current.max_tokens,
                        "content_chars": len(str(result.get("text", ""))),
                        "attempt": index + 1,
                    }
                )
            )
            if index or visible_content:
                if index and (not str(result.get("text", "")).strip()):
                    raise RuntimeError("empty_content_after_retry")
                raise RuntimeError("incomplete_provider_answer")
        # Empty terminal responses retain validated billing, then get one retry.
        if (
            malformed
            or malformed_arguments
            or incomplete
            or (not str(result.get("text", "")).strip() and not result.get("calls"))
        ):
            if index:
                raise RuntimeError("empty_content_after_retry")
            # A large evidence input may no longer fit the original provider's
            # conservative reservation. Try the configured alternate before
            # rejecting a recovery that still fits the same request ledger.
            alternate = policy.models[fallback_role]
            if trace.strip():
                logging.getLogger(__name__).warning(
                    json.dumps(
                        {
                            "event": "provider_default_regression",
                            "effort": current.reasoning_effort,
                            "trace_tokens": count,
                            "attempt": index + 1,
                        }
                    )
                )
            if result.get("finish_reason") != "length" and not trace.strip():
                role, model = fallback_role, alternate
                fallback = True
            if (
                policy.cost(model, incoming, 3000) > budget - spent
                and policy.cost(alternate, incoming, 3000) <= budget - spent
            ):
                role, model = fallback_role, alternate
                fallback = True
            retried = True
            yield {"phase": "reasoning_fallback"}
            continue
        for event in buffered:
            yield event
        answer = {
            "provider_model": model,
            "text": result["text"],
            "calls": result["calls"],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
            "cost_eur": str(spent),
            "reasoning": reasoning,
            "trace_tokens": trace_tokens,
            "answer_tokens": answer_tokens,
            "token_split_estimated": estimated,
            "reasoning_retried": retried,
        }
        if retry_completion_tokens:
            answer["retry_completion_tokens"] = retry_completion_tokens
        if request.observe:
            answer["observation"] = {
                "provider": "escalade",
                "route": "simple"
                if classify(request.messages) == "chat_simple"
                else "complexe",
                "task_type": task,
                "fallback": fallback,
            }
        logging.getLogger(__name__).info(
            json.dumps(
                {
                    "event": "quality_usage",
                    "provider_model": model,
                    "profile": request.profile,
                    "effort": request.reasoning_effort,
                    "trace_tokens": trace_tokens,
                    "answer_tokens": answer_tokens,
                    "token_split_estimated": estimated,
                    "cost_eur": str(spent),
                    "reasoning_retried": retried,
                }
            )
        )
        yield {"result": answer}
        return
    raise RuntimeError("provider_error")
