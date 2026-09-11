"""Bounded producer queue and a single journal for the lifetime of an SSE response."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
import json
import os
from pathlib import Path
import re
import time

from fastapi.responses import StreamingResponse

from services.orchestrator.chat_schema import ChatRequest
from services.orchestrator.interactions import Interaction, write_interaction
from services.orchestrator.stream_client import sink_context


def response(
    payload: ChatRequest,
    item: Interaction,
    started: float,
    process: Callable[[ChatRequest, Interaction], Awaitable[None]],
) -> StreamingResponse:
    async def generate() -> AsyncIterator[str]:
        queue: asyncio.Queue[dict[str, object] | None] = asyncio.Queue(maxsize=8)
        pending = ""
        turn = 0
        citation_numbers: dict[str, int] = {}
        base = {
            "id": item.request_id,
            "created": int(time.time()),
            "model": "atlas",
            "object": "chat.completion.chunk",
        }

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
            nonlocal pending, turn
            if "phase" in event:
                if event["phase"] != "generating":
                    await content(pending)
                    pending = ""
                if event["phase"] == "intermediate":
                    await queue.put(
                        {
                            "delta": {
                                "content": "\n\n*Étape intermédiaire terminée : appel d’outil.*\n\n"
                            },
                            "atlas": {"turn": turn, "phase": "intermediate"},
                        }
                    )
                if event["phase"] == "generating":
                    citation_numbers.clear()
                turn = int(str(event["turn"]))
                await queue.put(
                    {"atlas": {**event, "reasoning_effort": payload.reasoning_effort}}
                )
                return
            delta = event.get("delta")
            if not isinstance(delta, dict):
                raise ValueError("invalid_delta")
            if "reasoning_content" in delta:
                await queue.put(event)
            if event.get("memory") is True or item.task_type in {"vision", "imagegen"}:
                await queue.put({"delta": {"content": delta["content"]}})
                return
            if "content" in delta:
                pending += str(delta["content"])
                suffix = re.search(r"(?<!\w)[`\[]?[a-f0-9]{1,64}$|[`\[]$", pending)
                end = suffix.start() if suffix else len(pending)
                await content(pending[:end])
                pending = pending[end:]

        async def produce() -> None:
            token = sink_context.set(sink)
            try:
                async with asyncio.timeout(max(0, 120 - (time.monotonic() - started))):
                    await process(payload, item)
                    if item.state != "done":
                        raise RuntimeError("request_stopped")
                    await content(pending)
                await queue.put({"finish": True})
            except asyncio.CancelledError:
                item.state = "cancelled"
                item.erreurs.append("cancelled")
                raise
            except Exception:
                item.state = "error"
                item.erreurs.append("stream_error")
                await queue.put(
                    {"error": {"code": "stream_error", "type": "stream_error"}}
                )
            finally:
                sink_context.reset(token)
            await queue.put(None)

        task = asyncio.create_task(produce())
        try:
            while True:
                event = await queue.get()
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
                            "cost_eur": item.cout_eur,
                            "reasoning_effort": payload.reasoning_effort,
                            "max_output_tokens": 2048,
                        }
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
