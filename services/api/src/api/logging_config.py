"""Structured (JSON) logging with a per-request correlation ID.

ADR 0066 Priority 2 item 3: the API had no configured log formatter at all
(19 modules call `logging.getLogger(__name__)`, but nothing ever called
`logging.basicConfig`, so those lines never had a distinct, aggregatable
shape) and no way to correlate every log line a single request produced.
Deliberately stdlib-only -- a JSON formatter is ~30 lines to get right, not
worth a new dependency (e.g. structlog) for this project's current needs.
"""

import json
import logging
import sys
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_RESERVED_RECORD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
}


class RequestIdFilter(logging.Filter):
    """Attaches the current request's correlation ID to every log record so
    the formatter can include it, even for log calls made deep inside a
    router/service function that never sees the request object directly."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        # Anything passed via logger.info(..., extra={...}) beyond the
        # standard LogRecord attributes -- e.g. path/status_code/duration_ms
        # from the request-logging middleware below.
        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_ATTRS and key != "request_id":
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


def log_request(logger: logging.Logger, *, method: str, path: str, status_code: int, duration_ms: float) -> None:
    logger.info(
        "request",
        extra={"method": method, "path": path, "status_code": status_code, "duration_ms": round(duration_ms, 2)},
    )


__all__ = ["configure_logging", "log_request", "request_id_var", "JsonFormatter", "RequestIdFilter"]
