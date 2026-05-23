"""
Structured JSON logging via Loguru.
Configures request-scoped context, correlation IDs, and log sinks.
"""
from __future__ import annotations

import sys
import json
import traceback
from contextvars import ContextVar
from typing import Any
from uuid import uuid4

from loguru import logger

from backend.core.config import settings

# ── Context variables for request-scoped logging ──────────────────────────────
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")
dataset_id_var: ContextVar[str] = ContextVar("dataset_id", default="")


def _serialize_record(record: dict) -> str:
    """Serialize a Loguru record to a JSON string."""
    subset: dict[str, Any] = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "logger": record["name"],
        "message": record["message"],
        "module": record["module"],
        "function": record["function"],
        "line": record["line"],
        "request_id": request_id_var.get(""),
        "user_id": user_id_var.get(""),
        "dataset_id": dataset_id_var.get(""),
        "environment": settings.ENVIRONMENT.value,
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
    # Merge any extra bound context
    if record.get("extra"):
        subset.update(record["extra"])
    # Attach exception info if present
    if record["exception"]:
        exc = record["exception"]
        subset["exception"] = {
            "type": exc.type.__name__ if exc.type else None,
            "value": str(exc.value) if exc.value else None,
            "traceback": "".join(
                traceback.format_tb(exc.traceback)
            ) if exc.traceback else None,
        }
    return json.dumps(subset, default=str)


def _json_sink(message) -> None:
    serialized = _serialize_record(message.record)
    print(serialized, file=sys.stdout, flush=True)


def configure_logging() -> None:
    """Remove default Loguru handler and install structured JSON sink."""
    logger.remove()

    if settings.is_development:
        # Human-readable format for local development
        logger.add(
            sys.stdout,
            level=settings.LOG_LEVEL.value,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "{message}"
            ),
            colorize=True,
            backtrace=True,
            diagnose=True,
        )
    else:
        # Structured JSON for staging/production
        logger.add(
            _json_sink,
            level=settings.LOG_LEVEL.value,
            serialize=False,
            backtrace=False,
            diagnose=False,
        )


def get_logger(name: str):
    """Return a named logger bound with service context."""
    return logger.bind(logger_name=name)


class RequestLoggingContext:
    """Context manager that sets request-scoped log variables."""

    def __init__(
        self,
        request_id: str | None = None,
        user_id: str | None = None,
        dataset_id: str | None = None,
    ) -> None:
        self._request_id = request_id or str(uuid4())
        self._user_id = user_id or ""
        self._dataset_id = dataset_id or ""
        self._tokens: list = []

    def __enter__(self) -> "RequestLoggingContext":
        self._tokens = [
            request_id_var.set(self._request_id),
            user_id_var.set(self._user_id),
            dataset_id_var.set(self._dataset_id),
        ]
        return self

    def __exit__(self, *_) -> None:
        for token in self._tokens:
            token.var.reset(token)

    @property
    def request_id(self) -> str:
        return self._request_id