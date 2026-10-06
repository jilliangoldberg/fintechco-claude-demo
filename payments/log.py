"""Structured JSON event logging.

Every line is one JSON object with an ``event`` name, a UTC timestamp and the
current request id. Log through ``EventLogger`` rather than the stdlib logger so
fields are checked: card data and customer contact details must never reach
the logs.
"""

import json
import logging
import sys
from contextvars import ContextVar

from payments.clock import Clock, isoformat

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

FORBIDDEN_FIELDS = frozenset({"card_token", "card_number", "pan", "cvc", "email"})

logger = logging.getLogger("payments")


class EventLogger:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    def info(self, event: str, **fields: object) -> None:
        self._emit(logging.INFO, event, fields)

    def warning(self, event: str, **fields: object) -> None:
        self._emit(logging.WARNING, event, fields)

    def _emit(self, level: int, event: str, fields: dict[str, object]) -> None:
        leaked = FORBIDDEN_FIELDS & fields.keys()
        if leaked:
            raise ValueError(f"refusing to log sensitive fields: {sorted(leaked)}")
        record = {
            "ts": isoformat(self._clock.now()),
            "level": logging.getLevelName(level).lower(),
            "event": event,
            "request_id": request_id_var.get(),
            **fields,
        }
        payload = {key: value for key, value in record.items() if value is not None}
        logger.log(level, json.dumps(payload, separators=(",", ":")))


class _StdoutHandler(logging.Handler):
    """Writes to whatever ``sys.stdout`` is at emit time."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            sys.stdout.write(self.format(record) + "\n")
        except Exception:
            self.handleError(record)


def configure_logging(level: int = logging.INFO) -> None:
    """Send JSON lines to stdout. Safe to call more than once."""
    if not logger.handlers:
        logger.addHandler(_StdoutHandler())
    logger.setLevel(level)
