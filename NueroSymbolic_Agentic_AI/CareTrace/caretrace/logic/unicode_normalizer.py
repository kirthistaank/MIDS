"""
Unicode normalization for robust text processing.

Handles:
- Emoji digits: 1️⃣ → 1
- Alternate symbols: º → °, ° → °
- Accented characters: café → cafe
- Smart quotes: " " → "
"""

from __future__ import annotations

import re
import unicodedata


def normalize_unicode(text: str) -> str:
    """Normalize unicode text for robust parsing."""
    # NFKD normalization: decompose characters to base + combining marks
    text = unicodedata.normalize("NFKD", text)

    # Remove combining marks (accents, diacritics)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")

    # Convert emoji digits to ASCII digits
    emoji_to_digit = {
        "0️⃣": "0",
        "1️⃣": "1",
        "2️⃣": "2",
        "3️⃣": "3",
        "4️⃣": "4",
        "5️⃣": "5",
        "6️⃣": "6",
        "7️⃣": "7",
        "8️⃣": "8",
        "9️⃣": "9",
    }
    for emoji, digit in emoji_to_digit.items():
        text = text.replace(emoji, digit)

    # Normalize degree symbols (multiple variants exist)
    # Use regex to catch various Unicode degree symbols
    text = re.sub(r"[°º˚∘]", "°", text)

    # Smart quotes to straight quotes
    text = re.sub(r"[""″]", '"', text)
    text = re.sub(r"[''´]", "'", text)

    # Remove zero-width characters
    text = re.sub(r"[​‌‍‎‏]", "", text)

    return text


def extract_temperature_robust(text: str) -> float | None:
    """Extract temperature with unicode normalization."""
    normalized = normalize_unicode(text)

    # Look for number followed by ° or F or similar
    patterns = [
        r"(\d{2,3}(?:\.\d+)?)\s*°?\s*[Ff]\b",  # 102°F or 102 F
        r"(\d{2,3}(?:\.\d+)?)\s*(?:degrees?\s+)?[Ff](?:ahrenheit)?\b",  # 102 degrees F
        r"(?:temp|temperature)[^\d]{0,12}(\d{2,3}(?:\.\d+)?)",  # temperature: 102
    ]

    for pattern in patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except (ValueError, IndexError):
                continue

    return None


def extract_age_robust(text: str) -> tuple[float | None, str]:
    """Extract age with unicode normalization. Returns (value, unit)."""
    normalized = normalize_unicode(text)

    # Years
    years_match = re.search(r"(\d{1,2})\s*-?\s*years?\s*-?\s*old\b", normalized, re.IGNORECASE)
    if years_match:
        try:
            return float(years_match.group(1)), "years"
        except ValueError:
            pass

    # Months
    months_match = re.search(r"(\d{1,2})\s*-?\s*months?\b", normalized, re.IGNORECASE)
    if months_match:
        try:
            return float(months_match.group(1)), "months"
        except ValueError:
            pass

    return None, None


def test_unicode_normalization():
    """Test unicode normalization."""
    test_cases = [
        ("Temperature: 1️⃣0️⃣2️⃣°F", "Temperature: 102°F"),
        ("102ºF (degree symbol variant)", "102°F (degree symbol variant)"),
        ("Café fever", "Cafe fever"),
    ]

    for input_text, expected_normalized in test_cases:
        normalized = normalize_unicode(input_text)
        print(f"Input: {input_text}")
        print(f"  → {normalized}")
        print()
