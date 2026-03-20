"""
logger.py — centralised logging configuration.
- Rotating file handler: 128MB per file, max 3 files, purge the rest
- Logs to /tmp/confidenceos/
- Console handler for dev visibility
- One logger per module via get_logger(name)
"""

import logging
import os
from logging.handlers import RotatingFileHandler

# ── Config ────────────────────────────────────────────────────────────────────

LOG_DIR      = "/tmp/confidenceos"
LOG_FILE     = os.path.join(LOG_DIR, "app.log")
MAX_BYTES    = 128 * 1024 * 1024   # 128 MB
BACKUP_COUNT = 3                    # keep 3 rotated files, purge the rest
LOG_FORMAT   = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
DATE_FORMAT  = "%Y-%m-%d %H:%M:%S"


def _setup_root_logger():
    os.makedirs(LOG_DIR, exist_ok=True)

    root = logging.getLogger("confidenceos")
    root.setLevel(logging.DEBUG)

    if root.handlers:
        return root   # already configured

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # ── Rotating file handler ─────────────────────────────────────────────────
    fh = RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    root.addHandler(fh)

    # ── Console handler (INFO and above) ──────────────────────────────────────
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    root.addHandler(ch)

    return root


# Initialise on import
_setup_root_logger()


def get_logger(name: str) -> logging.Logger:
    """
    Return a child logger under the 'confidenceos' namespace.
    Usage:  from logger import get_logger
            log = get_logger(__name__)
    """
    return logging.getLogger(f"confidenceos.{name}")
