"""Structured JSON logging and Request-ID context propagation.

# CONCEPT: Error handling & good error design (Request-ID correlation + structured JSON logs)
"""

import contextvars
import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from typing import Any

request_id_ctx_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="system"
)


def get_request_id() -> str:
    """Retrieve the current request's correlation ID from contextvars."""
    return request_id_ctx_var.get()


class JSONLogFormatter(logging.Formatter):
    """Format log records as single-line structured JSON with correlation request_id.

    Never leaks PII or secrets; full stack traces are logged internally here
    and never exposed in HTTP responses.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
        }
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_payload.update(record.extra_data)

        if record.exc_info:
            log_payload["exception"] = "".join(traceback.format_exception(*record.exc_info))

        return json.dumps(log_payload, default=str)


def setup_logging(debug: bool = False) -> None:
    """Configure root logger with structured JSON output."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if debug else logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONLogFormatter())

    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Quiet noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

