"""
Bounded medication guidance with explicit provenance strings.

Integrated summary text from **Seattle Children’s — Fever** (patient education)
`https://www.seattlechildrens.org/health-safety/illness/fever` (local PDF in `Docs/`).

This module must never invent doses: unknown weight → ask, do not compute.
"""

from __future__ import annotations

from dataclasses import dataclass

from caretrace.state import CaseFields


CPG_FEVER_SCH_URL = "https://www.seattlechildrens.org/health-safety/illness/fever"


def _age_months(case: CaseFields) -> float | None:
    """Best-effort age in months for CPG age gates."""
    am = case.get("age_months")
    if isinstance(am, (int, float)):
        return float(am)
    ay = case.get("age_years")
    if isinstance(ay, (int, float)):
        return float(ay) * 12.0
    return None


@dataclass(frozen=True)
class MedGuidance:
    text: str
    provenance: str
    must_escalate: bool  # if True, surface "do not dose without clinician"


def seattle_childrens_fever_cpg_summary() -> str:
    """Short paraphrase of the CPG’s non-dosing guidance (course integration; cite URL in UI/report)."""
    return (
        "CPG highlights (Seattle Children’s Fever): fever is temperature over 100.4°F (38°C). "
        "You do not always need to treat a fever—watch how the child acts and prioritize fluids. "
        "Never give aspirin; do not give fever medicine to babies under 3 months unless a clinician says so; "
        "do not use ibuprofen under 6 months unless a clinician says so; "
        "do not alternate acetaminophen and ibuprofen unless a clinician instructs you. "
        f"Full source: {CPG_FEVER_SCH_URL}"
    )


def acetaminophen_note(case: CaseFields) -> MedGuidance:
    w = case.get("weight_kg")
    am = _age_months(case)
    if am is not None and am < 3.0:
        return MedGuidance(
            text="For infants under 3 months with fever, the CPG advises not to give fever medicine "
            "unless a clinician tells you to—seek clinician guidance rather than self-dosing.",
            provenance=f"Seattle Children’s Fever CPG — “Don’t give fever medicine to a baby under 3 months old, unless told to by a doctor.” ({CPG_FEVER_SCH_URL})",
            must_escalate=True,
        )
    if w is None:
        return MedGuidance(
            text="For fever comfort, acetaminophen dosing depends on your child’s exact weight "
            "and the product concentration (mg per mL). I don’t have a reliable weight yet—"
            "please confirm weight or use the dosing chart on the product packaging / your clinician’s instructions.",
            provenance=f"Seattle Children’s Fever CPG — weight-based dosing + measuring tool ({CPG_FEVER_SCH_URL})",
            must_escalate=False,
        )
    dose_mg = round(15.0 * float(w), 1)
    return MedGuidance(
        text=f"Illustrative acetaminophen total dose ≈ {dose_mg} mg per dose (15 mg/kg) "
        f"for weight {w} kg — VERIFY concentration and maximum daily doses on your specific formulation.",
        provenance=f"Illustrative mg/kg scaffold — align to your formulary; CPG requires correct dose by weight ({CPG_FEVER_SCH_URL})",
        must_escalate=False,
    )


def ibuprofen_note(case: CaseFields, dehydration_risk: bool) -> MedGuidance:
    am = _age_months(case)
    if am is not None and am < 6.0:
        return MedGuidance(
            text="Do not use ibuprofen for babies less than 6 months unless a clinician tells you to.",
            provenance=f"Seattle Children’s Fever CPG ({CPG_FEVER_SCH_URL})",
            must_escalate=True,
        )
    if dehydration_risk:
        return MedGuidance(
            text="If dehydration is a concern, avoid ibuprofen unless a clinician has advised otherwise; "
            "prefer acetaminophen for fever discomfort and focus on hydration.",
            provenance="Dehydration + NSAID risk coupling (insert citation)",
            must_escalate=False,
        )
    return MedGuidance(
        text="Ibuprofen may be appropriate only if hydration is adequate and the child is over 6 months old; "
        "confirm dose using weight-based guidance for your product concentration.",
        provenance=f"Seattle Children’s Fever CPG — “You can give acetaminophen or ibuprofen (Motrin) if your child is over 6 months old.” ({CPG_FEVER_SCH_URL})",
        must_escalate=False,
    )
