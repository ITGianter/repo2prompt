"""Centralized logging configuration for repo2prompt."""

from __future__ import annotations

import logging
import sys

_ROOT_LOGGER_NAME = "repo2prompt"

# Format tiers selected automatically by level
_FORMAT_SIMPLE = "%(message)s"
_FORMAT_VERBOSE = "%(name)s [%(levelname)s] %(message)s"
_FORMAT_DEBUG = "%(asctime)s %(name)s [%(levelname)s] %(message)s"


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the repo2prompt hierarchy."""
    return logging.getLogger(name)


def setup_logging(level: int = logging.WARNING) -> None:
    """Configure the root repo2prompt logger with a stderr handler.

    Called once from cli.main() before any pipeline work begins.
    Idempotent — safe to call multiple times.
    """
    root = logging.getLogger(_ROOT_LOGGER_NAME)
    root.setLevel(level)

    # Avoid duplicate handlers on repeated calls
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)

    if level <= logging.DEBUG:
        handler.setFormatter(logging.Formatter(_FORMAT_DEBUG))
    elif level <= logging.INFO:
        handler.setFormatter(logging.Formatter(_FORMAT_VERBOSE))
    else:
        handler.setFormatter(logging.Formatter(_FORMAT_SIMPLE))

    root.addHandler(handler)
