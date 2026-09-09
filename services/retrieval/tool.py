"""Read-only JSON CLI boundary for rag_search (contracts/m3.md)."""

import json
import os
import sys

from pydantic import BaseModel, ConfigDict, Field
from services.retrieval.search import Gateway, rank
from services.retrieval.store import Store


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: str = Field(min_length=1, max_length=4000, pattern=r"\S")


def main() -> None:
    request = Request.model_validate_json(sys.stdin.buffer.read(16001))
    store = Store(os.environ["ATLAS_RETRIEVAL_DSN"])
    chunks = rank(
        request.query,
        store.read(),
        Gateway(os.environ.get("ATLAS_GATEWAY_URL", "http://127.0.0.1:8010")),
    )
    print(
        json.dumps(
            {
                "passages": [
                    {
                        "chunk_id": c.chunk_id,
                        "text": c.text.encode()[:400].decode("utf-8", errors="ignore"),
                        "source": c.source,
                    }
                    for c in chunks
                ]
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
