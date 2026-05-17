from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple, Union

import pandas as pd


JsonDict = Dict[str, Any]
Meeting = Tuple[str, JsonDict]  # (meeting_id, raw_json)


def _safe_int(x: Any) -> Optional[int]:
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def clean_transcript_text(text: str) -> str:
    """
    Lightweight cleanup for common QMSum transcript markers.
    Keeps behavior intentionally simple for EDA (not model training).
    """
    if not isinstance(text, str):
        return ""
    replacements = {
        "{vocalsound}": "",
        "{ vocalsound }": "",
        "{disfmarker}": "",
        "{ disfmarker }": "",
        "{pause}": "",
        "{ pause }": "",
        "{nonvocalsound}": "",
        "{ nonvocalsound }": "",
        "{gap}": "",
        "{ gap }": "",
        "a_m_i_": "ami",
        "l_c_d_": "lcd",
        "t_v_": "tv",
        "p_m_s": "pms",
        "d_v_d_": "dvd",
    }
    out = text
    for k, v in replacements.items():
        out = out.replace(k, v)
    # Normalize whitespace a bit
    out = " ".join(out.split())
    return out


def iter_qmsum_json_dir(dir_path: Union[str, Path]) -> Iterator[Meeting]:
    """
    Iterate meetings from a directory containing per-meeting *.json files.
    meeting_id is derived from the filename stem (e.g., ES2002a).
    """
    p = Path(dir_path)
    for fp in sorted(p.glob("*.json")):
        with fp.open("r", encoding="utf-8") as f:
            yield fp.stem, json.load(f)


def iter_qmsum_jsonl(jsonl_path: Union[str, Path], meeting_id_prefix: str = "meeting") -> Iterator[Meeting]:
    """
    Iterate meetings from a *.jsonl file (one JSON object per line).
    Since QMSum JSONL typically has no explicit meeting id, we generate one.
    """
    p = Path(jsonl_path)
    with p.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            yield f"{meeting_id_prefix}_{i:05d}", json.loads(line)


@dataclass(frozen=True)
class QMSumDataFrames:
    meetings: pd.DataFrame
    transcripts: pd.DataFrame
    topics: pd.DataFrame
    queries: pd.DataFrame


DEFAULT_CONFLICT_PATTERNS: List[Tuple[str, str, int]] = [
    ("conflict", r"\bconflict\b", 5),
    ("disagree", r"\bdisagree(?:ment|ments)?\b", 4),
    ("argument", r"\bargument(?:s|ing)?\b", 4),
    ("fight", r"\bfight(?:s|ing)?\b", 4),
    ("blame", r"\bblame(?:d|s|ing)?\b|\bfault\b", 3),
    ("you are wrong", r"\byou(?:'re| are) wrong\b|\bthat'?s wrong\b", 3),
    ("unacceptable", r"\bunacceptable\b|\bnot acceptable\b", 3),
    ("frustrated", r"\bfrustrat\w*\b|\bannoy\w*\b", 2),
    ("angry/upset", r"\b(angry|upset)\b", 2),
    ("complain", r"\bcomplain\w*\b", 2),
    ("concern", r"\bconcern(s)?\b", 1),
    ("problem", r"\bproblem(s)?\b", 1),
    ("issue", r"\bissue(s)?\b", 1),
    ("however/but", r"\bhowever\b|\bno[, ]+but\b", 1),
]

DEFAULT_RESOLUTION_PATTERNS: List[Tuple[str, str, int]] = [
    ("resolve/resolution", r"\bresolve(?:d|s|ving)?\b|\bresolution\b", 5),
    ("compromise", r"\bcompromis(e|ed|ing)\b", 5),
    ("consensus", r"\bconsensus\b", 5),
    ("settle", r"\bsettle(?:d|s|ing)?\b", 4),
    ("agree", r"\bwe (?:all )?agree\b|\bagree(?:d|s|ing)?\b", 2),
    ("decide/decision", r"\bdecide(?:d|s)?\b|\bdecision(s)?\b", 2),
    ("apology", r"\b(i'?m|i am) sorry\b|\bapologiz\w*\b", 3),
    ("clarify", r"\bclarif(y|ied|ying)\b", 2),
    ("work it out", r"\bwork(?:ing)? it out\b", 3),
    ("next steps", r"\bnext steps?\b|\baction items?\b", 2),
]


def score_meetings_for_conflict_resolution(
    transcripts_df: pd.DataFrame,
    topics_df: Optional[pd.DataFrame] = None,
    *,
    meeting_id_col: str = "meeting_id",
    dataset_col: str = "dataset",
    text_col: str = "content_clean",
    speaker_col: str = "speaker",
    topic_col: str = "topic",
    conflict_patterns: Optional[List[Tuple[str, str, int]]] = None,
    resolution_patterns: Optional[List[Tuple[str, str, int]]] = None,
    conflict_threshold: int = 6,
    resolution_threshold: int = 6,
    return_evidence: bool = False,
    top_n_turn_evidence: int = 5,
) -> Union[pd.DataFrame, Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]]:
    """
    Rule-based scoring for whether each meeting contains (a) conflict and/or (b) conflict resolution.

    Returns a meeting-level DataFrame with scores + boolean flags. Optionally also returns:
      (summary_df, turn_evidence_df, topic_evidence_df)
    """
    if conflict_patterns is None:
        conflict_patterns = DEFAULT_CONFLICT_PATTERNS
    if resolution_patterns is None:
        resolution_patterns = DEFAULT_RESOLUTION_PATTERNS

    if transcripts_df.empty:
        summary = pd.DataFrame(
            columns=[
                dataset_col,
                meeting_id_col,
                "conflict_score",
                "resolution_score",
                "conflict_turns",
                "resolution_turns",
                "conflict_topic_score",
                "resolution_topic_score",
                "is_conflict",
                "is_resolution",
                "label",
            ]
        )
        if return_evidence:
            return summary, pd.DataFrame(), pd.DataFrame()
        return summary

    t = transcripts_df.copy()
    t["_text"] = t.get(text_col, "").fillna("").astype(str).str.lower()

    def _score_from_patterns(text_series: pd.Series, patterns: List[Tuple[str, str, int]]) -> pd.DataFrame:
        cols: Dict[str, pd.Series] = {}
        for name, pat, weight in patterns:
            rx = re.compile(pat, flags=re.IGNORECASE)
            cols[name] = text_series.str.contains(rx, regex=True).astype(int) * int(weight)
        return pd.DataFrame(cols)

    conflict_turn_scores = _score_from_patterns(t["_text"], conflict_patterns)
    resolution_turn_scores = _score_from_patterns(t["_text"], resolution_patterns)
    t["conflict_turn_score"] = conflict_turn_scores.sum(axis=1)
    t["resolution_turn_score"] = resolution_turn_scores.sum(axis=1)

    group_cols = [meeting_id_col]
    if dataset_col in t.columns:
        group_cols = [dataset_col, meeting_id_col]

    turns_agg = (
        t.groupby(group_cols, dropna=False)
        .agg(
            conflict_score=("conflict_turn_score", "sum"),
            resolution_score=("resolution_turn_score", "sum"),
            conflict_turns=("conflict_turn_score", lambda s: int((s > 0).sum())),
            resolution_turns=("resolution_turn_score", lambda s: int((s > 0).sum())),
        )
        .reset_index()
    )

    # Evidence turns (only matching turns)
    evidence_cols = [c for c in [dataset_col, meeting_id_col, "turn_idx", speaker_col, text_col] if c in t.columns]
    evidence_turns = t.loc[
        (t["conflict_turn_score"] > 0) | (t["resolution_turn_score"] > 0),
        evidence_cols + ["conflict_turn_score", "resolution_turn_score"],
    ].copy()

    # Topic-level weak signal (optional)
    topic_evidence = pd.DataFrame()
    if topics_df is not None and not topics_df.empty and topic_col in topics_df.columns:
        tp = topics_df.copy()
        tp["_topic_text"] = tp[topic_col].fillna("").astype(str).str.lower()
        conflict_topic_scores = _score_from_patterns(tp["_topic_text"], conflict_patterns)
        resolution_topic_scores = _score_from_patterns(tp["_topic_text"], resolution_patterns)
        tp["conflict_topic_score"] = conflict_topic_scores.sum(axis=1)
        tp["resolution_topic_score"] = resolution_topic_scores.sum(axis=1)

        topic_evidence_cols = [c for c in [dataset_col, meeting_id_col, topic_col, "topic_idx", "span_idx"] if c in tp.columns]
        topic_evidence = tp.loc[
            (tp["conflict_topic_score"] > 0) | (tp["resolution_topic_score"] > 0),
            topic_evidence_cols + ["conflict_topic_score", "resolution_topic_score"],
        ].copy()

        topic_group_cols = [meeting_id_col]
        if dataset_col in tp.columns:
            topic_group_cols = [dataset_col, meeting_id_col]
        topic_agg = (
            tp.groupby(topic_group_cols, dropna=False)
            .agg(
                conflict_topic_score=("conflict_topic_score", "sum"),
                resolution_topic_score=("resolution_topic_score", "sum"),
            )
            .reset_index()
        )
        summary = turns_agg.merge(topic_agg, on=topic_group_cols, how="left")
    else:
        summary = turns_agg.copy()
        summary["conflict_topic_score"] = 0
        summary["resolution_topic_score"] = 0

    summary[["conflict_topic_score", "resolution_topic_score"]] = summary[
        ["conflict_topic_score", "resolution_topic_score"]
    ].fillna(0)

    # Combine topic signal into overall scores (kept lightweight; still interpretable)
    summary["conflict_score"] = summary["conflict_score"] + summary["conflict_topic_score"].astype(int)
    summary["resolution_score"] = summary["resolution_score"] + summary["resolution_topic_score"].astype(int)

    summary["is_conflict"] = summary["conflict_score"] >= int(conflict_threshold)
    summary["is_resolution"] = summary["resolution_score"] >= int(resolution_threshold)

    def _label_row(r: pd.Series) -> str:
        if bool(r["is_conflict"]) and bool(r["is_resolution"]):
            return "conflict+resolution"
        if bool(r["is_conflict"]):
            return "conflict"
        if bool(r["is_resolution"]):
            return "resolution"
        return "none"

    summary["label"] = summary.apply(_label_row, axis=1)

    if not return_evidence:
        return summary

    # Reduce evidence to top-N turns per meeting for quick auditing
    if not evidence_turns.empty:
        sort_cols = [meeting_id_col, "conflict_turn_score", "resolution_turn_score"]
        ascending = [True, False, False]
        if dataset_col in evidence_turns.columns:
            sort_cols = [dataset_col] + sort_cols
            ascending = [True] + ascending
        evidence_turns = evidence_turns.sort_values(sort_cols, ascending=ascending, kind="stable")
        evidence_turns = (
            evidence_turns.groupby(group_cols, dropna=False)
            .head(int(top_n_turn_evidence))
            .reset_index(drop=True)
        )

    return summary, evidence_turns, topic_evidence


def build_qmsum_dfs(
    meetings: Iterable[Meeting],
    *,
    dataset: Optional[str] = None,
    split: Optional[str] = None,
    clean_text: bool = True,
) -> QMSumDataFrames:
    """
    Normalize QMSum-style nested JSON into 4 EDA-friendly DataFrames:
    - meetings: 1 row per meeting (high-level counts + concatenated transcript text)
    - transcripts: 1 row per transcript turn
    - topics: 1 row per topic span (topic + start/end turn indices)
    - queries: 1 row per query (general/specific) span (query + answer + optional start/end)
    """
    meeting_rows: List[JsonDict] = []
    transcript_rows: List[JsonDict] = []
    topic_rows: List[JsonDict] = []
    query_rows: List[JsonDict] = []

    for meeting_id, m in meetings:
        topic_list = m.get("topic_list") or []
        general_queries = m.get("general_query_list") or []
        specific_queries = m.get("specific_query_list") or []
        transcripts = m.get("meeting_transcripts") or []

        # transcripts (turn-level)
        combined_turns: List[str] = []
        for turn_idx, t in enumerate(transcripts):
            speaker = (t or {}).get("speaker")
            content = (t or {}).get("content", "")
            content_clean = clean_transcript_text(content) if clean_text else content
            transcript_rows.append(
                {
                    "dataset": dataset,
                    "split": split,
                    "meeting_id": meeting_id,
                    "turn_idx": turn_idx,
                    "speaker": speaker,
                    "content": content,
                    "content_clean": content_clean,
                    "n_chars": len(content_clean or ""),
                    "n_words": len((content_clean or "").split()),
                }
            )
            if speaker is not None:
                combined_turns.append(f"{str(speaker).strip()}: {content_clean}")
            else:
                combined_turns.append(content_clean)

        meeting_text = "\n".join(combined_turns)

        meeting_rows.append(
            {
                "dataset": dataset,
                "split": split,
                "meeting_id": meeting_id,
                "n_turns": len(transcripts),
                "n_topics": len(topic_list),
                "n_general_queries": len(general_queries),
                "n_specific_queries": len(specific_queries),
                "meeting_text": meeting_text,
                "meeting_text_chars": len(meeting_text),
                "meeting_text_words": len(meeting_text.split()),
            }
        )

        # topics (span-level)
        for topic_idx, topic in enumerate(topic_list):
            topic_name = (topic or {}).get("topic")
            spans = (topic or {}).get("relevant_text_span") or []
            if not spans:
                topic_rows.append(
                    {
                        "dataset": dataset,
                        "split": split,
                        "meeting_id": meeting_id,
                        "topic_idx": topic_idx,
                        "topic": topic_name,
                        "span_idx": None,
                        "span_start_turn": None,
                        "span_end_turn": None,
                    }
                )
            else:
                for span_idx, span in enumerate(spans):
                    start = _safe_int(span[0]) if isinstance(span, Sequence) and len(span) >= 2 else None
                    end = _safe_int(span[1]) if isinstance(span, Sequence) and len(span) >= 2 else None
                    topic_rows.append(
                        {
                            "dataset": dataset,
                            "split": split,
                            "meeting_id": meeting_id,
                            "topic_idx": topic_idx,
                            "topic": topic_name,
                            "span_idx": span_idx,
                            "span_start_turn": start,
                            "span_end_turn": end,
                        }
                    )

        # queries (span-level; general/specific)
        def _add_query_rows(q_list: Sequence[Mapping[str, Any]], qtype: str) -> None:
            for q_idx, q in enumerate(q_list):
                query = (q or {}).get("query")
                answer = (q or {}).get("answer")
                spans = (q or {}).get("relevant_text_span") or []
                if not spans:
                    query_rows.append(
                        {
                            "dataset": dataset,
                            "split": split,
                            "meeting_id": meeting_id,
                            "query_type": qtype,
                            "query_idx": q_idx,
                            "query": query,
                            "answer": answer,
                            "span_idx": None,
                            "span_start_turn": None,
                            "span_end_turn": None,
                        }
                    )
                else:
                    for span_idx, span in enumerate(spans):
                        start = _safe_int(span[0]) if isinstance(span, Sequence) and len(span) >= 2 else None
                        end = _safe_int(span[1]) if isinstance(span, Sequence) and len(span) >= 2 else None
                        query_rows.append(
                            {
                                "dataset": dataset,
                                "split": split,
                                "meeting_id": meeting_id,
                                "query_type": qtype,
                                "query_idx": q_idx,
                                "query": query,
                                "answer": answer,
                                "span_idx": span_idx,
                                "span_start_turn": start,
                                "span_end_turn": end,
                            }
                        )

        _add_query_rows(general_queries, "general")
        _add_query_rows(specific_queries, "specific")

    meetings_df = pd.DataFrame(meeting_rows)
    transcripts_df = pd.DataFrame(transcript_rows)
    topics_df = pd.DataFrame(topic_rows)
    queries_df = pd.DataFrame(query_rows)

    # Helpful ordering for EDA
    if not transcripts_df.empty:
        transcripts_df = transcripts_df.sort_values(["meeting_id", "turn_idx"], kind="stable").reset_index(drop=True)
    if not topics_df.empty:
        topics_df = topics_df.sort_values(["meeting_id", "topic_idx", "span_idx"], kind="stable").reset_index(drop=True)
    if not queries_df.empty:
        queries_df = queries_df.sort_values(["meeting_id", "query_type", "query_idx", "span_idx"], kind="stable").reset_index(drop=True)

    return QMSumDataFrames(
        meetings=meetings_df,
        transcripts=transcripts_df,
        topics=topics_df,
        queries=queries_df,
    )


def load_qmsum_split_as_dfs(
    *,
    root: Union[str, Path] = "data",
    dataset: str = "Product",  # Product | Academic | Committee | ALL
    split: str = "train",  # train | val | test | all
    prefer_jsonl: bool = True,
    clean_text: bool = True,
) -> QMSumDataFrames:
    """
    Convenience loader that reads from this repo's `data/` layout.

    Examples:
      load_qmsum_split_as_dfs(dataset="Product", split="train")
      load_qmsum_split_as_dfs(dataset="ALL", split="train", prefer_jsonl=True)
      load_qmsum_split_as_dfs(dataset="Product", split="all", prefer_jsonl=False)
    """
    root_p = Path(root)
    dataset_dir = root_p / dataset

    # "ALL" folder in this repo is special: it contains json files directly at data/ALL/
    # but also there are jsonl splits under data/<dataset>/jsonl/.
    json_dir: Optional[Path]
    if dataset.upper() == "ALL":
        # Prefer jsonl if it exists: data/ALL/jsonl/{split}.jsonl (if present), else data/ALL/*.json
        jsonl_fp = root_p / "ALL" / "jsonl" / f"{split}.jsonl"
        json_dir = root_p / "ALL" if split in {"all", "ALL"} else None
    else:
        jsonl_fp = dataset_dir / "jsonl" / f"{split}.jsonl"
        json_dir = dataset_dir / split if split in {"train", "val", "test"} else (dataset_dir / "all" if split == "all" else None)

    if prefer_jsonl and jsonl_fp.exists():
        meetings_iter = iter_qmsum_jsonl(jsonl_fp)
        return build_qmsum_dfs(meetings_iter, dataset=dataset, split=split, clean_text=clean_text)

    if json_dir is None or not json_dir.exists():
        raise FileNotFoundError(
            f"Could not find data for dataset={dataset!r}, split={split!r}. "
            f"Tried jsonl at {jsonl_fp} and json dir at {json_dir}."
        )

    meetings_iter = iter_qmsum_json_dir(json_dir)
    return build_qmsum_dfs(meetings_iter, dataset=dataset, split=split, clean_text=clean_text)

