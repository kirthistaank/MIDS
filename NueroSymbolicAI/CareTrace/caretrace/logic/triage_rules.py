"""
Deterministic triage + medication safety rules (PyDatalog).

Scope: pediatric febrile illness with GI symptoms and dehydration risk (course bundle).
Session-scoped facts `cf(session_id, name, value)` keep rules module-level while allowing
multi-run evaluations without pyDatalog.clear() (which would strip rules).

Integrate your official Fever CPG as additional predicates / facts.
"""

from __future__ import annotations

import uuid
from typing import Any

from pyDatalog import pyDatalog

from caretrace.state import CaseFields, TriageDecision


# --- Module-level terms & rules (loaded once) ---
pyDatalog.create_terms(
    "cf, S, er_now, urgent_same_day, home_candidate, "
    "rule_fired, med_flag"
)

# Hard gates → ER
er_now(S) <= cf(S, "alertness", "altered")
er_now(S) <= cf(S, "breathing", "distress")
er_now(S) <= cf(S, "dehydration_severe", "yes")
er_now(S) <= cf(S, "fluid_intake", "none") & cf(S, "urine_last_8h", "no")
# Seattle Children’s Fever CPG — “Call the doctor” items mapped to immediate escalation
er_now(S) <= cf(S, "cpg_seizure", "yes")
er_now(S) <= cf(S, "cpg_infant_under_3mo_fever", "yes")

# Urgent same-day patterns (non-ER)
urgent_same_day(S) <= cf(S, "temp_f", "very_high") & ~er_now(S)
urgent_same_day(S) <= (
    cf(S, "vomiting", "repeated")
    & cf(S, "fluid_intake", "poor")
    & ~er_now(S)
)
urgent_same_day(S) <= cf(S, "breathing", "tachypnea_concern") & ~er_now(S)
urgent_same_day(S) <= cf(S, "cpg_fever_duration_3_days", "yes") & ~er_now(S)

# Home candidates (conservative; final disposition still ranked in Python)
home_candidate(S) <= (
    cf(S, "alertness", "normal")
    & cf(S, "breathing", "normal")
    & ~cf(S, "fluid_intake", "none")
    & ~er_now(S)
    & ~urgent_same_day(S)
)
home_candidate(S) <= (
    cf(S, "alertness", "sleepy_ok")
    & cf(S, "breathing", "normal")
    & ~cf(S, "fluid_intake", "none")
    & ~er_now(S)
    & ~urgent_same_day(S)
)

# Audit trace
rule_fired(S, "R_ER_ALERTNESS") <= cf(S, "alertness", "altered")
rule_fired(S, "R_ER_BREATHING") <= cf(S, "breathing", "distress")
rule_fired(S, "R_ER_DEHYDRATION_SEVERE") <= cf(S, "dehydration_severe", "yes")
rule_fired(S, "R_ER_NO_FLUID_NO_URINE") <= (
    cf(S, "fluid_intake", "none") & cf(S, "urine_last_8h", "no")
)
rule_fired(S, "R_CPG_SEIZURE") <= cf(S, "cpg_seizure", "yes")
rule_fired(S, "R_CPG_INFANT_UNDER_3MO_FEVER") <= cf(S, "cpg_infant_under_3mo_fever", "yes")
rule_fired(S, "R_URGENT_VERY_HIGH_FEVER") <= cf(S, "temp_f", "very_high")
rule_fired(S, "R_URGENT_REPEATED_VOMIT_POOR_FLUID") <= (
    cf(S, "vomiting", "repeated") & cf(S, "fluid_intake", "poor")
)
rule_fired(S, "R_URGENT_TACHYPNEA_CONCERN") <= cf(S, "breathing", "tachypnea_concern")
rule_fired(S, "R_URGENT_FEVER_OVER_3_DAYS") <= cf(S, "cpg_fever_duration_3_days", "yes")
rule_fired(S, "R_HOME_CONSERVATIVE") <= home_candidate(S)

med_flag(S, "dehydration_avoid_nsaid_or_use_with_caution") <= cf(
    S, "dehydration_risk", "yes"
)
med_flag(S, "antibiotic_on_file_review_interactions") <= cf(S, "on_antibiotic", "yes")
med_flag(S, "cpg_ibuprofen_under_6mo_requires_clinician") <= cf(
    S, "cpg_ibuprofen_contraindicated_age", "yes"
)
med_flag(S, "cpg_no_routine_antipyretic_under_3mo") <= cf(
    S, "cpg_acetaminophen_under_3mo_requires_clinician", "yes"
)


def _add_cf(session: str, name: str, value: str) -> None:
    + cf(session, name, value)  # noqa: F821


def _case_to_facts(session: str, case: CaseFields) -> None:
    a = case.get("alertness", "unknown")
    if a != "unknown":
        _add_cf(session, "alertness", str(a))

    b = case.get("breathing", "unknown")
    if b != "unknown":
        _add_cf(session, "breathing", str(b))

    fi = case.get("fluid_intake", "unknown")
    if fi != "unknown":
        _add_cf(session, "fluid_intake", str(fi))

    u = case.get("urine_last_8h", "unknown")
    if u != "unknown":
        _add_cf(session, "urine_last_8h", str(u))

    v = case.get("vomiting", "unknown")
    if v != "unknown":
        _add_cf(session, "vomiting", str(v))

    tf = case.get("temp_f")
    if isinstance(tf, (int, float)):
        if tf >= 104.0:
            _add_cf(session, "temp_f", "very_high")
        elif tf >= 103.0:
            _add_cf(session, "temp_f", "high")
        else:
            _add_cf(session, "temp_f", "non_extreme")
    elif case.get("temp_unknown"):
        _add_cf(session, "temp_f", "unknown")

    poor_fluid = fi in ("poor", "none") if fi != "unknown" else False
    no_urine = u == "no"
    if poor_fluid and no_urine:
        _add_cf(session, "dehydration_severe", "yes")
    elif poor_fluid or no_urine:
        _add_cf(session, "dehydration_risk", "yes")

    meds = case.get("current_meds") or []
    if any(str(m).strip() for m in meds):
        _add_cf(session, "on_antibiotic", "yes")

    if case.get("seizure") == "yes":
        _add_cf(session, "cpg_seizure", "yes")

    age_months: float | None = case.get("age_months")
    if age_months is None and case.get("age_years") is not None:
        age_months = float(case["age_years"]) * 12.0  # type: ignore[index]
    if isinstance(age_months, (int, float)):
        if float(age_months) < 6.0:
            _add_cf(session, "cpg_ibuprofen_contraindicated_age", "yes")
        if float(age_months) < 3.0:
            _add_cf(session, "cpg_acetaminophen_under_3mo_requires_clinician", "yes")

    tf_val = case.get("temp_f")
    if (
        isinstance(age_months, (int, float))
        and float(age_months) < 3.0
        and isinstance(tf_val, (int, float))
        and float(tf_val) > 100.4
    ):
        # CPG: <3 months with fever — call right away (modeled as ER_NOW)
        _add_cf(session, "cpg_infant_under_3mo_fever", "yes")

    fd = case.get("fever_duration_hours")
    if isinstance(fd, (int, float)) and float(fd) >= 72.0:
        _add_cf(session, "cpg_fever_duration_3_days", "yes")


def _rules_for_session(session: str) -> list[str]:
    R = pyDatalog.Variable()
    try:
        rows = list(rule_fired(session, R))  # type: ignore[name-defined]
        return [row[0] for row in rows if row]
    except Exception:
        return []


def _med_flags_for_session(session: str) -> list[str]:
    M = pyDatalog.Variable()
    try:
        rows = list(med_flag(session, M))  # type: ignore[name-defined]
        return [row[0] for row in rows if row]
    except Exception:
        return []


def required_missing(case: CaseFields) -> list[str]:
    """Must-ask fields before a disposition (executable intake policy)."""
    missing: list[str] = []

    tf = case.get("temp_f")
    temp_unknown = bool(case.get("temp_unknown"))
    if tf is None and not temp_unknown:
        missing.append("temperature (or confirm unknown)")

    if case.get("alertness", "unknown") == "unknown":
        missing.append("alertness / responsiveness")

    if case.get("breathing", "unknown") == "unknown":
        missing.append("breathing")

    if case.get("fluid_intake", "unknown") == "unknown":
        missing.append("fluid intake")

    if case.get("urine_last_8h", "unknown") == "unknown":
        missing.append("urination in the last 6–8 hours")

    return missing


def evaluate_triage(case: CaseFields, missing_required: list[str]) -> TriageDecision:
    """
    Returns disposition + rule trace. If required fields missing, caller should ask
    questions (we return OUT_OF_SCOPE with reason incomplete_intake).
    """
    if case.get("intake_declined") and missing_required:
        return TriageDecision(
            disposition="OUT_OF_SCOPE",
            rule_ids=[],
            missing_required=[],
            med_flags=[],
            out_of_scope_reason="intake_declined",
        )

    if missing_required:
        return TriageDecision(
            disposition="OUT_OF_SCOPE",
            rule_ids=[],
            missing_required=list(missing_required),
            med_flags=[],
            out_of_scope_reason="incomplete_intake",
        )

    session = str(uuid.uuid4())
    _case_to_facts(session, case)

    er = bool(er_now(session))  # type: ignore[name-defined]
    ug = bool(urgent_same_day(session))  # type: ignore[name-defined]
    hm = bool(home_candidate(session))  # type: ignore[name-defined]

    rules = _rules_for_session(session)
    mflags = _med_flags_for_session(session)

    if er:
        return TriageDecision(
            disposition="ER_NOW",
            rule_ids=rules or ["R_ER_UNSPECIFIED"],
            missing_required=[],
            med_flags=mflags,
            out_of_scope_reason=None,
        )
    if ug:
        return TriageDecision(
            disposition="URGENT_SAME_DAY",
            rule_ids=rules,
            missing_required=[],
            med_flags=mflags,
            out_of_scope_reason=None,
        )
    if hm:
        return TriageDecision(
            disposition="HOME_MANAGEMENT",
            rule_ids=rules or ["R_HOME_CONSERVATIVE"],
            missing_required=[],
            med_flags=mflags,
            out_of_scope_reason=None,
        )

    return TriageDecision(
        disposition="OUT_OF_SCOPE",
        rule_ids=rules,
        missing_required=[],
        med_flags=mflags,
        out_of_scope_reason="undetermined_safe_disposition",
    )
