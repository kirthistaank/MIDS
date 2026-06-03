"""
Orchestration Agent: LangGraph state machine for CareTrace.

Flow: interpret → KG annotate → safety logic → (explain | ask missing)
"""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, StateGraph

from caretrace.agents.explanation import explain
from caretrace.agents.interpretation import interpret_user_message
from caretrace.audit.postgres_logger import log_triage_decision
from caretrace.config import Settings
from caretrace.graph.fever_cpg_mentions import kg_mentions_from_case_and_text
from caretrace.graph.neo4j_client import close_driver, get_driver
from caretrace.graph.snomed_retrieval import annotate_case_mentions
from caretrace.logic.triage_rules import evaluate_triage, required_missing
from caretrace.state import CareTraceState, default_case


def node_interpret(state: CareTraceState) -> CareTraceState:
    settings = Settings.from_env()
    prior = state.get("case") or default_case()
    text = state.get("raw_user_text") or ""
    case = interpret_user_message(settings, prior, text)
    return {
        "case": case,
        "turn": int(state.get("turn") or 0) + 1,
    }


def node_kg(state: CareTraceState) -> CareTraceState:
    settings = Settings.from_env()
    if settings.skip_neo4j:
        return {"kg_annotations": []}
    driver = get_driver(settings)
    try:
        case = state.get("case") or default_case()
        raw = state.get("raw_user_text") or ""
        mentions = kg_mentions_from_case_and_text(dict(case), raw)
        ann = (
            annotate_case_mentions(driver, mentions, database=settings.neo4j_database)
            if mentions
            else []
        )
        return {"kg_annotations": ann}
    finally:
        close_driver(driver)


def node_safety(state: CareTraceState) -> CareTraceState:
    case = state.get("case") or default_case()
    miss = required_missing(case)
    decision = evaluate_triage(case, miss)
    return {"decision": decision}


def node_explain(state: CareTraceState) -> CareTraceState:
    settings = Settings.from_env()
    case = state.get("case") or default_case()
    decision = state.get("decision") or {}
    kg = state.get("kg_annotations") or []
    text = explain(settings, case, decision, kg)
    messages = list(state.get("messages") or [])
    messages.append({"role": "assistant", "content": text})
    return {"assistant_reply": text, "messages": messages}


def route_after_safety(
    state: CareTraceState,
) -> Literal["explain", "explain_incomplete"]:
    decision = state.get("decision") or {}
    miss = decision.get("missing_required") or []
    if miss:
        return "explain_incomplete"
    return "explain"


def node_explain_incomplete(state: CareTraceState) -> CareTraceState:
    """Bounded questions only — reuse explanation agent with incomplete decision."""
    settings = Settings.from_env()
    case = state.get("case") or default_case()
    decision = state.get("decision") or {}
    kg = state.get("kg_annotations") or []
    text = explain(settings, case, decision, kg)
    messages = list(state.get("messages") or [])
    messages.append({"role": "assistant", "content": text})
    return {"assistant_reply": text, "messages": messages}


def node_audit(state: CareTraceState) -> CareTraceState:
    """Log triage decision to audit database."""
    decision = state.get("decision") or {}

    log_triage_decision(
        turn_number=int(state.get("turn") or 0),
        disposition=decision.get("disposition", "UNKNOWN"),
        rules_fired=decision.get("rule_ids"),
        med_flags=decision.get("med_flags"),
        kg_evidence=state.get("kg_annotations"),
        case_fields=state.get("case"),
        raw_user_input=state.get("raw_user_text"),
        out_of_scope_reason=decision.get("out_of_scope_reason"),
    )
    return {}


def build_app():
    g = StateGraph(CareTraceState)
    g.add_node("interpret", node_interpret)
    g.add_node("kg", node_kg)
    g.add_node("safety", node_safety)
    g.add_node("explain", node_explain)
    g.add_node("explain_incomplete", node_explain_incomplete)
    g.add_node("audit", node_audit)

    g.set_entry_point("interpret")
    g.add_edge("interpret", "kg")
    g.add_edge("kg", "safety")
    g.add_conditional_edges(
        "safety",
        route_after_safety,
        {
            "explain": "explain",
            "explain_incomplete": "explain_incomplete",
        },
    )
    g.add_edge("explain", "audit")
    g.add_edge("explain_incomplete", "audit")
    g.add_edge("audit", END)
    return g.compile()


APP = build_app()


def run_turn(state: CareTraceState) -> CareTraceState:
    """Single invoke; merge output with prior state for multi-turn CLI."""
    out = APP.invoke(state)
    merged = dict(state)
    merged.update(out)
    return merged  # type: ignore[return-value]
