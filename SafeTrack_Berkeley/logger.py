"""
logger.py
---------
Centralised logging setup for the Berkeley Bike Safety Route Planner.

All modules import `get_logger(__name__)` to obtain a named logger that
writes to both the console (coloured, human-readable) and a rotating log
file under logs/bike_safety.log.

Usage
-----
    from logger import get_logger
    log = get_logger(__name__)
    log.info("Route calculation started")
    log.warning("No crash data found for segment")
    log.error("Graph build failed: %s", err)
"""

import logging
import logging.handlers
import os
from pathlib import Path

# ── Colour codes for console output (green theme) ────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[32m"
CYAN   = "\033[36m"
YELLOW = "\033[33m"
RED    = "\033[31m"
DIM    = "\033[2m"

LEVEL_COLOURS = {
    "DEBUG":    DIM    + "DEBUG" + RESET,
    "INFO":     GREEN  + "INFO " + RESET,
    "WARNING":  YELLOW + "WARN " + RESET,
    "ERROR":    RED    + "ERROR" + RESET,
    "CRITICAL": BOLD   + RED + "CRIT " + RESET,
}


class ColouredFormatter(logging.Formatter):
    """Custom formatter that injects ANSI colour codes into console output."""

    FMT = (
        DIM + "%(asctime)s" + RESET
        + "  {level}"
        + CYAN + "  %(name)-30s" + RESET
        + "  %(message)s"
    )

    def format(self, record: logging.LogRecord) -> str:
        level_tag = LEVEL_COLOURS.get(record.levelname, record.levelname)
        formatter = logging.Formatter(
            self.FMT.format(level=level_tag),
            datefmt="%H:%M:%S",
        )
        return formatter.format(record)


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger configured with:
      - A coloured StreamHandler for console output.
      - A RotatingFileHandler writing to logs/bike_safety.log
        (max 5 MB per file, keeps last 3 files).

    Parameters
    ----------
    name : str
        Typically ``__name__`` of the calling module.

    Returns
    -------
    logging.Logger
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if get_logger is called multiple times
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # ── Console handler (INFO and above, coloured) ────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(ColouredFormatter())
    logger.addHandler(console_handler)

    # ── File handler (DEBUG and above, plain text, rotating) ─────────────
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "bike_safety.log"

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB per file
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s  %(levelname)-8s  %(name)-30s  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(file_handler)

    # Prevent log records propagating to the root logger
    logger.propagate = False

    return logger