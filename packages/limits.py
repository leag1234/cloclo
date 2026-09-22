"""Safe measured boundary failures; never retain rejected input content."""

import logging


class LimitError(ValueError):
    def __init__(self, code: str, measured: int, limit: int, unit: str) -> None:
        self.code, self.measured, self.limit, self.unit = code, measured, limit, unit
        self.detail = f"{code}: measured {measured} {unit}; limit {limit} {unit}"
        super().__init__(self.detail)
        logging.getLogger(__name__).warning(self.detail)


class ProviderLimitError(LimitError, RuntimeError):
    """Retain the provider-failure interface while carrying numeric diagnostics."""
