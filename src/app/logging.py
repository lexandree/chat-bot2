"""Logging setup that avoids secret leakage."""

from __future__ import annotations

import logging
from typing import Iterable


SECRET_MARKERS = ("password", "secret", "token", "key")


class SecretRedactionFilter(logging.Filter):
    """Redact obvious secret-bearing log fields."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        lowered = message.lower()
        if any(marker in lowered for marker in SECRET_MARKERS):
            record.msg = "[redacted secret-bearing log message]"
            record.args = ()
        return True


def configure_logging(level: int = logging.INFO, *, logger_names: Iterable[str] = ("legal_graph",)) -> None:
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
    for name in logger_names:
        logger = logging.getLogger(name)
        if not any(isinstance(filter_, SecretRedactionFilter) for filter_ in logger.filters):
            logger.addFilter(SecretRedactionFilter())
