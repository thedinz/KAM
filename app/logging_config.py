"""Logging configuration helper for KAM."""
import logging
import os
import sys
from typing import Optional

DEFAULT_LEVEL = "INFO"
ENV_LEVEL = "KAM_LOG_LEVEL"


def _resolve_level(name: Optional[str]) -> int:
    """Return a logging level from an environment-provided name."""
    if not name:
        return logging.getLevelName(DEFAULT_LEVEL)
    normalized = name.strip().upper()
    level = logging.getLevelName(normalized)
    if isinstance(level, int):
        return level
    return logging.getLevelName(DEFAULT_LEVEL)


def configure_logging() -> None:
    """Configure application-wide logging based on environment variables."""
    level = _resolve_level(os.getenv(ENV_LEVEL))
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )


__all__ = ["configure_logging"]
