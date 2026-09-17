"""Bounded producer queue and a single journal for the lifetime of an SSE response."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
import json
import logging
import html
import os
from pathlib import Path
import re
import time

from fastapi.responses import StreamingResponse

from services.orchestrator.chat_schema import ChatRequest
from services.orchestrator.deadline import request_deadline
from services.orchestrator.interactions import Interaction, write_interaction
from services.orchestrator.stream_client import sink_context
from services.orchestrator.model import GatewayError


def response(
    payload: ChatRequest,
    item: Interaction,
    started: float,
    process: Callable[[ChatRequest, Interaction], Awaitable[None]],
) -> StreamingResponse:
    language = payload.ui_locale
    labels = json.loads(Path("prompts/progress.json").read_text())
    progress = str(labels.get(language, labels["en"])).split(":", 1)[0].strip()
    activity_labels = json.loads(Path("prompts/activity-labels.json").read_text())
    activity_labels = activity_labels.get(language, activity_labels["en"])

    async def generate() -> AsyncIterator[str]:
        queue: asyncio.Queue[dict[str, object] | None] = asyncio.Queue(maxsize=8)
        pending = ""
        turn = 0
        activity = "thinking" if payload.reasoning_effort == "high" else "answering"
        activity_urls: list[str] = []
        last_activity = time.monotonic()
        citation_numbers: dict[str, int] = {}
        base = {
            "id": item.request_id,
            "created": int(time.time()),
            "model": payload.model,
            "object": "chat.completion.chunk",
        }

        def status_event(done: bool = False) -> dict[str, object]:
            elapsed = round(time.monotonic() - started, 1)
            description = str(
                activity_labels.get("done" if done else activity, activity)
            )
            if activity_urls:
                description += " — " + ", ".join(activity_urls)
            return {
                "type": "status",
                "data": {
                    "description": f"{description} ({elapsed:.1f}s)",
                    "done": done,
                    "elapsed_seconds": elapsed,
                    "urls": activity_urls,
                },
            }

        def heartbeat() -> str:
            return (
                "data: "
                + json.dumps(
                    {
                        **base,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
                        "atlas": {
                            "phase": activity,
                            "elapsed_seconds": round(time.monotonic() - started, 1),
                        },
                        "event": status_event(),
                    }
                )
                + "\n\n"
            )

        async def content(text: str) -> None:
            # Retain only a possible citation suffix. Never expose an unresolved link.
            from services.orchestrator.chat_pipeline import render_citations

            if not text:
                return
            temporary = Interaction()
            temporary.reponse = text
            temporary.chunks_recuperes = item.chunks_recuperes
            if payload.project_id:
                from services.orchestrator.project_chat import render_project_citations

                temporary.reponse = render_project_citations(
                    temporary, payload.project_id, text
                )
            else:
                await render_citations(temporary)
            for citation in temporary.citations:
                key = str(citation["chunk_id"])
                citation_numbers.setdefault(key, len(citation_numbers) + 1)
            labels = {
                str(index): citation_numbers[str(c["chunk_id"])]
                for index, c in enumerate(temporary.citations, 1)
            }
            temporary.reponse = re.sub(
                r"\[Source (\d+)\]",
                lambda match: f"[Source {labels.get(match[1], match[1])}]",
                temporary.reponse,
            )
            await queue.put(
                {
                    "delta": {"content": temporary.reponse},
                    "atlas": {"turn": turn, "phase": "generating"},
                }
            )

        async def sink(event: dict[str, object]) -> None:
            nonlocal pending, turn, activity, activity_urls
            if "phase" in event:
                phase = str(event["phase"])
                raw_urls = event.get("urls")
                raw_tools = event.get("tools")
                named_tools = raw_tools if isinstance(raw_tools, list) else []
                if phase in {"tool_started", "tool_finished"}:
                    activity = str(event.get("tool", "answering"))
                    activity_urls = (
                        [str(url) for url in raw_urls]
                        if isinstance(raw_urls, list)
                        else []
                    )
                elif phase in {
                    "reasoning_fallback",
                    "provider_fallback",
                    "synthesized",
                    "source_truncated",
                }:
                    activity = phase
                elif phase == "generating":
                    activity = (
                        "thinking"
                        if payload.reasoning_effort == "high"
                        else "answering"
                    )
                    activity_urls = []
                if event["phase"] != "generating":
                    await content(pending)
                    pending = ""
                if event["phase"] == "intermediate":
                    await queue.put(
                        {
                            "delta": {
                                "content": "\n\n<details>\n<summary>"
                                + html.escape(
                                    progress
                                    + ": "
                                    + ", ".join(
                                        str(activity_labels.get(str(tool), tool))
                                        for tool in named_tools
                                        if isinstance(tool, str)
                                    )
                                )
                                + "</summary>\n\n</details>\n\n"
                            },
                            "atlas": {"turn": turn, "phase": "tool_details"},
                        }
                    )
                if phase == "tool_finished" and activity != "generate_image":
                    links = "<br>".join(html.escape(url) for url in activity_urls)
                    await queue.put(
                        {
                            "delta": {
                                "content": "\n\n<details>\n<summary>"
                                + html.escape(
                                    str(activity_labels.get(activity, activity))
                                )
                                + "</summary>\n"
                                + links
                                + "\n</details>\n\n"
                            },
                            "atlas": {"phase": "tool_details", "tool": activity},
                        }
                    )
                if event["phase"] == "generating":
                    citation_numbers.clear()
                turn = int(str(event.get("turn", turn)))
                await queue.put(
                    {
                        "atlas": {
                            **event,
                            "reasoning_effort": payload.reasoning_effort,
                        },
                        "event": status_event(),
                    }
                )
                return
            delta = event.get("delta")
            if not isinstance(delta, dict):
                raise ValueError("invalid_delta")
            if "reasoning_content" in delta:
                activity = "thinking"
                await queue.put(event)
            if "content" in delta and (
                event.get("memory") is True
                or item.task_type
                in {
                    "vision",
                    "imagegen",
                    "followup",
                }
            ):
                await queue.put({"delta": {"content": delta["content"]}})
                return
            if "content" in delta:
                activity = "answering"
                pending += str(delta["content"])
                suffix = re.search(r"(?<!\w)[`\[]?[a-f0-9]{1,64}$|[`\[]$", pending)
                end = suffix.start() if suffix else len(pending)
                await content(pending[:end])
                pending = pending[end:]

        async def produce() -> None:
            token = sink_context.set(sink)
            try:
                async with request_deadline(
                    max(0, payload.timeout_seconds - (time.monotonic() - started))
                ):
                    await process(payload, item)
                    if item.state != "done":
                        raise RuntimeError("request_stopped")
                    await content(pending)
                await queue.put({"finish": True})
            except asyncio.CancelledError:
                item.state = "cancelled"
                item.erreurs.append("cancelled")
                raise
            except TimeoutError:
                item.state = "error"
                item.erreurs.append("stream_error")
                detail = f"Timeout: {time.monotonic() - started:.3f} seconds elapsed, limit {payload.timeout_seconds + item.startup_seconds:.3f} seconds"
                item.rejection = {"code": "timeout", "message": detail}
                await queue.put(
                    {
                        "error": {
                            "code": "stream_error",
                            "type": "stream_error",
                            "message": detail,
                        }
                    }
                )
            except GatewayError as exc:
                item.state = "error"
                item.erreurs.append(exc.code)
                item.rejection = {"code": exc.code, "message": exc.detail}
                await queue.put(
                    {
                        "error": {
                            "code": exc.code,
                            "type": exc.code,
                            "message": exc.detail or exc.code,
                        }
                    }
                )
            except Exception:
                item.state = "error"
                item.erreurs.append("stream_error")
                detail = (
                    "The provider did not complete a valid answer. "
                    f"Elapsed {time.monotonic() - started:.3f}s "
                    f"(limit {payload.timeout_seconds:.0f}s); "
                    f"reserved cost {item.cout_eur:.6f} EUR (limit 0.10 EUR)."
                )
                item.rejection = {"code": "stream_error", "message": detail}
                logging.getLogger(__name__).warning(json.dumps(item.rejection))
                await queue.put(
                    {
                        "error": {
                            "code": "stream_error",
                            "type": "stream_error",
                            "message": detail,
                        }
                    }
                )
            finally:
                sink_context.reset(token)
            await queue.put(None)

        task = asyncio.create_task(produce())
        try:
            yield heartbeat()
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1)
                except TimeoutError:
                    last_activity = time.monotonic()
                    yield heartbeat()
                    continue
                if event is None:
                    break
                if "error" in event:
                    output = event
                else:
                    output = {
                        **base,
                        "choices": [
                            {
                                "index": 0,
                                "delta": event.get("delta", {}),
                                "finish_reason": "stop"
                                if event.get("finish")
                                else None,
                            }
                        ],
                        "atlas": event.get(
                            "atlas", {"turn": turn, "phase": "generating"}
                        ),
                    }
                    if event.get("finish"):
                        output["usage"] = {
                            "prompt_tokens": item.tokens["in"],
                            "completion_tokens": item.tokens["out"],
                            "total_tokens": sum(item.tokens.values()),
                        }
                        output["atlas"] = {
                            "images": item.images,
                            "uploaded_images": item.uploaded_images,
                            "cost_eur": item.cout_eur,
                            "provider_model": item.provider_model,
                            "reasoning_effort": payload.reasoning_effort,
                            "max_output_tokens": payload.max_tokens,
                            "reasoning_retried": item.reasoning_retried,
                            "status": activity_labels["reasoning_fallback"]
                            if item.reasoning_retried
                            else "",
                            "reasoning": {
                                "collapsed": True,
                                "trace_tokens": item.trace_tokens,
                                "answer_tokens": item.answer_tokens,
                                "estimated": item.token_split_estimated,
                            },
                        }
                if (
                    "atlas" in event
                    or event.get("finish")
                    or time.monotonic() - last_activity >= 1
                ):
                    output["event"] = event.get(
                        "event", status_event(bool(event.get("finish")))
                    )
                    last_activity = time.monotonic()
                yield "data: " + json.dumps(output) + "\n\n"
            yield "data: [DONE]\n\n"
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            item.latence_ms["total"] = (time.monotonic() - started) * 1000
            write_interaction(
                item,
                Path(os.environ.get("ATLAS_INTERACTION_DIR", "BRAIN/interactions")),
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
