"""Disk cache and conservative, atomic monthly search reservations."""

from contextlib import contextmanager
from collections.abc import Iterator
import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import cast


class Cache:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connection() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, expires REAL, value TEXT)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS quota (month TEXT PRIMARY KEY, used INTEGER NOT NULL)"
            )

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=1, isolation_level="IMMEDIATE")
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def key(value: object) -> str:
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    def get(self, key: str) -> dict[str, object] | None:
        with self.connection() as db:
            row = db.execute(
                "SELECT value FROM cache WHERE key=? AND expires>?", (key, time.time())
            ).fetchone()
        return cast(dict[str, object], json.loads(row[0])) if row else None

    def put(self, key: str, value: dict[str, object], ttl: int) -> None:
        with self.connection() as db:
            db.execute(
                "INSERT OR REPLACE INTO cache VALUES (?,?,?)",
                (key, time.time() + ttl, json.dumps(value)),
            )

    def reserve_search(self, provider: str = "serpapi") -> None:
        month = time.strftime("%Y-%m", time.gmtime())
        if provider not in {"serpapi", "tavily"}:
            raise ValueError("invalid_search_provider")
        if provider != "serpapi":
            month = provider + ":" + month
        with self.connection() as db:
            db.execute("INSERT OR IGNORE INTO quota VALUES (?,0)", (month,))
            if (
                db.execute(
                    "UPDATE quota SET used=used+1 WHERE month=? AND used<900", (month,)
                ).rowcount
                != 1
            ):
                raise ValueError("quota_exceeded")
