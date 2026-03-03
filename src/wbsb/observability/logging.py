"""Structured JSON logging to logs.jsonl."""
from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Reserved LogRecord attributes that cannot be used as extra keys
_RESERVED_LOG_KEYS = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname",
    "filename", "module", "exc_info", "exc_text", "stack_info",
    "lineno", "funcName", "created", "msecs", "relativeCreated",
    "thread", "threadName", "processName", "process", "message",
    "taskName",
})


class JsonlHandler(logging.Handler):
    """Logging handler that writes JSON objects to a .jsonl file."""

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path
        self._formatter = logging.Formatter()
        self._write_failed = False

    def emit(self, record: logging.LogRecord) -> None:
        entry: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        if record.exc_info:
            entry["exc"] = self._formatter.formatException(record.exc_info)
        # Add any extra fields passed via the record
        for key, val in record.__dict__.items():
            if key not in _RESERVED_LOG_KEYS:
                entry[key] = val
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as exc:
            if not self._write_failed:
                self._write_failed = True
                print(
                    f"[wbsb] WARNING: JSONL log write failed ({exc}); "
                    "further write errors will be suppressed.",
                    file=sys.stderr,
                )


_logger: logging.Logger | None = None


class StructLogger:
    """Thin wrapper around Logger that accepts kwargs as structured fields."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def _log(self, level: int, event: str, **kwargs: Any) -> None:
        # Prefix keys that conflict with LogRecord reserved attributes
        safe_extra = {
            (f"field_{k}" if k in _RESERVED_LOG_KEYS else k): v
            for k, v in kwargs.items()
        }
        self._logger.log(level, event, extra=safe_extra)

    def info(self, event: str, **kwargs: Any) -> None:
        self._log(logging.INFO, event, **kwargs)

    def error(self, event: str, exc_info: bool = False, **kwargs: Any) -> None:
        safe_extra = {
            (f"field_{k}" if k in _RESERVED_LOG_KEYS else k): v
            for k, v in kwargs.items()
        }
        if exc_info:
            self._logger.error(event, exc_info=True, extra=safe_extra)
        else:
            self._logger.log(logging.ERROR, event, extra=safe_extra)

    def debug(self, event: str, **kwargs: Any) -> None:
        self._log(logging.DEBUG, event, **kwargs)


def init_run_logger(log_path: Path) -> logging.Logger:
    """Initialise the run logger writing to log_path."""
    logger = logging.getLogger("wbsb")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    # File handler (JSONL)
    logger.addHandler(JsonlHandler(log_path))

    # Console handler (plain)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(levelname)s  %(message)s"))
    logger.addHandler(console)

    return logger


def get_logger() -> StructLogger:
    """Return the structured module logger."""
    return StructLogger(logging.getLogger("wbsb"))
