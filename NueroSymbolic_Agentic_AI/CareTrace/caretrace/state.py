from __future__ import annotations

from typing import Any, Literal, TypedDict, cast

Disposition = Literal["ER_NOW", "URGENT_SAME_DAY", "HOME_MANAGEMENT", "OUT_OF_SCOPE"]


class CaseFields(TypedDict, total=False):
    """Canonical clinical fields after interpretation + optional KG normalization."""

    age_years: float | None
    age_months: float | None  # if set, takes precedence over age_years for infant rules
    weight_kg: float | None
    temp_f: float | None
    temp_unknown: bool
    vomiting: Literal["none", "once", "repeated", "unknown"]
    alertness: Literal["normal", "sleepy_ok", "altered", "unknown"]
    breathing: Literal["normal", "tachypnea_concern", "distress", "unknown"]
    fluid_intake: Literal["good", "some", "poor", "none", "unknown"]
    urine_last_8h: Literal["yes", "no", "unknown"]
    current_meds: list[str]
    last_antibiotic_dose_hours_ago: float | None
    local_outbreak_context: str | None  # probabilistic prior only; never overrides gates
    seizure: Literal["yes", "no", "unknown"]
    fever_duration_hours: float | None  # for CPG “>3 days” / prolonged fever triggers
    intake_declined: bool  # caregiver cannot/will not provide required workup (e.g. “I don’t know”)


class TriageDecision(TypedDict, total=False):
    disposition: Disposition
    rule_ids: list[str]
    missing_required: list[str]
    med_flags: list[str]
    out_of_scope_reason: str | None


class CareTraceState(TypedDict, total=False):
    """LangGraph state."""

    messages: list[dict[str, str]]  # {"role": "user"|"assistant", "content": str}
    raw_user_text: str
    case: CaseFields
    kg_annotations: list[dict[str, Any]]
    decision: TriageDecision
    assistant_reply: str
    turn: int


REQUIRED_FOR_SAFE_PLAN: tuple[str, ...] = (
    "temp_f_or_unknown_ack",
    "alertness",
    "breathing",
    "fluid_intake",
    "urine_last_8h",
)


def default_case() -> CaseFields:
    return cast(
        CaseFields,
        {
            "age_years": None,
            "age_months": None,
            "weight_kg": None,
            "temp_f": None,
            "temp_unknown": False,
            "vomiting": "unknown",
            "alertness": "unknown",
            "breathing": "unknown",
            "fluid_intake": "unknown",
            "urine_last_8h": "unknown",
            "current_meds": [],
            "last_antibiotic_dose_hours_ago": None,
            "local_outbreak_context": None,
            "seizure": "unknown",
            "fever_duration_hours": None,
            "intake_declined": False,
        },
    )
