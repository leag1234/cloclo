"""Real contained native UI with a fresh test-only terminal credential."""

from collections.abc import Iterator
from contextlib import contextmanager
import os
import secrets
from unittest.mock import patch

from services.orchestrator.terminal_stack import terminal, user_interface


@contextmanager
def native_ui(name: str) -> Iterator[None]:
    with (
        patch.dict(
            os.environ,
            {
                "OPEN_TERMINAL_API_KEY": os.environ.get("OPEN_TERMINAL_API_KEY")
                or secrets.token_urlsafe(32)
            },
        ),
        terminal(name + "-terminal", "127.0.0.1:8000"),
        user_interface(name, False),
    ):
        yield
