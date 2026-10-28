"""Structured logs: one JSON line per event, machine-readable, greppable."""

from __future__ import annotations

import logging
import sys

import structlog

_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}


def configure_logging(level: str = "INFO", *, json_output: bool = True) -> None:
    """Configure once at process start. Answer text goes to stdout, logs to stderr."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=_LEVELS.get(level.upper(), logging.INFO),
    )
    renderer = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            _LEVELS.get(level.upper(), logging.INFO)
        ),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "signal") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
