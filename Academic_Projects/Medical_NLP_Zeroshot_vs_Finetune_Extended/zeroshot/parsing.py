"""Constraint-based output parsing (Section 3.3)."""

import difflib
import math
from typing import Any, List


def coerce_text(value: Any, max_len: int | None = 2000) -> str:
    """Convert a dataframe cell to a safe string for prompts (handles NaN, None, numbers)."""
    if value is None:
        s = ""
    elif isinstance(value, float) and math.isnan(value):
        s = ""
    elif isinstance(value, (float, int)) and not isinstance(value, bool):
        s = str(value).strip()
    else:
        s = str(value).strip()
        if s.lower() == "nan":
            s = ""
    if max_len is not None:
        return s[:max_len]
    return s


def normalize_label(raw: str) -> str:
    return raw.strip().upper().replace(" ", "_").replace("-", "_")


def _fuzzy_match(query: str, choices: List[str], threshold: int) -> str | None:
    try:
        from rapidfuzz import fuzz, process

        match = process.extractOne(query, choices, scorer=fuzz.ratio)
        if match and match[1] >= threshold:
            return match[0]
    except ImportError:
        best = difflib.get_close_matches(query, choices, n=1, cutoff=threshold / 100.0)
        if best:
            return best[0]
    return None


def validate_prediction(raw_output: str, valid_labels: List[str], fuzzy_threshold: int = 80) -> str:
    """Normalize and validate zero-shot model output."""
    cleaned = normalize_label(raw_output)
    valid_upper = [normalize_label(v) for v in valid_labels]

    if cleaned in valid_upper:
        return cleaned

    for prefix in ("CATEGORY:", "LABEL:", "SENTIMENT:", "CLASSIFICATION:", "OUTPUT:"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
            if cleaned in valid_upper:
                return cleaned

    matched = _fuzzy_match(cleaned, valid_upper, fuzzy_threshold)
    return matched if matched else "INVALID"
