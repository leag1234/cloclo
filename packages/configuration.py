"""Fail before startup side effects when required configuration is absent."""

import os

CHAT_REQUIRED_ENV = (
    "ESCALATION_MODEL",
    "SCW_GENERATIVE_BASE_URL",
    "SCW_GENERATIVE_API_KEY",
)
GPU_REQUIRED_ENV = (
    "SCW_DEFAULT_PROJECT_ID",
    "SCW_DEFAULT_ZONE",
    "LOCAL_MODEL",
    "GPU_CLIENT_IP",
    "GPU_MAX_EUR_H",
)


IMAGE_REQUIRED_ENV = (
    *CHAT_REQUIRED_ENV,
    "SCW_DEFAULT_PROJECT_ID",
    "SCW_DEFAULT_ZONE",
    "LOCAL_MODEL",
    "GPU_MAX_EUR_H",
)


class MissingConfiguration(RuntimeError):
    def __init__(self, missing: tuple[str, ...]) -> None:
        self.missing = missing
        super().__init__(
            "missing_configuration: Missing required environment variables: "
            + ", ".join(missing)
        )


def require_env(names: tuple[str, ...]) -> None:
    missing = [name for name in names if not os.environ.get(name, "").strip()]
    if missing:
        raise MissingConfiguration(tuple(missing))
