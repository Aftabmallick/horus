"""Internal logging for Agent Tracer Plus.

Uses a namespaced logger so users can control our log output
without interfering with their application logging.
Tracing errors are NEVER propagated to the user's application.
"""

from __future__ import annotations

import logging
import os

_LOG_LEVEL = os.environ.get("AGENT_TRACER_PLUS_LOG_LEVEL", "WARNING").upper()
_LOGGER_NAME = "agent_tracer_plus"


def get_logger(name: str | None = None) -> logging.Logger:
    """Get a namespaced logger for internal use.

    Args:
        name: Optional sub-name (e.g., "storage.sqlite").
              Will be prefixed with "agent_tracer_plus.".

    Returns:
        A configured Logger instance.
    """
    full_name = f"{_LOGGER_NAME}.{name}" if name else _LOGGER_NAME
    logger = logging.getLogger(full_name)

    # Only configure the root agent_tracer_plus logger once
    if not logger.handlers and name is None:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "[%(name)s] %(levelname)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, _LOG_LEVEL, logging.WARNING))
        logger.propagate = False

    return logger
