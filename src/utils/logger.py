"""
Structured JSON Logger for GroundedOps.
Provides standardized logging for AWS Lambda, CloudWatch, and local development.
"""

import json
import logging
import os
import sys
import time
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects for CloudWatch Logs."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Include custom extra attributes if passed in record.__dict__
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            log_data.update(record.extra_fields)

        # Include exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def get_logger(name: str = "groundedops", level: Optional[str] = None) -> logging.Logger:
    """
    Get or configure a structured logger instance.
    """
    log_level_str = level or os.environ.get("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(log_level)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    return logger


class Timer:
    """Context manager for measuring elapsed execution time."""

    def __init__(self, description: str = "operation"):
        self.description = description
        self.start_time: float = 0.0
        self.elapsed_ms: float = 0.0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed_ms = (time.perf_counter() - self.start_time) * 1000.0
