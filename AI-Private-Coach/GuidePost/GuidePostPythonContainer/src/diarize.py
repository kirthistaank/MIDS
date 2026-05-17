from __future__ import annotations

import base64
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Union

try:
    from openai import OpenAI
except Exception as e:  # pragma: no cover
    raise ImportError(
        "Missing dependency: `openai`. Install it (e.g. `pip install openai`)."
    ) from e


ChunkingStrategy = Union[str, dict]


def _seg_get(seg: Any, key: str):
    """Support both OpenAI segment objects and dicts."""
    if hasattr(seg, key):
        return getattr(seg, key)
    return seg[key]


def merge_same_speaker_segments(
    segments: Iterable[Any],
    *,
    max_gap_s: float = 0.25,
) -> list[dict[str, Any]]:
    """Merge adjacent segments with the same speaker."""
    segs = sorted(segments, key=lambda s: float(_seg_get(s, "start")))
    merged: list[dict[str, Any]] = []

    for s in segs:
        speaker = _seg_get(s, "speaker")
        start = float(_seg_get(s, "start"))
        end = float(_seg_get(s, "end"))

        if not merged:
            merged.append({"speaker": speaker, "start": start, "end": end})
            continue

        prev = merged[-1]
        if speaker == prev["speaker"] and start <= prev["end"] + max_gap_s:
            prev["end"] = max(prev["end"], end)
        else:
            merged.append({"speaker": speaker, "start": start, "end": end})

    return merged


def to_data_url(path: str) -> str:
    """Encode an audio file as a data URL for known_speaker_references[]."""
    ext = os.path.splitext(path)[1].lower()
    mime_by_ext = {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".mp4": "audio/mp4",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".webm": "audio/webm",
    }
    mime = mime_by_ext.get(ext, "application/octet-stream")

    with open(path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def relabel_target_vs_other(
    segments: Iterable[Any], *, target_name: str, other_label: str = "other"
) -> list[dict[str, Any]]:
    """Collapse diarization labels into {target_name, other_label}."""
    relabeled: list[dict[str, Any]] = []
    for s in segments:
        speaker = _seg_get(s, "speaker")
        relabeled.append(
            {
                "speaker": target_name if speaker == target_name else other_label,
                "start": float(_seg_get(s, "start")),
                "end": float(_seg_get(s, "end")),
                "text": _seg_get(s, "text"),
            }
        )
    return relabeled


@dataclass(frozen=True)
class DiarizationResult:
    text: str
    segments: list[dict[str, Any]]


class Diarize:
    """Diarize + transcribe audio using OpenAI `gpt-4o-transcribe-diarize`."""

    def __init__(self, *, api_key: Optional[str] = None, client: Optional[OpenAI] = None):
        if client is not None:
            self._client = client
            return

        # Load `.env` if present (local dev) but don't override real env.
        try:
            from dotenv import find_dotenv, load_dotenv  # type: ignore

            env_path = find_dotenv(usecwd=True)
            if env_path:
                load_dotenv(env_path, override=False)
        except Exception:
            pass

        key = api_key or os.getenv("OPENAI_API_KEY")
        self._client = OpenAI(api_key=key) if key else OpenAI()

    def diarize_audio(
        self,
        path: str,
        *,
        known_speaker_names: Optional[list[str]] = None,
        known_speaker_references: Optional[list[str]] = None,
        language: Optional[str] = "en",
        chunking_strategy: ChunkingStrategy = "auto",
        timeout_s: Optional[float] = 300.0,
        verbose_segments: bool = False,
    ) -> DiarizationResult:
        """Diarize + transcribe audio.

        `known_speaker_references` should be data URLs (see `to_data_url()`).
        """
        with open(path, "rb") as audio_file:
            transcript = self._client.audio.transcriptions.create(
                model="gpt-4o-transcribe-diarize",
                file=audio_file,
                response_format="diarized_json",
                chunking_strategy=chunking_strategy,
                language=language,
                known_speaker_names=known_speaker_names,
                known_speaker_references=known_speaker_references,
                timeout=timeout_s,
            )

        if verbose_segments:
            for segment in transcript.segments:
                print(segment.speaker, segment.text, segment.start, segment.end)

        seg_dicts: list[dict[str, Any]] = [
            {
                "speaker": _seg_get(s, "speaker"),
                "start": float(_seg_get(s, "start")),
                "end": float(_seg_get(s, "end")),
                "text": _seg_get(s, "text"),
            }
            for s in transcript.segments
        ]
        return DiarizationResult(text=transcript.text, segments=seg_dicts)

    def diarize_target_vs_other(
        self,
        audio_path: str,
        *,
        target_name: str,
        target_reference_audio: str,
        other_label: str = "other",
        two_pass: bool = False,
        language: str = "en",
        verbose_segments: bool = False,
        chunking_strategy: ChunkingStrategy = "auto",
    ) -> DiarizationResult:
        """Diarize with one stored target identity, label everyone else as `other_label`."""
        base = self.diarize_audio(
            audio_path,
            known_speaker_names=[target_name],
            known_speaker_references=[to_data_url(target_reference_audio)],
            language=language,
            chunking_strategy=chunking_strategy,
            verbose_segments=verbose_segments,
        )

        if not two_pass:
            return DiarizationResult(
                text=base.text,
                segments=relabel_target_vs_other(base.segments, target_name=target_name, other_label=other_label),
            )

        # Keeping two_pass in the signature for future use.
        return DiarizationResult(
            text=base.text,
            segments=relabel_target_vs_other(base.segments, target_name=target_name, other_label=other_label),
        )

