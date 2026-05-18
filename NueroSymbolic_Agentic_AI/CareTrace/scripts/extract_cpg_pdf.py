#!/usr/bin/env python3
"""Extract text from the Seattle Children’s Fever PDF for report / diff review."""

from __future__ import annotations

import argparse
from pathlib import Path

from pypdf import PdfReader


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "pdf",
        nargs="?",
        default=str(
            Path(__file__).resolve().parents[1]
            / "Docs"
            / "CPG Fever - Safety and Wellness - Seattle Children's.pdf"
        ),
    )
    p.add_argument(
        "-o",
        "--out",
        default=str(
            Path(__file__).resolve().parents[1]
            / "Docs"
            / "CPG_Fever_Seattle_Childrens_extracted.txt"
        ),
    )
    args = p.parse_args()
    reader = PdfReader(args.pdf)
    parts = []
    for i, page in enumerate(reader.pages):
        parts.append(f"\n--- PAGE {i + 1} ---\n{(page.extract_text() or '').strip()}")
    Path(args.out).write_text("\n".join(parts).strip() + "\n", encoding="utf-8")
    print(f"Wrote {args.out} ({len(reader.pages)} pages)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
