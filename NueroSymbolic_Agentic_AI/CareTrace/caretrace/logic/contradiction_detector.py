"""
Contradiction detection: Find and flag conflicting information in case data.

Examples:
- "fever" AND "no fever"
- "drinking fluids" AND "not drinking"
- "wet diapers" AND "no urination"
"""

from __future__ import annotations

from typing import Any

from caretrace.state import CaseFields


def _detect_text_contradictions(user_text: str) -> list[str]:
    """Detect contradictions in user input text."""
    contradictions = []
    text_lower = user_text.lower()

    # Fever contradictions
    has_fever = any(x in text_lower for x in ["fever", "high temperature", "temp", "hot"])
    no_fever = any(x in text_lower for x in ["no fever", "not fever", "without fever", "no temperature"])
    if has_fever and no_fever:
        contradictions.append("Conflicting fever status: mentions both 'fever' and 'no fever'")

    # Fluid intake contradictions
    drinking = any(x in text_lower for x in ["drinking", "fluids", "water", "milk", "juice"])
    not_drinking = any(x in text_lower for x in ["not drinking", "won't drink", "refuses fluid", "no fluids"])
    if drinking and not_drinking:
        contradictions.append("Conflicting fluid intake: mentions both 'drinking' and 'not drinking'")

    # Urination contradictions
    urinating = any(x in text_lower for x in ["peed", "urinated", "wet diaper", "urine"])
    not_urinating = any(x in text_lower for x in ["no pee", "hasn't peed", "dry diaper", "no urine"])
    if urinating and not_urinating:
        contradictions.append("Conflicting urination: mentions both 'wet diaper' and 'no urine'")

    # Alertness contradictions
    alert = any(x in text_lower for x in ["alert", "awake", "responsive", "normal", "fine"])
    not_alert = any(x in text_lower for x in ["altered", "sleepy", "lethargic", "not responding", "unresponsive"])
    if alert and not_alert and "sleepy but" not in text_lower:  # Allow "sleepy but responsive"
        contradictions.append("Conflicting alertness: mentions both 'alert' and 'not responding'")

    return contradictions


def detect_field_contradictions(case: CaseFields) -> list[str]:
    """Detect contradictions between extracted fields."""
    contradictions = []

    # Temperature contradictions
    temp = case.get("temp_f")
    temp_unknown = case.get("temp_unknown")
    if temp is not None and temp_unknown:
        contradictions.append("Temperature contradiction: has both value and 'unknown' flag")

    # Age contradictions
    age_y = case.get("age_years")
    age_m = case.get("age_months")
    if age_y is not None and age_m is not None:
        # Check if they're consistent (allow 1-month tolerance for rounding)
        expected_months = age_y * 12
        if abs(age_m - expected_months) > 1:
            contradictions.append(
                f"Age contradiction: {age_y} years ({expected_months} months) conflicts with {age_m} months"
            )

    # Fluid vs urination logical contradiction
    # If taking fluids, should be urinating
    fluid = case.get("fluid_intake")
    urine = case.get("urine_last_8h")
    if fluid == "good" and urine == "no":
        contradictions.append("Logical contradiction: good fluid intake but no urination in 8 hours")

    # No fluid but urinating (less critical but odd)
    if fluid == "none" and urine == "yes":
        contradictions.append("Logical contradiction: no fluid intake but has urinated")

    return contradictions


def get_all_contradictions(case: CaseFields, user_text: str) -> list[str]:
    """Get all contradictions from text and extracted fields."""
    text_contradictions = _detect_text_contradictions(user_text)
    field_contradictions = detect_field_contradictions(case)
    return text_contradictions + field_contradictions


def has_contradictions(case: CaseFields, user_text: str) -> bool:
    """Check if there are any contradictions."""
    return bool(get_all_contradictions(case, user_text))
