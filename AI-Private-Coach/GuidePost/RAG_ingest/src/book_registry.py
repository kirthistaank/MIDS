"""
src/book_registry.py

Single source of truth for all 7 framework books.
Imported by chunking.py, pinecone_store.py, neo4j_store.py, and main.py.
Add a new book here — nothing else needs to change.
"""
from typing import Dict, Any

# Key = exact PDF stem (pdf_path.stem), value = metadata dict
BOOK_REGISTRY: Dict[str, Dict[str, Any]] = {
    "Motivational Interviewing - Helping People Change and Grow": {
        "short_name": "MI",
        "framework":  "Motivational Interviewing",
        "themes": [
            "change readiness", "ambivalence", "resistance", "guiding style",
            "empathy", "autonomy", "reflective listening", "change talk",
            "partnership", "acceptance", "compassion", "empowerment",
        ],
        "best_for": [
            "manager relationship", "change resistance",
            "communication style", "motivation",
        ],
    },
    "Nonviolent Communication - A Language of Life": {
        "short_name": "NVC",
        "framework":  "Nonviolent Communication",
        "themes": [
            "observations", "feelings", "needs", "requests", "empathy",
            "jackal language", "giraffe language", "compassionate communication",
            "self-empathy", "expressing anger", "conflict resolution",
        ],
        "best_for": [
            "conflict", "communication style",
            "expressing needs", "arguing", "feedback",
        ],
    },
    "Cognitive Behavior Therapy - Basics and Beyond": {
        "short_name": "CBT",
        "framework":  "Cognitive Behavior Therapy",
        "themes": [
            "cognitive distortions", "automatic thoughts", "reframing",
            "schemas", "catastrophising", "all-or-nothing thinking",
            "mind reading", "should statements", "behavioural activation",
            "thought records",
        ],
        "best_for": [
            "self-limiting beliefs", "anxiety at work",
            "negative self-talk", "conflict", "perfectionism",
        ],
    },
    "A Guide to Rational Living": {
        "short_name": "REBT",
        "framework":  "Rational Emotive Behavior Therapy",
        "themes": [
            "irrational beliefs", "must statements", "self-defeating thoughts",
            "awfulising", "low frustration tolerance", "disputing beliefs",
            "unconditional self-acceptance", "rational beliefs",
        ],
        "best_for": [
            "perfectionism", "people pleasing",
            "arguing", "frustration tolerance", "self-worth",
        ],
    },
    "Difficult Conversations How to Discuss What Matters Most": {
        "short_name": "DC",
        "framework":  "Difficult Conversations",
        "themes": [
            "what happened story", "feelings conversation", "identity conversation",
            "contribution", "intent vs impact", "assumption", "curiosity",
            "third story", "learning conversation",
        ],
        "best_for": [
            "promotion conversation", "conflict", "feedback",
            "arguing", "manager relationship",
        ],
    },
    "Getting to Yes": {
        "short_name": "GTY",
        "framework":  "Principled Negotiation",
        "themes": [
            "positions vs interests", "BATNA", "mutual gains",
            "objective criteria", "negotiation", "separate people from problem",
            "inventing options", "principled negotiation",
        ],
        "best_for": [
            "promotion", "salary negotiation",
            "conflict resolution", "disagreement",
        ],
    },
    "Space Framework": {
        "short_name": "SPACE",
        "framework":  "SPACE Framework",
        "themes": [
            "social context", "physiology", "actions", "cognition", "emotion",
            "situational analysis", "self-awareness", "behavioural patterns",
        ],
        "best_for": [
            "understanding reactions", "conflict",
            "communication style", "self-awareness",
        ],
    },
}


def get_book_meta(pdf_stem: str) -> Dict[str, Any]:
    """
    Look up metadata for a PDF by its stem (filename without .pdf).
    Returns a safe default if the book isn't registered — never raises.
    """
    meta = BOOK_REGISTRY.get(pdf_stem)
    if meta is None:
        # Fuzzy match: check if any registry key is contained in the stem
        stem_lower = pdf_stem.lower()
        for key, val in BOOK_REGISTRY.items():
            if key.lower() in stem_lower or stem_lower in key.lower():
                return val
        # Unrecognised book — safe fallback so pipeline never breaks
        return {
            "short_name": pdf_stem[:6].upper(),
            "framework":  pdf_stem,
            "themes":     [],
            "best_for":   [],
        }
    return meta