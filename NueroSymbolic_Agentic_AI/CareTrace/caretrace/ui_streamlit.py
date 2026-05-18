"""
Streamlit UI for CareTrace.

Run:
  streamlit run caretrace/ui_streamlit.py
"""

from __future__ import annotations

import streamlit as st

from caretrace.orchestration.graph import run_turn
from caretrace.state import CareTraceState, default_case


def _init_state() -> CareTraceState:
    return {
        "messages": [],
        "case": default_case(),
        "kg_annotations": [],
        "turn": 0,
    }


def _reset() -> None:
    st.session_state.ct_state = _init_state()
    st.session_state.ct_chat = []


def _assistant_footer(state: CareTraceState) -> str:
    decision = state.get("decision") or {}
    disposition = decision.get("disposition", "UNKNOWN")
    missing = decision.get("missing_required") or []
    med_flags = decision.get("med_flags") or []
    bits = [f"Disposition: `{disposition}`"]
    if missing:
        bits.append(f"Missing required: {len(missing)}")
    if med_flags:
        bits.append(f"Med flags: {', '.join(str(x) for x in med_flags)}")
    return " | ".join(bits)


def main() -> None:
    st.set_page_config(page_title="CareTrace UI", page_icon="🩺", layout="wide")
    st.title("CareTrace Interactive UI")
    st.caption("Chat-based pediatric triage demo (course prototype).")

    if "ct_state" not in st.session_state:
        st.session_state.ct_state = _init_state()
    if "ct_chat" not in st.session_state:
        st.session_state.ct_chat = []

    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("Reset session"):
            _reset()
            st.rerun()
    with col_b:
        show_debug = st.checkbox("Show structured state/debug", value=False)

    for turn in st.session_state.ct_chat:
        with st.chat_message("user"):
            st.markdown(turn["user"])
        with st.chat_message("assistant"):
            st.markdown(turn["assistant"])
            st.caption(turn["meta"])

    user_text = st.chat_input("Describe your child’s symptoms...")
    if not user_text:
        return

    with st.chat_message("user"):
        st.markdown(user_text)

    state: CareTraceState = st.session_state.ct_state
    state["raw_user_text"] = user_text
    msgs = list(state.get("messages") or [])
    msgs.append({"role": "user", "content": user_text})
    state["messages"] = msgs

    with st.spinner("CareTrace is reasoning..."):
        new_state = run_turn(state)

    assistant_text = new_state.get("assistant_reply") or "(no response)"
    meta = _assistant_footer(new_state)
    with st.chat_message("assistant"):
        st.markdown(assistant_text)
        st.caption(meta)

    st.session_state.ct_state = new_state
    st.session_state.ct_chat.append(
        {"user": user_text, "assistant": assistant_text, "meta": meta}
    )

    if show_debug:
        st.divider()
        st.subheader("Debug snapshot")
        st.write(
            {
                "turn": new_state.get("turn"),
                "case": new_state.get("case"),
                "decision": new_state.get("decision"),
                "kg_annotations": new_state.get("kg_annotations"),
            }
        )


if __name__ == "__main__":
    main()

