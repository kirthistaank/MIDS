"""
emotion.py — detects emotional signals in user messages.
Keeps emotion logic isolated so it can be improved independently.
Used by the agent to decide whether to pivot to supportive mode.
"""

# Keywords that signal anxiety, self-doubt, or distress
NEGATIVE_SIGNALS = [
    "i'm terrible", "i am terrible", "i always fail", "i always mess up",
    "i can't do this", "i cannot do this", "i'm not good enough",
    "i am not good enough", "i'm so bad at", "i am so bad at",
    "nobody will hire me", "i'll never get", "i will never get",
    "i'm nervous", "i am nervous", "i'm scared", "i am scared",
    "i'm anxious", "i am anxious", "i hate interviews", "so stressed",
    "i'm a failure", "i am a failure", "i give up", "what's the point",
    "i don't know why i bother", "i suck at", "i'm hopeless",
    "i am hopeless", "i'm worthless", "i feel like a fraud",
    "impostor syndrome", "imposter syndrome", "not qualified",
    "they will think i'm", "they will think i am",
]

POSITIVE_SIGNALS = [
    "excited", "confident", "ready", "i got this", "feeling good",
    "i did well", "i got the job", "they offered", "great feedback",
]


def detect_emotion(message: str) -> dict:
    """
    Analyse a message for emotional signals.
    Returns a dict with:
      - has_negative (bool)
      - has_positive (bool)
      - signals (list of matched keywords)
      - tone (str: 'distressed' | 'positive' | 'neutral')
    """
    lower = message.lower()

    matched_negative = [s for s in NEGATIVE_SIGNALS if s in lower]
    matched_positive = [s for s in POSITIVE_SIGNALS if s in lower]

    has_negative = len(matched_negative) > 0
    has_positive = len(matched_positive) > 0

    if has_negative:
        tone = "distressed"
    elif has_positive:
        tone = "positive"
    else:
        tone = "neutral"

    return {
        "has_negative": has_negative,
        "has_positive": has_positive,
        "signals": matched_negative + matched_positive,
        "tone": tone,
    }


def build_emotion_prefix(emotion: dict) -> str:
    """
    Returns an instruction prefix injected into the system prompt
    when strong emotion is detected — guides the LLM response tone.
    """
    if emotion["tone"] == "distressed":
        return (
            "\n[EMOTION DETECTED: The user is expressing self-doubt or anxiety. "
            "Acknowledge their feeling warmly FIRST before any advice. "
            "Be extra gentle and encouraging. "
            "If relevant, name the cognitive distortion you notice.]\n"
        )
    elif emotion["tone"] == "positive":
        return (
            "\n[EMOTION DETECTED: The user is feeling positive. "
            "Celebrate this with them briefly before continuing.]\n"
        )
    return ""
