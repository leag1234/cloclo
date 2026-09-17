"""ATLAS image references: installed as a native Open WebUI inlet filter."""

from collections import OrderedDict
from collections.abc import Awaitable, Callable
import hashlib
import re
from typing import Any

import aiohttp


class Filter:
    def __init__(self) -> None:
        self.references: OrderedDict[str, str] = OrderedDict()

    async def upload(self, url: str) -> str:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15), trust_env=False
        ) as client:
            async with client.post(
                "http://127.0.0.1:8020/images/upload",
                json={"url": url},
                allow_redirects=False,
            ) as response:
                data = await response.json()
                if response.status != 200:
                    raise ValueError(
                        "Image upload: "
                        + str(data.get("message", data.get("error", "failed")))
                    )
                reference = data.get("url")
                if not isinstance(reference, str) or not re.fullmatch(
                    r"https?://[^/]+/images/[a-f0-9]{32}", reference
                ):
                    raise ValueError("Invalid uploaded image reference")
                return reference

    async def inlet(
        self,
        body: dict[str, Any],
        __event_emitter__: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        if body.get("model") not in {"atlas", "atlas-glm", "atlas-fast"}:
            return body
        for message in body.get("messages", []):
            if message.get("role") != "user" or not isinstance(
                message.get("content"), list
            ):
                continue
            for part in message["content"]:
                data = part.get("image_url") if isinstance(part, dict) else None
                if not isinstance(data, dict) or not isinstance(data.get("url"), str):
                    continue
                url = data["url"]
                if not url.startswith("data:image/"):
                    continue
                digest = hashlib.sha256(url.encode()).hexdigest()
                if digest not in self.references:
                    if __event_emitter__:
                        await __event_emitter__(
                            {
                                "type": "status",
                                "data": {
                                    "description": "Preparing image references…",
                                    "done": False,
                                },
                            }
                        )
                    self.references[digest] = await self.upload(url)
                    while len(self.references) > 256:
                        self.references.popitem(last=False)
                else:
                    self.references.move_to_end(digest)
                data["url"] = self.references[digest]
        return body
