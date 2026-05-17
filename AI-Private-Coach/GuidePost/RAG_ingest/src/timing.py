"""
Shared helpers for timing steps in the ingestion pipeline.
"""

from __future__ import annotations

from typing import Union


Number = Union[int, float]


def format_duration(seconds: Number) -> str:
    """
    Format a duration in seconds as HH:MM:SS.

    Fractions of a second are discarded (floor).
    """
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def log_step_duration(logger, step_name: str, elapsed_seconds: Number) -> None:
    """
    Log a single step's duration in a consistent format for pipeline visibility.
    Example: [DURATION] Text extraction: 00:01:23
    """
    logger.info("[DURATION] %s: %s", step_name, format_duration(elapsed_seconds))

