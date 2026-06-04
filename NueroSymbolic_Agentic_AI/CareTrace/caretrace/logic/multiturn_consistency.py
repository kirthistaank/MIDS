"""
Multi-turn consistency checking: Detect changes and conflicts across conversation turns.

Tracks:
- Field changes (temp reported as 102°F, then 105°F)
- Contradictory updates (said "alert", then "not responding")
- Confidence in extracted values over time
"""

from __future__ import annotations

from typing import Any

from caretrace.state import CaseFields


class ConversationHistory:
    """Track case field changes across conversation turns."""

    def __init__(self):
        self.turns: list[dict[str, Any]] = []
        self.field_history: dict[str, list[tuple[int, Any]]] = {}  # field -> [(turn, value), ...]

    def add_turn(self, turn_number: int, case: CaseFields) -> None:
        """Record a turn with extracted case fields."""
        self.turns.append({"turn": turn_number, "case": dict(case)})

        # Track each field value over time
        for key, value in case.items():
            if value is None:
                continue
            if key not in self.field_history:
                self.field_history[key] = []
            self.field_history[key].append((turn_number, value))

    def get_field_changes(self, field: str) -> list[tuple[int, Any, Any]]:
        """Get all changes to a field. Returns [(turn, old_value, new_value), ...]"""
        if field not in self.field_history:
            return []

        history = self.field_history[field]
        if len(history) < 2:
            return []

        changes = []
        for i in range(1, len(history)):
            turn, value = history[i]
            prev_turn, prev_value = history[i - 1]
            if value != prev_value:
                changes.append((turn, prev_value, value))

        return changes

    def detect_suspicious_changes(self) -> list[str]:
        """Detect suspicious field changes that might indicate error."""
        issues = []

        # Temperature changes > 2°F are suspicious
        temp_changes = self.get_field_changes("temp_f")
        for turn, old_val, new_val in temp_changes:
            if abs(new_val - old_val) > 2.0:
                issues.append(
                    f"Large temperature change in turn {turn}: {old_val}°F → {new_val}°F (Δ{abs(new_val - old_val)}°F)"
                )

        # Alertness flipping is suspicious
        alertness_changes = self.get_field_changes("alertness")
        for turn, old_val, new_val in alertness_changes:
            if old_val == "normal" and new_val == "altered":
                issues.append(f"Alertness declined in turn {turn}: normal → altered (possible deterioration)")
            elif old_val == "altered" and new_val == "normal":
                issues.append(f"Alertness improved in turn {turn}: altered → normal (verify accuracy)")

        # Age should never change
        age_changes = self.get_field_changes("age_years")
        if age_changes:
            issues.append(f"Age changed: {age_changes} (age should not change between turns)")

        age_m_changes = self.get_field_changes("age_months")
        if age_m_changes:
            issues.append(f"Age (months) changed: {age_m_changes} (age should not change)")

        return issues

    def get_consistent_value(self, field: str, prefer_latest: bool = True) -> Any:
        """Get the most consistent value for a field across turns."""
        if field not in self.field_history:
            return None

        history = self.field_history[field]

        if not history:
            return None

        if prefer_latest:
            # Return latest value
            return history[-1][1]
        else:
            # Return most common value
            from collections import Counter

            values = [val for _, val in history]
            return Counter(values).most_common(1)[0][0]

    def flag_inconsistency(self, field: str, threshold: int = 2) -> bool:
        """Check if a field has been reported inconsistently."""
        if field not in self.field_history:
            return False

        history = self.field_history[field]

        # Count unique values
        unique_values = set(val for _, val in history)
        return len(unique_values) >= threshold


def compare_cases(previous: CaseFields, current: CaseFields) -> dict[str, Any]:
    """Compare two case snapshots and report changes."""
    changes = {
        "added": {},  # New fields provided
        "changed": {},  # Existing fields with different values
        "clarified": {},  # Fields changed from "unknown" to specific value
    }

    for key, current_value in current.items():
        previous_value = previous.get(key)

        if previous_value is None and current_value is not None:
            changes["added"][key] = current_value
        elif previous_value != current_value and current_value is not None:
            if previous_value == "unknown" or (isinstance(previous_value, bool) and not previous_value):
                changes["clarified"][key] = (previous_value, current_value)
            else:
                changes["changed"][key] = (previous_value, current_value)

    return changes
