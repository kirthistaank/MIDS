"""Pretty-print CareTrace decisions and assistant replies (e.g. notebooks, terminals)."""

from __future__ import annotations

import json
import re
from typing import Any

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str | None) -> str:
    """Remove terminal ANSI escape sequences from *text*."""
    return _ANSI_RE.sub("", text or "")


def reply_paragraphs(text: str | None) -> list[str]:
    """Split stripped text on blank lines into non-empty paragraphs."""
    return [p.strip() for p in strip_ansi(text).split("\n\n") if p.strip()]


def display_caretrace_turn(
    decision: dict[str, Any] | None,
    assistant_reply: str | None,
    *,
    max_reply_chars: int | None = None,
) -> None:
    """Print structured *decision* and *assistant_reply* sections (ANSI stripped)."""
    d = decision or {}
    reply = assistant_reply or ""
    if max_reply_chars is not None:
        reply = reply[:max_reply_chars]

    print("=== Decision (structured) ===")
    print(json.dumps(d, indent=2, default=str))
    print("\n=== Assistant reply (by section) ===")
    for i, block in enumerate(reply_paragraphs(reply), 1):
        print(f"\n--- Section {i} ---")
        print(block)
