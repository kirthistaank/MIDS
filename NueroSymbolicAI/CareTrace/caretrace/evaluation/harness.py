"""
Evaluation harness: replay multi-turn transcripts and assert expected dispositions.

Usage:
  CARETRACE_MOCK_LLM=1 CARETRACE_SKIP_NEO4J=1 python -m caretrace.evaluation.harness
  python -m caretrace.evaluation.harness path/to/scenarios.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from caretrace.orchestration.graph import run_turn
from caretrace.state import CareTraceState, default_case


@dataclass(frozen=True)
class ScenarioRow:
    id: str
    description: str
    expected: str
    turns: list[str]


_ALLOWED = frozenset(
    {"ER_NOW", "URGENT_SAME_DAY", "HOME_MANAGEMENT", "OUT_OF_SCOPE"}
)


def _load_csv(path: Path) -> list[ScenarioRow]:
    rows: list[ScenarioRow] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            sid = (r.get("id") or "").strip()
            desc = (r.get("description") or "").strip()
            exp = (r.get("expected_disposition") or "").strip()
            if exp not in _ALLOWED:
                raise ValueError(f"Invalid expected_disposition {exp!r} for {sid}")
            raw_turns = r.get("turns_json") or "[]"
            turns = json.loads(raw_turns)
            if not isinstance(turns, list) or not all(isinstance(t, str) for t in turns):
                raise ValueError(f"Invalid turns_json for {sid}")
            rows.append(
                ScenarioRow(
                    id=sid,
                    description=desc,
                    expected=exp,
                    turns=turns,
                )
            )
    return rows


def replay_turns(turns: list[str]) -> dict[str, Any]:
    """Run full graph for each user turn; return final state dict."""
    state: CareTraceState = {
        "messages": [],
        "case": default_case(),
        "kg_annotations": [],
        "turn": 0,
    }
    for text in turns:
        state = dict(state)
        state["raw_user_text"] = text
        msgs = list(state.get("messages") or [])
        msgs.append({"role": "user", "content": text})
        state["messages"] = msgs
        state = run_turn(state)  # type: ignore[assignment]
    return state


def run_file(path: Path) -> int:
    scenarios = _load_csv(path)
    failures: list[str] = []
    for s in scenarios:
        final = replay_turns(s.turns)
        dec = (final.get("decision") or {}).get("disposition")
        if dec != s.expected:
            failures.append(
                f"[{s.id}] expected {s.expected!r}, got {dec!r} — {s.description}"
            )
    if failures:
        print("FAILURES:\n" + "\n".join(failures))
        return 1
    print(f"OK: {len(scenarios)} scenario(s) from {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="CareTrace scenario evaluation harness")
    p.add_argument(
        "csv_path",
        nargs="?",
        default=str(Path(__file__).resolve().parent / "scenarios.csv"),
        help="CSV with id,description,expected_disposition,turns_json",
    )
    args = p.parse_args(argv)
    return run_file(Path(args.csv_path))


if __name__ == "__main__":
    raise SystemExit(main())
