from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


# ----------------------------
# Patterns (interpretable rules)
# ----------------------------

FACILITATION_PATTERNS: List[Tuple[str, str, int]] = [
    ("agenda", r"\bagenda\b", 3),
    ("kickoff", r"\b(let'?s|lets)\s+(start|begin|kick\s*off)\b", 3),
    ("time", r"\bwe(?:'re| are)\s+(running\s+out\s+of\s+time|short\s+on\s+time)\b", 2),
    ("move_on", r"\b(move(?:\s+)?on|next\s+(topic|item|point))\b", 3),
    ("wrap_up", r"\b(wrap\s*up|to\s+wrap\s+up|in\s+summary|to\s+summarize)\b", 3),
    ("action_items", r"\b(action\s+items?|next\s+steps?)\b", 3),
    ("assign", r"\b(you|we)\s+(will|can)\s+(take|own|handle)\b", 1),
    ("call_on", r"\b(any\s+thoughts|what\s+do\s+you\s+think|can\s+you\s+share|do\s+you\s+have)\b", 2),
    ("check_in", r"\bany\s+questions\??\b|\bdoes\s+that\s+make\s+sense\??\b", 2),
]

QUESTION_PAT = re.compile(r"\?$|\b(what|why|how|when|where|who|which)\b", flags=re.IGNORECASE)
CLARIFICATION_REQUEST_PATTERNS: List[Tuple[str, str, int]] = [
    ("clarify", r"\bclarif(y|ied|ying)\b", 3),
    ("dont_understand", r"\b(i\s+don'?t\s+understand|i\s+do\s+not\s+understand)\b", 4),
    ("what_do_you_mean", r"\bwhat\s+do\s+you\s+mean\b", 4),
    ("repeat", r"\b(can\s+you|could\s+you)\s+(repeat|say\s+that\s+again)\b", 3),
    ("explain", r"\b(can\s+you|could\s+you)\s+(explain|elaborate)\b", 3),
    ("sorry_pardon", r"\b(sorry|pardon)\b", 1),
]

CLARIFICATION_PROVIDE_PATTERNS: List[Tuple[str, str, int]] = [
    ("let_me_clarify", r"\b(let\s+me\s+clarify|to\s+clarify)\b", 2),
    ("what_i_mean", r"\b(what\s+i\s+mean\s+is)\b", 2),
    ("in_other_words", r"\b(in\s+other\s+words)\b", 2),
]


# ----------------------------
# Utilities
# ----------------------------

def _safe_text(x: Any) -> str:
    if not isinstance(x, str):
        return ""
    return " ".join(x.split())


def _normalized_entropy(counts: Sequence[float]) -> float:
    """
    Returns entropy normalized to [0,1] where 1 = perfectly uniform, 0 = all mass on one category.
    """
    x = np.asarray(counts, dtype=float)
    x = x[x > 0]
    if x.size <= 1:
        return 0.0
    p = x / x.sum()
    h = float(-(p * np.log(p)).sum())
    return float(h / math.log(len(p)))


def _clip01(x: float) -> float:
    if np.isnan(x):
        return float("nan")
    return float(max(0.0, min(1.0, x)))


def _sigmoid01(x: float) -> float:
    # mild sigmoid to map arbitrary values to (0,1)
    return float(1.0 / (1.0 + math.exp(-x)))


def _score_from_patterns(text_series: pd.Series, patterns: List[Tuple[str, str, int]]) -> pd.DataFrame:
    cols: Dict[str, pd.Series] = {}
    s = text_series.fillna("").astype(str)
    for name, pat, weight in patterns:
        rx = re.compile(pat, flags=re.IGNORECASE)
        # `str.contains` warns if regex has capturing groups; we don't need groups, so disable.
        cols[name] = s.str.contains(rx, regex=True, na=False).astype(int) * int(weight)
    return pd.DataFrame(cols)


def _is_question(text: str) -> bool:
    t = _safe_text(text)
    if not t:
        return False
    if t.strip().endswith("?"):
        return True
    # lightweight heuristic: interrogatives + short-ish utterances
    return bool(QUESTION_PAT.search(t)) and (len(t.split()) <= 30)


def _try_sentiment_fn():
    """
    Returns a function f(text)->float in [-1,1].
    Prefers VADER if available, else TextBlob, else a tiny lexicon fallback.
    """
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # type: ignore

        analyzer = SentimentIntensityAnalyzer()

        def _vader(text: str) -> float:
            return float(analyzer.polarity_scores(_safe_text(text)).get("compound", 0.0))

        return _vader
    except Exception:
        pass

    try:
        from textblob import TextBlob  # type: ignore

        def _tb(text: str) -> float:
            return float(TextBlob(_safe_text(text)).sentiment.polarity)

        return _tb
    except Exception:
        pass

    # fallback: tiny lexicon (kept small + interpretable)
    POS = {
        "good",
        "great",
        "excellent",
        "love",
        "like",
        "thanks",
        "thank",
        "agree",
        "ok",
        "okay",
        "nice",
        "cool",
        "perfect",
        "works",
        "clear",
    }
    NEG = {
        "bad",
        "terrible",
        "awful",
        "hate",
        "dislike",
        "problem",
        "issue",
        "concern",
        "confused",
        "unclear",
        "disagree",
        "wrong",
        "fail",
        "broken",
        "angry",
        "frustrated",
    }

    def _lex(text: str) -> float:
        toks = re.findall(r"[a-z]+", _safe_text(text).lower())
        if not toks:
            return 0.0
        p = sum(1 for t in toks if t in POS)
        n = sum(1 for t in toks if t in NEG)
        # scale to [-1,1] with diminishing returns
        return float((p - n) / max(3.0, p + n + 3.0))

    return _lex


# ----------------------------
# Lead inference
# ----------------------------

@dataclass(frozen=True)
class LeadInference:
    lead_speaker: Optional[str]
    confidence: float
    details: Dict[str, Any]


def infer_meeting_lead(
    meeting_turns: pd.DataFrame,
    *,
    speaker_col: str = "speaker",
    text_col: str = "content_clean",
    turn_idx_col: str = "turn_idx",
) -> LeadInference:
    """
    Heuristic lead inference:
    - participates early
    - has many turns/words
    - uses facilitation language (agenda/next steps/wrap-up/calling on others)
    - asks coordination questions
    """
    if meeting_turns.empty or speaker_col not in meeting_turns.columns:
        return LeadInference(lead_speaker=None, confidence=0.0, details={"reason": "empty_meeting"})

    df = meeting_turns.copy()
    df["_speaker"] = df[speaker_col].astype(str)
    df["_text"] = df.get(text_col, df.get("content", "")).fillna("").astype(str)
    if turn_idx_col in df.columns:
        df["_turn_idx"] = pd.to_numeric(df[turn_idx_col], errors="coerce").fillna(0).astype(int)
    else:
        df["_turn_idx"] = np.arange(len(df), dtype=int)

    n_turns = len(df)
    early_cutoff = max(1, int(round(n_turns * 0.15)))
    early = df[df["_turn_idx"] < early_cutoff]

    facil_scores = _score_from_patterns(df["_text"], FACILITATION_PATTERNS).sum(axis=1)
    df["_facil"] = facil_scores.astype(float)
    df["_is_question"] = df["_text"].map(_is_question).astype(int)
    df["_n_words"] = df["_text"].map(lambda x: len(_safe_text(x).split())).astype(int)

    agg = (
        df.groupby("_speaker", dropna=False)
        .agg(
            n_turns=("_speaker", "size"),
            n_words=("_n_words", "sum"),
            facil=("__facil", "sum") if "__facil" in df.columns else ("_facil", "sum"),
            n_questions=("_is_question", "sum"),
            first_turn=("_turn_idx", "min"),
        )
        .reset_index()
    )
    # early participation share
    early_share = early.groupby("_speaker").size() / max(1, len(early))
    agg["early_share"] = agg["_speaker"].map(early_share).fillna(0.0)

    # normalize features into comparable ranges
    def _z(x: pd.Series) -> pd.Series:
        if x.nunique(dropna=False) <= 1:
            return x * 0.0
        return (x - x.mean()) / (x.std(ddof=0) + 1e-9)

    # higher is more "lead-like"
    agg["lead_score"] = (
        0.35 * _z(agg["n_turns"])
        + 0.25 * _z(agg["n_words"])
        + 0.25 * _z(agg["facil"])
        + 0.15 * _z(agg["early_share"])
        + 0.10 * _z(agg["n_questions"])
        - 0.10 * _z(agg["first_turn"])
    )

    agg = agg.sort_values("lead_score", ascending=False, kind="stable")
    lead = str(agg.iloc[0]["_speaker"]) if not agg.empty else None

    # confidence: margin between top-1 and top-2, squashed to [0,1]
    if len(agg) >= 2:
        margin = float(agg.iloc[0]["lead_score"] - agg.iloc[1]["lead_score"])
    else:
        margin = 1.0
    confidence = _clip01(_sigmoid01(2.0 * margin))

    return LeadInference(
        lead_speaker=lead,
        confidence=confidence,
        details={
            "n_turns": int(n_turns),
            "speaker_table": agg,
            "early_cutoff_turn": int(early_cutoff),
        },
    )


# ----------------------------
# Metric computation
# ----------------------------

def _tfidf_matrix(texts: Sequence[str]):
    from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore

    vec = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        min_df=1,
        max_df=0.95,
    )
    X = vec.fit_transform(list(texts))
    return vec, X


def semantic_meaning_score(
    meeting_turns: pd.DataFrame,
    *,
    text_col: str = "content_clean",
    window: int = 25,
) -> Dict[str, Any]:
    """
    Semantic meaning (coherence): average cosine similarity of each utterance to the centroid
    of previous utterances (last `window` turns).
    """
    texts = meeting_turns.get(text_col, meeting_turns.get("content", "")).fillna("").astype(str).tolist()
    texts = [_safe_text(t) for t in texts]
    if len(texts) <= 2:
        return {"semantic_meaning_raw": float("nan"), "semantic_meaning_score": float("nan")}

    _, X = _tfidf_matrix(texts)
    from sklearn.metrics.pairwise import cosine_similarity  # type: ignore

    sims: List[float] = []
    for i in range(1, X.shape[0]):
        j0 = max(0, i - int(window))
        # NOTE: sparse.mean(axis=0) returns a numpy.matrix in some numpy/sklearn combos,
        # which cosine_similarity (and numpy) may reject. Convert to ndarray.
        prev_centroid = np.asarray(X[j0:i].mean(axis=0))
        s = float(cosine_similarity(X[i], prev_centroid)[0, 0])
        sims.append(s)

    raw = float(np.nanmean(sims)) if sims else float("nan")
    # map raw similarity (typically ~0.05-0.35 for TF-IDF) into [0,1]
    score = _clip01((raw - 0.05) / (0.30 - 0.05))
    return {"semantic_meaning_raw": raw, "semantic_meaning_score": score}


def qa_completion_score(
    meeting_turns: pd.DataFrame,
    *,
    speaker_col: str = "speaker",
    text_col: str = "content_clean",
    lead_speaker: Optional[str] = None,
    window: int = 6,
    similarity_threshold: float = 0.15,
) -> Dict[str, Any]:
    """
    Q&A completion (turn-level heuristic):
    - detect question turns
    - question is "answered" if any of the next `window` turns is a non-question by someone else
      with cosine similarity >= threshold to the question (TF-IDF).

    Also reports `lead_answer_rate`: fraction of others' questions answered by the inferred lead.
    """
    # IMPORTANT: reset index so TF-IDF row indices align with df positions.
    # Grouped meeting slices often keep original indices, which break sparse indexing.
    df = meeting_turns.copy().reset_index(drop=True)
    df["_speaker"] = df.get(speaker_col, "").astype(str)
    df["_text"] = df.get(text_col, df.get("content", "")).fillna("").astype(str).map(_safe_text)
    df["_is_q"] = df["_text"].map(_is_question)

    texts = df["_text"].tolist()
    if len(texts) <= 2:
        return {
            "n_questions": 0,
            "n_answered": 0,
            "qa_completion_raw": float("nan"),
            "qa_completion_score": float("nan"),
            "lead_answer_rate_raw": float("nan"),
            "lead_answer_rate_score": float("nan"),
        }

    _, X = _tfidf_matrix(texts)
    from sklearn.metrics.pairwise import cosine_similarity  # type: ignore

    q_idxs = [i for i, isq in enumerate(df["_is_q"].tolist()) if bool(isq)]
    if not q_idxs:
        # if no questions, treat completion as "not applicable"; score neutral-high
        return {
            "n_questions": 0,
            "n_answered": 0,
            "qa_completion_raw": float("nan"),
            "qa_completion_score": 1.0,
            "lead_answer_rate_raw": float("nan"),
            "lead_answer_rate_score": 1.0 if lead_speaker else float("nan"),
        }

    answered = 0
    lead_answered = 0
    lead_eligible = 0

    for i in q_idxs:
        asker = df.iloc[i]["_speaker"]
        j1 = min(len(df), i + 1 + int(window))
        cand = df.iloc[i + 1 : j1]
        cand = cand[~cand["_is_q"]]
        cand_other = cand[cand["_speaker"] != asker]

        if not cand_other.empty:
            sims = cosine_similarity(X[i], X[cand_other.index]).ravel()
            if float(np.max(sims)) >= float(similarity_threshold):
                answered += 1

        if lead_speaker is not None and str(lead_speaker) != "nan":
            if str(asker) != str(lead_speaker):
                lead_eligible += 1
                cand_lead = cand_other[cand_other["_speaker"] == str(lead_speaker)]
                if not cand_lead.empty:
                    sims2 = cosine_similarity(X[i], X[cand_lead.index]).ravel()
                    if float(np.max(sims2)) >= float(similarity_threshold):
                        lead_answered += 1

    raw = float(answered / max(1, len(q_idxs)))
    score = _clip01(raw)  # already in [0,1]

    lead_raw = float(lead_answered / max(1, lead_eligible)) if lead_eligible > 0 else float("nan")
    lead_score = _clip01(lead_raw) if not np.isnan(lead_raw) else (float("nan"))

    return {
        "n_questions": int(len(q_idxs)),
        "n_answered": int(answered),
        "qa_completion_raw": raw,
        "qa_completion_score": score,
        "lead_answer_rate_raw": lead_raw,
        "lead_answer_rate_score": lead_score,
        "lead_answer_eligible_questions": int(lead_eligible),
        "lead_answered_questions": int(lead_answered),
    }


def clarification_frequency_score(
    meeting_turns: pd.DataFrame,
    *,
    text_col: str = "content_clean",
) -> Dict[str, Any]:
    """
    Clarification frequency: how often participants request clarification / express confusion.
    Lower frequency => higher score.
    """
    texts = meeting_turns.get(text_col, meeting_turns.get("content", "")).fillna("").astype(str)
    req = _score_from_patterns(texts, CLARIFICATION_REQUEST_PATTERNS).sum(axis=1) > 0
    prov = _score_from_patterns(texts, CLARIFICATION_PROVIDE_PATTERNS).sum(axis=1) > 0
    n_turns = int(len(texts))
    n_req = int(req.sum())
    n_prov = int(prov.sum())

    # requests per 100 turns; map 0..8 per 100 turns into 1..0
    req_rate = (100.0 * n_req / max(1, n_turns))
    score = _clip01(1.0 - (req_rate / 8.0))

    return {
        "clarification_requests": n_req,
        "clarification_provides": n_prov,
        "clarification_request_rate_per_100_turns": float(req_rate),
        "clarification_frequency_score": score,
    }


def sentiment_stability_score(
    meeting_turns: pd.DataFrame,
    *,
    text_col: str = "content_clean",
) -> Dict[str, Any]:
    """
    Sentiment stability: compare beginning vs end sentiment and compute a simple slope.
    Stability is higher when absolute drift is small.
    """
    sentiment = _try_sentiment_fn()
    texts = meeting_turns.get(text_col, meeting_turns.get("content", "")).fillna("").astype(str).map(_safe_text)
    vals = np.array([sentiment(t) for t in texts], dtype=float)
    n = len(vals)
    if n < 4:
        return {
            "sentiment_begin_mean": float("nan"),
            "sentiment_end_mean": float("nan"),
            "sentiment_delta": float("nan"),
            "sentiment_slope": float("nan"),
            "sentiment_stability_score": float("nan"),
        }

    k = max(1, int(round(n * 0.2)))
    begin = float(np.nanmean(vals[:k]))
    end = float(np.nanmean(vals[-k:]))
    delta = float(end - begin)

    # simple regression slope over normalized time in [0,1]
    x = np.linspace(0.0, 1.0, n)
    slope = float(np.polyfit(x, vals, deg=1)[0])

    # map abs(slope) of 0..0.6 into 1..0
    score = _clip01(1.0 - (abs(slope) / 0.6))

    return {
        "sentiment_begin_mean": begin,
        "sentiment_end_mean": end,
        "sentiment_delta": delta,
        "sentiment_slope": slope,
        "sentiment_stability_score": score,
    }


def conversational_balance_score(
    meeting_turns: pd.DataFrame,
    *,
    speaker_col: str = "speaker",
    text_col: str = "content_clean",
    lead_speaker: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Conversational balance: distribution of participation across speakers.
    Uses normalized entropy over word counts (and reports lead share).
    """
    df = meeting_turns.copy()
    df["_speaker"] = df.get(speaker_col, "").astype(str)
    df["_text"] = df.get(text_col, df.get("content", "")).fillna("").astype(str).map(_safe_text)
    df["_n_words"] = df["_text"].map(lambda x: len(x.split())).astype(int)
    words = df.groupby("_speaker")["_n_words"].sum()
    turns = df.groupby("_speaker").size()

    word_entropy = _normalized_entropy(words.values.astype(float))
    turn_entropy = _normalized_entropy(turns.values.astype(float))

    lead_share_words = float("nan")
    lead_share_turns = float("nan")
    if lead_speaker is not None:
        total_w = float(words.sum()) or 1.0
        total_t = float(turns.sum()) or 1.0
        lead_share_words = float(words.get(str(lead_speaker), 0.0) / total_w)
        lead_share_turns = float(turns.get(str(lead_speaker), 0.0) / total_t)

    # Score: average of word/turn entropy.
    score = _clip01(0.5 * word_entropy + 0.5 * turn_entropy)
    return {
        "n_speakers": int(len(words)),
        "balance_word_entropy": float(word_entropy),
        "balance_turn_entropy": float(turn_entropy),
        "lead_word_share": float(lead_share_words),
        "lead_turn_share": float(lead_share_turns),
        "conversational_balance_score": score,
    }


def conversation_convergence_score(
    meeting_turns: pd.DataFrame,
    *,
    topics_df: Optional[pd.DataFrame] = None,
    queries_df: Optional[pd.DataFrame] = None,
    dataset: Optional[str] = None,
    meeting_id: Optional[str] = None,
    text_col: str = "content_clean",
) -> Dict[str, Any]:
    """
    Conversation convergence: did the meeting converge toward its intended goals?

    Since "goal" is not explicitly present per turn, we approximate it using:
    - QMSum general query answer (meeting-level summary/goal proxy)
    - topic names for that meeting

    We compute:
    - alignment_begin: avg similarity of first 20% turns to goal text
    - alignment_end:   avg similarity of last 20% turns to goal text
    - alignment_delta: end - begin
    - query_span_coverage: fraction of turns that appear in any annotated query span (if spans exist)
    """
    texts = meeting_turns.get(text_col, meeting_turns.get("content", "")).fillna("").astype(str).map(_safe_text).tolist()
    n = len(texts)
    if n < 4:
        return {
            "goal_text_len": 0,
            "alignment_begin": float("nan"),
            "alignment_end": float("nan"),
            "alignment_delta": float("nan"),
            "query_span_coverage": float("nan"),
            "conversation_convergence_score": float("nan"),
        }

    goal_parts: List[str] = []
    if queries_df is not None and meeting_id is not None and "meeting_id" in queries_df.columns:
        q = queries_df
        if dataset is not None and "dataset" in q.columns:
            q = q[q["dataset"] == dataset]
        q = q[q["meeting_id"] == meeting_id]
        # use the general "Summarize the whole meeting" answer if present; else all general answers concatenated
        qg = q[q.get("query_type", "") == "general"]
        if "query" in qg.columns:
            qg2 = qg[qg["query"].fillna("").astype(str).str.contains("Summarize", case=False, na=False)]
        else:
            qg2 = qg
        ans = (
            qg2.get("answer", pd.Series(dtype=str))
            .dropna()
            .astype(str)
            .map(_safe_text)
            .tolist()
        )
        if not ans:
            ans = (
                qg.get("answer", pd.Series(dtype=str))
                .dropna()
                .astype(str)
                .map(_safe_text)
                .tolist()
            )
        if ans:
            goal_parts.append(" ".join(ans[:3]))

    if topics_df is not None and meeting_id is not None and "meeting_id" in topics_df.columns and "topic" in topics_df.columns:
        tp = topics_df
        if dataset is not None and "dataset" in tp.columns:
            tp = tp[tp["dataset"] == dataset]
        tp = tp[tp["meeting_id"] == meeting_id]
        topics = tp["topic"].dropna().astype(str).map(_safe_text).tolist()
        if topics:
            goal_parts.append(" ".join(sorted(set([t for t in topics if t]))))

    goal_text = _safe_text(" ".join(goal_parts))
    if not goal_text:
        # no usable goal proxy; treat convergence as unknown
        return {
            "goal_text_len": 0,
            "alignment_begin": float("nan"),
            "alignment_end": float("nan"),
            "alignment_delta": float("nan"),
            "query_span_coverage": float("nan"),
            "conversation_convergence_score": float("nan"),
        }

    # TF-IDF over turns + goal text
    all_docs = list(texts) + [goal_text]
    _, X = _tfidf_matrix(all_docs)
    from sklearn.metrics.pairwise import cosine_similarity  # type: ignore

    goal_vec = X[-1]
    turn_vecs = X[:-1]
    sims = cosine_similarity(turn_vecs, goal_vec).ravel()
    k = max(1, int(round(n * 0.2)))
    begin = float(np.nanmean(sims[:k]))
    end = float(np.nanmean(sims[-k:]))
    delta = float(end - begin)

    # annotated query span coverage (if available)
    coverage = float("nan")
    if queries_df is not None and meeting_id is not None and "meeting_id" in queries_df.columns:
        q = queries_df
        if dataset is not None and "dataset" in q.columns:
            q = q[q["dataset"] == dataset]
        q = q[q["meeting_id"] == meeting_id]
        if "span_start_turn" in q.columns and "span_end_turn" in q.columns:
            covered: set[int] = set()
            for _, r in q.iterrows():
                s = r.get("span_start_turn")
                e = r.get("span_end_turn")
                if pd.isna(s) or pd.isna(e):
                    continue
                try:
                    s2 = int(s)
                    e2 = int(e)
                except Exception:
                    continue
                for t in range(max(0, s2), min(n - 1, e2) + 1):
                    covered.add(t)
            coverage = float(len(covered) / max(1, n))

    # Convert to an interpretable score:
    # - end alignment matters most
    # - positive delta helps
    # - coverage (if present) helps
    score = 0.0
    score += 2.5 * (end - 0.05) / (0.35 - 0.05)  # scale typical TF-IDF sim range
    score += 1.5 * (delta / 0.15)
    if not np.isnan(coverage):
        score += 0.75 * (coverage - 0.2) / (0.8 - 0.2)
    score01 = _clip01(_sigmoid01(score) * 1.05)  # mild stretch

    return {
        "goal_text_len": int(len(goal_text)),
        "alignment_begin": begin,
        "alignment_end": end,
        "alignment_delta": delta,
        "query_span_coverage": coverage,
        "conversation_convergence_score": score01,
    }


# ----------------------------
# End-to-end scoring
# ----------------------------

def score_qmsum_meeting_communication(
    transcripts_df: pd.DataFrame,
    *,
    topics_df: Optional[pd.DataFrame] = None,
    queries_df: Optional[pd.DataFrame] = None,
    dataset_col: str = "dataset",
    meeting_id_col: str = "meeting_id",
    speaker_col: str = "speaker",
    turn_idx_col: str = "turn_idx",
    text_col: str = "content_clean",
    weights: Optional[Dict[str, float]] = None,
) -> pd.DataFrame:
    """
    Scores each meeting across 6 traits and infers the meeting lead.

    Returns a meeting-level DataFrame with:
    - inferred lead (`lead_speaker`, `lead_confidence`)
    - trait score columns (0..1)
    - raw diagnostic columns (counts / deltas)
    - final `effective_communication` boolean.
    """
    if transcripts_df.empty:
        return pd.DataFrame()

    w = {
        "semantic_meaning": 1.0,
        "qa_completion": 1.0,
        "clarification_frequency": 1.0,
        "sentiment_stability": 1.0,
        "conversational_balance": 1.0,
        "conversation_convergence": 1.0,
    }
    if weights:
        w.update({k: float(v) for k, v in weights.items()})

    group_cols = [meeting_id_col]
    if dataset_col in transcripts_df.columns:
        group_cols = [dataset_col, meeting_id_col]

    out_rows: List[Dict[str, Any]] = []
    t = transcripts_df.sort_values(group_cols + [turn_idx_col] if turn_idx_col in transcripts_df.columns else group_cols, kind="stable")

    for keys, mtg in t.groupby(group_cols, dropna=False):
        if isinstance(keys, tuple):
            dataset = keys[0] if len(keys) == 2 else None
            meeting_id = keys[-1]
        else:
            dataset = None
            meeting_id = keys

        lead_inf = infer_meeting_lead(mtg, speaker_col=speaker_col, text_col=text_col, turn_idx_col=turn_idx_col)
        lead = lead_inf.lead_speaker

        sem = semantic_meaning_score(mtg, text_col=text_col)
        qa = qa_completion_score(mtg, speaker_col=speaker_col, text_col=text_col, lead_speaker=lead)
        clar = clarification_frequency_score(mtg, text_col=text_col)
        sent = sentiment_stability_score(mtg, text_col=text_col)
        bal = conversational_balance_score(mtg, speaker_col=speaker_col, text_col=text_col, lead_speaker=lead)
        conv = conversation_convergence_score(
            mtg,
            topics_df=topics_df,
            queries_df=queries_df,
            dataset=dataset,
            meeting_id=str(meeting_id),
            text_col=text_col,
        )

        # overall score: weighted mean of the 6 normalized scores (skip NaNs)
        trait_scores = {
            "semantic_meaning": sem.get("semantic_meaning_score"),
            "qa_completion": qa.get("qa_completion_score"),
            "clarification_frequency": clar.get("clarification_frequency_score"),
            "sentiment_stability": sent.get("sentiment_stability_score"),
            "conversational_balance": bal.get("conversational_balance_score"),
            "conversation_convergence": conv.get("conversation_convergence_score"),
        }

        num = 0.0
        den = 0.0
        for k, v in trait_scores.items():
            if v is None or (isinstance(v, float) and np.isnan(v)):
                continue
            num += float(w.get(k, 1.0)) * float(v)
            den += float(w.get(k, 1.0))
        overall = float(num / den) if den > 0 else float("nan")

        # final determination (interpretable threshold)
        effective = bool(overall >= 0.60) if not np.isnan(overall) else False

        row: Dict[str, Any] = {
            dataset_col: dataset,
            meeting_id_col: meeting_id,
            "n_turns": int(len(mtg)),
            "lead_speaker": lead,
            "lead_confidence": float(lead_inf.confidence),
            "effective_communication_score": overall,
            "effective_communication": effective,
            # trait scores
            "semantic_meaning_score": trait_scores["semantic_meaning"],
            "qa_completion_score": trait_scores["qa_completion"],
            "clarification_frequency_score": trait_scores["clarification_frequency"],
            "sentiment_stability_score": trait_scores["sentiment_stability"],
            "conversational_balance_score": trait_scores["conversational_balance"],
            "conversation_convergence_score": trait_scores["conversation_convergence"],
        }

        # raw diagnostic fields (useful for auditing)
        row.update({k: v for k, v in sem.items() if k not in row})
        row.update({k: v for k, v in qa.items() if k not in row})
        row.update({k: v for k, v in clar.items() if k not in row})
        row.update({k: v for k, v in sent.items() if k not in row})
        row.update({k: v for k, v in bal.items() if k not in row})
        row.update({k: v for k, v in conv.items() if k not in row})

        out_rows.append(row)

    out = pd.DataFrame(out_rows)
    if dataset_col in out.columns and meeting_id_col in out.columns:
        out = out.sort_values([dataset_col, meeting_id_col], kind="stable").reset_index(drop=True)
    else:
        out = out.sort_values([meeting_id_col], kind="stable").reset_index(drop=True)
    return out

