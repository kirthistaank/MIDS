"""
Shared logging helpers for the RAG_ingest pipeline.

Features:
- Logs to rotating files under /tmp/RAG_ingest
- Optional console logging (enable only from main)
- Single base logger configuration per process via get_logger()
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


_BASE_CONFIGURED: bool = False
_HAS_CONSOLE_HANDLER: bool = False


def _ensure_log_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


class _OnlyInfoFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        return record.levelno == logging.INFO


def _configure_base_logger() -> logging.Logger:
    """
    Configure the base pipeline logger (file handler only).
    """
    global _BASE_CONFIGURED
    base = logging.getLogger("rag_ingest")
    if _BASE_CONFIGURED:
        return base

    log_dir = Path("/tmp/RAG_ingest")
    _ensure_log_dir(log_dir)
    log_file = log_dir / "rag_ingest.log"

    base.setLevel(logging.INFO)
    base.propagate = False

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=250 * 1024,   # ~250 KB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    base.addHandler(file_handler)

    _BASE_CONFIGURED = True
    return base


def _ensure_console_handler(base: logging.Logger) -> None:
    global _HAS_CONSOLE_HANDLER
    if _HAS_CONSOLE_HANDLER:
        return

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler = logging.StreamHandler()
    # Terminal should show only INFO; warnings/errors still go to the file.
    console_handler.setLevel(logging.INFO)
    console_handler.addFilter(_OnlyInfoFilter())
    console_handler.setFormatter(fmt)
    base.addHandler(console_handler)
    _HAS_CONSOLE_HANDLER = True


def get_logger(name: str = "__main__", *, to_console: bool = False) -> logging.Logger:
    """
    Return a configured logger for the RAG_ingest pipeline.

    - Logs to /tmp/RAG_ingest/rag_ingest.log
    - Rotates up to 3 files at ~250 KB each
    - Only logs to console when requested (use in main only)
    """
    base = _configure_base_logger()
    if to_console:
        _ensure_console_handler(base)

    # Ensure per-module loggers route to the base handlers.
    if name == "rag_ingest":
        return base
    child_name = name if name.startswith("rag_ingest") else f"rag_ingest.{name}"
    child = logging.getLogger(child_name)
    child.setLevel(logging.INFO)
    child.propagate = True
    return child

