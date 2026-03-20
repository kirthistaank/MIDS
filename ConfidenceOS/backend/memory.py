"""
memory.py — session memory management.
Stores per-session context (name, role, mode, history) in a simple dict.
In production you'd swap this for Redis or a database.
"""

from datetime import datetime
from langgraph.checkpoint.memory import MemorySaver

# ── LangGraph checkpointer (persists message history across turns) ────────────
checkpointer = MemorySaver()

# ── Session store (in-memory, per session_id) ─────────────────────────────────
_sessions: dict[str, dict] = {}


def get_session(session_id: str) -> dict:
    """Get or create a session."""
    if session_id not in _sessions:
        _sessions[session_id] = {
            "session_id":    session_id,
            "created_at":    datetime.now().isoformat(),
            "mode":          "chat",
            "user_name":     None,
            "target_role":   None,
            "confidence":    5,        # 1-10 confidence score, starts neutral
            "questions_asked": 0,
            "topics_covered":  [],
        }
    return _sessions[session_id]


def update_session(session_id: str, updates: dict) -> dict:
    """Merge updates into an existing session."""
    session = get_session(session_id)
    session.update(updates)
    return session


def set_mode(session_id: str, mode: str) -> dict:
    """Switch the agent mode for a session."""
    return update_session(session_id, {"mode": mode})


def get_mode(session_id: str) -> str:
    """Get the current mode for a session."""
    return get_session(session_id)["mode"]


def increment_questions(session_id: str) -> int:
    """Track how many mock interview questions have been asked."""
    session = get_session(session_id)
    session["questions_asked"] += 1
    return session["questions_asked"]


def add_topic(session_id: str, topic: str):
    """Track topics covered in the session."""
    session = get_session(session_id)
    if topic not in session["topics_covered"]:
        session["topics_covered"].append(topic)


def update_confidence(session_id: str, score: int):
    """Update the user's confidence score (1-10)."""
    score = max(1, min(10, score))   # clamp to 1-10
    update_session(session_id, {"confidence": score})


def get_session_summary(session_id: str) -> str:
    """Build a context string injected into the system prompt."""
    s = get_session(session_id)
    parts = []
    if s["user_name"]:
        parts.append(f"User's name: {s['user_name']}")
    if s["target_role"]:
        parts.append(f"Target role: {s['target_role']}")
    if s["topics_covered"]:
        parts.append(f"Topics covered so far: {', '.join(s['topics_covered'])}")
    if s["questions_asked"] > 0:
        parts.append(f"Mock interview questions asked: {s['questions_asked']}")
    parts.append(f"Current confidence score: {s['confidence']}/10")

    if not parts:
        return ""
    return "\n[SESSION CONTEXT]\n" + "\n".join(parts) + "\n"
