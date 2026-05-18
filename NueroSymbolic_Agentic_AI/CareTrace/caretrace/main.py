"""
CLI entrypoint for CareTrace multi-turn demos.

Usage:
  CARETRACE_MOCK_LLM=1 python -m caretrace.main

Environment:
  OPENAI_API_KEY / OPENAI_MODEL — optional; without them, heuristics + templates run.
  NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD / NEO4J_DATABASE — optional graph grounding
  (course Aura DB: NEO4J_*_KGA fallbacks are also read in Settings).
  CARETRACE_EXIT_ON_COMPLETE=1 — quit the CLI after a turn with no missing required fields
  (default keeps prompting until you type quit).
  CARETRACE_USE_LAG=1 — Logic-Augmented Generation for explanations (requires OpenAI; ignored if mock LLM or no API key).
"""

from __future__ import annotations

from caretrace.config import Settings
from caretrace.orchestration.graph import run_turn
from caretrace.state import CareTraceState, default_case


def _bold(text: str) -> str:
    """Render terminal label text in ANSI bold."""
    return f"\033[1m{text}\033[0m"


def main() -> None:
    settings = Settings.from_env()
    lag_active = (
        settings.use_lag
        and not settings.use_mock_llm
        and bool(settings.openai_api_key)
    )
    print("--------------------------------")
    print("use lag: ", settings.use_lag)
    print("lag explanations active: ", lag_active)
    print("use mock llm: ", settings.use_mock_llm)
    print("openai api key: ", bool(settings.openai_api_key))
    
    print("--------------------------------")
    print(
        "CareTrace (scoped pediatric febrile + GI + dehydration). Type 'quit' to exit.\n"
        f"mock_llm={settings.use_mock_llm}  openai={'set' if settings.openai_api_key else 'unset'}  "
        f"neo4j={'skipped' if settings.skip_neo4j else ('set' if settings.neo4j_uri else 'unset')}  "
        f"use_lag={settings.use_lag}  lag_explanations_active={lag_active}\n"
    )
    if settings.use_lag and not lag_active:
        print(
            "(CARETRACE_USE_LAG=1 is set but LAG is inactive: unset CARETRACE_MOCK_LLM and set OPENAI_API_KEY "
            "for Logic-Augmented explanations; otherwise template text is used.)\n"
        )
    state: CareTraceState = {
        "messages": [],
        "case": default_case(),
        "kg_annotations": [],
        "turn": 0,
    }
    if settings.exit_on_complete:
        print("(CARETRACE_EXIT_ON_COMPLETE=1: session ends after a full triage conclusion.)\n")
    while True:
        user = input(f"\n{_bold('Caregiver:')} ").strip()
        if user.lower() in {"q", "quit", "exit"}:
            break
        state["raw_user_text"] = user
        msgs = list(state.get("messages") or [])
        msgs.append({"role": "user", "content": user})
        state["messages"] = msgs
        state = run_turn(state)
        print(f"\n{_bold('CareTrace:')}\n" + (state.get("assistant_reply") or ""))
        if settings.exit_on_complete:
            decision = state.get("decision") or {}
            miss = decision.get("missing_required") or []
            if not miss:
                print("\n(Required intake complete — exiting. Set CARETRACE_EXIT_ON_COMPLETE=0 to stay in the loop.)")
                break


if __name__ == "__main__":
    main()
