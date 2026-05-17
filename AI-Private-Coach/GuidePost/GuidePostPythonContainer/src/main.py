"""Guidepost FastAPI backend.

This module provides a minimal API for:
- Uploading an audio file and running diarization/transcription in the background.
- Fetching processing status (for polling from the frontend).
- Chatting with a coaching assistant grounded in the processed conversation.
- Exposing a small surface of the RAG system for retrieval utilities.

Design notes:
- Storage is in-memory for jobs + conversations (good for MVP; not durable across restarts).
- Uploaded audio is persisted to disk under `GUIDEPOST_DATA_DIR` so background work can read it.
"""

from __future__ import annotations

import os
from pathlib import Path
from src.config import PINECONE_INDEX_NAME
from logging.handlers import RotatingFileHandler
from src.logging_utils import get_logger
import logging
import sys
import re
import hashlib
# Load .env from project root (GuidePostPythonContainer) so PINECONE_API_KEY etc. are set
# before any os.getenv, regardless of CWD (e.g. uvicorn from repo root).
try:
    from dotenv import load_dotenv
    _env_file = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(_env_file)
except Exception:
    pass

# Read config directly from environment
#PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "delete-test-rag-ingest-git")

# setting up logger

def _setup_kg_logger() -> logging.Logger:
    """Logger for RAG retrieval pipeline: stdout + rotating file under /tmp/RAG_retrieval."""
    logger = logging.getLogger("RAG_retrieval")
    if logger.handlers:
        return logger  # avoid duplicate handlers on repeated imports

    logger.setLevel(logging.DEBUG)

    log_dir = Path("/tmp/RAG_retrieval")
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        # If /tmp is not writable, still allow stdout logging.
        pass

    fmt = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Stdout handler
    sh = logging.StreamHandler(stream=sys.stdout)
    sh.setLevel(logging.DEBUG)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    # Rotating file handler: 500KB each, keep 3 files total (current + 2 backups)
    try:
        fh_path = log_dir / "main.log"
        fh = RotatingFileHandler(
            filename=str(fh_path),
            maxBytes=500 * 1024,
            backupCount=2,
            encoding="utf-8",
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception:
        # If file handler can't be created, stdout logging still works.
        pass

    logger.propagate = False
    logger.debug("RAG retrieval logger initialized (stdout + rotating file in /tmp/RAG_retrieval).")
    return logger


logger = _setup_kg_logger()
def _normalize_embed_model(name: str) -> str:
    """Strip quotes/whitespace and ensure full sentence-transformers/ model id."""
    if not name:
        return "sentence-transformers/multi-qa-mpnet-base-dot-v1"
    name = name.strip().strip('"').strip("'")
    if not name.startswith("sentence-transformers/"):
        name = f"sentence-transformers/{name}"
    return name


HF_EMBED_MODEL = _normalize_embed_model(
    os.getenv("HUGGING_FACE_EMBED_MODEL", "sentence-transformers/multi-qa-mpnet-base-dot-v1")
)
CLOUD_NEO4J_URI = os.getenv("NEO4J_URI", "")
CLOUD_NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "")
CLOUD_NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

import threading
import time
import uuid
from typing import Any, Literal, Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel, Field

from src.diarize import Diarize
from src.database import SessionLocal, engine
from src.database_models import (
    AudioJob as DbAudioJob,
    Base,
    ChatConversation as DbChatConversation,
    HomeSummary as DbHomeSummary,
    Session as DbSession,
    User as DbUser,
    VoiceReference as DbVoiceReference,
)
import uuid
from datetime import date, datetime, timedelta
from sqlalchemy import and_, func
import math
import json
import re


AudioStatus = Literal["uploaded", "processing", "ready", "error"]
currentUserId = None

def getCurrentUserId():
    """Return the last authenticated user id set by user endpoints (module-level session hint)."""
    return currentUserId


class AudioUploadResponse(BaseModel):
    """Response from POST /api/audio: new job id for status polling."""

    audioId: str


class AudioJobResponse(BaseModel):
    """Public shape for GET /api/audio/{id}: processing state without full transcript payload."""

    audioId: str
    status: AudioStatus
    createdAt: float
    updatedAt: float
    transcript: Optional[str] = None
    analysis: Optional[str] = None
    finalStrategy: Optional[str] = None
    errorMessage: Optional[str] = None


class ChatRequest(BaseModel):
    """Inbound chat turn: message plus optional conversation and coaching phase metadata."""

    audioId: str
    conversationId: Optional[str] = None
    message: str = Field(min_length=1)
    userContext: Optional[str] = None
    targetName: Optional[str] = None
    phase: Optional[str] = None  # "alignment" | "coaching"


class ChatResponse(BaseModel):
    """Assistant reply plus conversation id and optional phase transition (alignment → coaching)."""

    reply: str
    conversationId: Optional[str] = None
    phase: Optional[str] = None
    alignedFocus: Optional[str] = None


class ReportRequest(BaseModel):
    """Request to generate a coaching report for a ready audio job."""

    audioId: str
    userContext: Optional[str] = None
    targetName: Optional[str] = None
    alignedFocus: Optional[str] = None
    conversationId: Optional[str] = None

class UserInput(BaseModel):
    """Onboarding payload for POST /api/updateUser (creates user and returns session history)."""

    name: str
    email: str
    occupation: str
    seniorityLevel: str


class UserProfile(BaseModel):
    """User profile returned by GET/POST /api/user."""

    id: str
    email: str
    name: Optional[str] = None
    occupation: Optional[str] = None
    seniorityLevel: Optional[str] = None
    rankedSkills: Optional[list[str]] = None
    otherFocus: Optional[str] = None
    voiceRecorded: Optional[bool] = None


class UpsertUserRequest(BaseModel):
    """Fields for PATCH-style upsert of a user row keyed by email."""

    email: str
    name: Optional[str] = None
    occupation: Optional[str] = None
    seniorityLevel: Optional[str] = None
    rankedSkills: Optional[list[str]] = None
    otherFocus: Optional[str] = None
    voiceRecorded: Optional[bool] = None


class ResetUserRequest(BaseModel):
    """Identifies which user to delete for dev reset (POST /api/reset_user)."""

    email: str


class SessionsReponse(BaseModel):
    """One past session row (report text plus CRI/CEI-style scores) from user bootstrap."""

    report: str
    cri: float
    cei: float
    sentiment: float
    speaker_volatility: float


class DashboardProgressPoint(BaseModel):
    """Single day on the dashboard progress chart (date + mapped overall score)."""

    date: str  # ISO date (YYYY-MM-DD)
    overall: float  # 0-100


class DashboardSkillScore(BaseModel):
    """Named skill score (CEI/CRI mapped to 0–100) with optional period-over-period change."""

    skill: str
    score: float  # 0-100
    changePct: Optional[float] = None


class DashboardMetricsResponse(BaseModel):
    """Aggregated dashboard metrics for GET /api/dashboard_metrics."""

    overallScore: float  # 0-100 (mapped from CRI/CEI 1-5)
    overallChangePct: Optional[float] = None
    conversationsAnalyzedThisMonth: int
    daysActiveThisMonth: int
    progressOverTime: list[DashboardProgressPoint]
    skills: list[DashboardSkillScore]
    avgCri: Optional[float] = None  # raw 1-5
    avgCei: Optional[float] = None  # raw 1-5


class ReportResponse(BaseModel):
    """Generated coaching narrative and final strategy text from POST /api/report."""

    report: str
    finalStrategy: Optional[str] = None



class YTDSummaryResponse(BaseModel):
    """Short home-dashboard paragraph from GET /api/home-summary."""

    summary: str


_DATA_DIR = Path(os.getenv("GUIDEPOST_DATA_DIR", "./data")).resolve()
_AUDIO_DIR = _DATA_DIR / "audio_uploads"
_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
_AUDIO_JOB_DIR = _DATA_DIR / "audio_jobs"
_AUDIO_JOB_DIR.mkdir(parents=True, exist_ok=True)
_CHAT_CONVO_DIR = _DATA_DIR / "chat_conversations"
_CHAT_CONVO_DIR.mkdir(parents=True, exist_ok=True)
_VOICE_REF_DIR = _DATA_DIR / "voice_references"
_VOICE_REF_DIR.mkdir(parents=True, exist_ok=True)
_HOME_SUMMARY_DIR = _DATA_DIR / "home_summaries"
_HOME_SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

_LOCK = threading.Lock()
_AUDIO_JOBS: dict[str, dict[str, Any]] = {}
_CONVERSATIONS: dict[str, list[dict[str, str]]] = {}
_VOICE_REFS: dict[str, str] = {}

# Home summary cache (fast dashboard loads)
_HOME_SUMMARY_TTL_S = float(os.getenv("HOME_SUMMARY_TTL_S", str(24 * 60 * 60)))  # default: 24 hours
_HOME_SUMMARY_REFRESH_DEBOUNCE_S = float(os.getenv("HOME_SUMMARY_REFRESH_DEBOUNCE_S", "5"))
_HOME_SUMMARY_TIMERS: dict[str, threading.Timer] = {}

_PERSIST_BACKEND = os.getenv("GUIDEPOST_PERSIST_BACKEND", "disk").strip().lower()
_S3_BUCKET = (os.getenv("GUIDEPOST_S3_BUCKET") or "").strip()
_S3_REGION = (os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "").strip() or None

_AUDIO_JOB_PERSIST_KEYS: tuple[str, ...] = (
    "status",
    "createdAt",
    "updatedAt",
    "path",
    "filename",
    "transcript",
    "segments",
    "analysis",
    "finalStrategy",
    "errorMessage",
    "userContext",
    "targetName",
    "userEmail",
    "userId",
    "targetReferencePath",
    "alignedFocus",
)


def _audio_job_disk_path(audio_id: str) -> Path:
    """Filesystem path for the JSON snapshot of an audio job (disk persistence backend)."""
    return _AUDIO_JOB_DIR / f"{audio_id}.json"


def _persist_audio_job(audio_id: str, job: dict[str, Any]) -> None:
    """Persist a JSON-serializable subset of an audio job to disk.

    This makes audio jobs durable across container restarts (docker compose down/up).
    We intentionally do NOT persist `docs` (LangChain Document objects) because those
    are not JSON-serializable and can be reconstructed from `segments`.
    """
    try:
        serializable: dict[str, Any] = {}
        for k in _AUDIO_JOB_PERSIST_KEYS:
            if k in job:
                serializable[k] = job.get(k)
        _audio_job_disk_path(audio_id).write_text(
            json.dumps(serializable, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        # Best-effort persistence: do not fail requests/jobs if disk write fails.
        pass


def _db_row_to_job_dict(row: DbAudioJob) -> dict[str, Any]:
    """Map an `audio_jobs` ORM row into the in-memory job dict shape (including rebuilt LangChain docs)."""
    segments = None
    try:
        if row.segments_json:
            segments = json.loads(row.segments_json)
    except Exception:
        segments = None

    job: dict[str, Any] = {
        "status": row.status or "uploaded",
        "createdAt": row.created_at.timestamp() if getattr(row, "created_at", None) else 0.0,
        "updatedAt": row.updated_at.timestamp() if getattr(row, "updated_at", None) else 0.0,
        "filename": row.filename,
        "path": row.audio_local_path,
        "audioS3Bucket": row.audio_s3_bucket,
        "audioS3Key": row.audio_s3_key,
        "targetReferencePath": row.target_ref_local_path,
        "targetReferenceS3Bucket": row.target_ref_s3_bucket,
        "targetReferenceS3Key": row.target_ref_s3_key,
        "transcript": row.transcript or "",
        "segments": segments,
        "analysis": row.analysis,
        "finalStrategy": row.final_strategy,
        "errorMessage": row.error_message,
        "userContext": row.user_context,
        "targetName": row.target_name,
        "userEmail": row.user_email,
        "userId": row.user_id,
        "alignedFocus": row.aligned_focus,
        "docs": None,
    }

    # Rebuild docs from segments when available (helps `/api/report` after restart).
    if job.get("segments"):
        try:
            from langchain_core.documents import Document  # type: ignore

            segs = job.get("segments") or []
            if isinstance(segs, list):
                docs = []
                for s in segs:
                    if not isinstance(s, dict):
                        continue
                    text = str(s.get("text", "")).strip()
                    if not text:
                        continue
                    docs.append(
                        Document(
                            page_content=text,
                            metadata={
                                "speaker": str(s.get("speaker", "Unknown")),
                                "timestamp": str(s.get("start", "N/A")),
                                "source_type": "Diarization",
                            },
                        )
                    )
                job["docs"] = docs
        except Exception:
            job["docs"] = None

    return job


def _db_get_audio_job(audio_id: str) -> Optional[dict[str, Any]]:
    """Load a single audio job from Postgres when `GUIDEPOST_PERSIST_BACKEND=db`."""
    with SessionLocal() as db:
        row = db.query(DbAudioJob).filter(DbAudioJob.audio_id == audio_id).first()
        if not row:
            return None
        return _db_row_to_job_dict(row)


def _db_put_audio_job(audio_id: str, job: dict[str, Any]) -> None:
    """Upsert job fields into `audio_jobs` (best-effort; failures are swallowed)."""
    # Upsert job into DB. Best-effort: do not crash request if DB write fails.
    try:
        segments_json = None
        if job.get("segments") is not None:
            try:
                segments_json = json.dumps(job.get("segments"), ensure_ascii=False)
            except Exception:
                segments_json = None

        with SessionLocal() as db:
            row = db.query(DbAudioJob).filter(DbAudioJob.audio_id == audio_id).first()
            if not row:
                row = DbAudioJob(audio_id=audio_id)
                db.add(row)

            row.status = str(job.get("status") or row.status or "uploaded")
            row.filename = job.get("filename") or row.filename

            row.audio_local_path = job.get("path") or row.audio_local_path
            row.audio_s3_bucket = job.get("audioS3Bucket") or row.audio_s3_bucket
            row.audio_s3_key = job.get("audioS3Key") or row.audio_s3_key

            row.target_ref_local_path = job.get("targetReferencePath") or row.target_ref_local_path
            row.target_ref_s3_bucket = job.get("targetReferenceS3Bucket") or row.target_ref_s3_bucket
            row.target_ref_s3_key = job.get("targetReferenceS3Key") or row.target_ref_s3_key

            row.user_context = job.get("userContext") or row.user_context
            row.target_name = job.get("targetName") or row.target_name
            row.user_email = job.get("userEmail") or row.user_email
            row.user_id = job.get("userId") or row.user_id
            row.aligned_focus = job.get("alignedFocus") or row.aligned_focus

            row.transcript = job.get("transcript") or row.transcript
            if segments_json is not None:
                row.segments_json = segments_json
            row.analysis = job.get("analysis") or row.analysis
            row.final_strategy = job.get("finalStrategy") or row.final_strategy
            row.error_message = job.get("errorMessage") or row.error_message

            db.commit()
    except Exception:
        pass


def _db_get_chat_conversation(
    conversation_id: str, *, audio_id: str,
) -> Optional[list[dict[str, str]]]:
    """Load chat messages for a conversation tied to an audio job (db persistence)."""
    with SessionLocal() as db:
        row = (
            db.query(DbChatConversation)
            .filter(DbChatConversation.conversation_id == conversation_id, DbChatConversation.audio_id == audio_id)
            .first()
        )
        if not row or not row.messages_json:
            return None
        try:
            msgs = json.loads(row.messages_json)
        except Exception:
            return None
        if not isinstance(msgs, list):
            return None
        out: list[dict[str, str]] = []
        for m in msgs:
            if not isinstance(m, dict):
                continue
            role = str(m.get("role") or "")
            content = str(m.get("content") or "")
            if role not in ("user", "assistant") or not content:
                continue
            out.append({"role": role, "content": content})
        return out


def _db_put_chat_conversation(
    conversation_id: str, *, audio_id: str, messages: list[dict[str, str]],
) -> None:
    """Persist full message list for a chat conversation (best-effort)."""
    try:
        messages_json = json.dumps(messages, ensure_ascii=False)
        with SessionLocal() as db:
            row = db.query(DbChatConversation).filter(DbChatConversation.conversation_id == conversation_id).first()
            if not row:
                row = DbChatConversation(conversation_id=conversation_id, audio_id=audio_id)
                db.add(row)
            row.audio_id = audio_id
            row.messages_json = messages_json
            db.commit()
    except Exception:
        pass


def _db_get_voice_reference(target_name: str) -> Optional[dict[str, str]]:
    """Return S3 bucket/key or local path for a stored voice reference, if any."""
    with SessionLocal() as db:
        row = db.query(DbVoiceReference).filter(DbVoiceReference.target_name == target_name).first()
        if not row:
            return None
        if row.s3_bucket and row.s3_key:
            return {"s3Bucket": row.s3_bucket, "s3Key": row.s3_key}
        if row.local_path:
            return {"path": row.local_path}
        return None


def _db_put_voice_reference(target_name: str, *, s3_bucket: Optional[str], s3_key: Optional[str], local_path: Optional[str]) -> None:
    """Upsert where the voice sample lives so diarization can resolve it after restarts."""
    try:
        with SessionLocal() as db:
            row = db.query(DbVoiceReference).filter(DbVoiceReference.target_name == target_name).first()
            if not row:
                row = DbVoiceReference(target_name=target_name)
                db.add(row)
            if s3_bucket:
                row.s3_bucket = s3_bucket
            if s3_key:
                row.s3_key = s3_key
            if local_path:
                row.local_path = local_path
            db.commit()
    except Exception:
        pass


def _s3_enabled() -> bool:
    """True when uploads should use S3 (bucket env configured)."""
    return bool(_S3_BUCKET)


def _get_s3_client():
    """Construct a boto3 S3 client using configured region when set."""
    import boto3  # type: ignore

    if _S3_REGION:
        return boto3.client("s3", region_name=_S3_REGION)
    return boto3.client("s3")


def _s3_put_bytes(*, key: str, body: bytes, content_type: Optional[str]) -> None:
    """Upload raw bytes to the configured bucket under `key` (optional Content-Type)."""
    client = _get_s3_client()
    extra: dict[str, Any] = {}
    if content_type:
        extra["ContentType"] = content_type
    client.put_object(Bucket=_S3_BUCKET, Key=key, Body=body, **extra)


def _s3_download_to_tmp(*, bucket: str, key: str, suffix: str) -> str:
    """Download an object to a unique file under /tmp; returns the local path."""
    client = _get_s3_client()
    tmp_path = Path("/tmp") / f"{uuid.uuid4().hex}{suffix}"
    client.download_file(bucket, key, str(tmp_path))
    return str(tmp_path)


def _materialize_audio_to_local(job: dict[str, Any]) -> str:
    """Resolve the job's main audio to a local path, downloading from S3 when needed."""
    # Prefer S3 when present (Fargate-safe), otherwise use local path.
    if job.get("audioS3Bucket") and job.get("audioS3Key"):
        return _s3_download_to_tmp(
            bucket=str(job["audioS3Bucket"]),
            key=str(job["audioS3Key"]),
            suffix=Path(str(job.get("filename") or "audio")).suffix or ".bin",
        )
    return str(job.get("path") or "")


def _materialize_voice_ref_to_local(job: dict[str, Any], *, target_name: str) -> Optional[str]:
    """Resolve target speaker reference audio for diarization (job fields, cache, or DB)."""
    if job.get("targetReferenceS3Bucket") and job.get("targetReferenceS3Key"):
        return _s3_download_to_tmp(
            bucket=str(job["targetReferenceS3Bucket"]),
            key=str(job["targetReferenceS3Key"]),
            suffix=Path(str(job.get("targetReferenceS3Key") or "")).suffix or ".webm",
        )
    if job.get("targetReferencePath"):
        return str(job.get("targetReferencePath"))
    if target_name:
        with _LOCK:
            if target_name in _VOICE_REFS:
                return str(_VOICE_REFS[target_name])
        if _PERSIST_BACKEND == "db":
            ref = _db_get_voice_reference(target_name)
            if ref and ref.get("s3Bucket") and ref.get("s3Key"):
                return _s3_download_to_tmp(
                    bucket=str(ref["s3Bucket"]),
                    key=str(ref["s3Key"]),
                    suffix=Path(str(ref["s3Key"])).suffix or ".webm",
                )
            if ref and ref.get("path"):
                return str(ref["path"])
    return None


def _load_audio_job_from_disk(audio_id: str) -> Optional[dict[str, Any]]:
    """Read a job JSON from disk and normalize defaults; rebuilds `docs` from segments when possible."""
    p = _audio_job_disk_path(audio_id)
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None

    job: dict[str, Any] = dict(raw)
    job.setdefault("status", "uploaded")
    job.setdefault("createdAt", 0.0)
    job.setdefault("updatedAt", job.get("createdAt", 0.0))
    job.setdefault("transcript", "")
    job.setdefault("segments", None)
    job.setdefault("analysis", None)
    job.setdefault("finalStrategy", None)
    job.setdefault("errorMessage", None)
    job["docs"] = None

    # Rebuild docs from segments when available (helps `/api/report` after restart).
    if job.get("segments"):
        try:
            from langchain_core.documents import Document  # type: ignore

            segs = job.get("segments") or []
            if isinstance(segs, list):
                docs = []
                for s in segs:
                    if not isinstance(s, dict):
                        continue
                    text = str(s.get("text", "")).strip()
                    if not text:
                        continue
                    docs.append(
                        Document(
                            page_content=text,
                            metadata={
                                "speaker": str(s.get("speaker", "Unknown")),
                                "timestamp": str(s.get("start", "N/A")),
                                "source_type": "Diarization",
                            },
                        )
                    )
                job["docs"] = docs
        except Exception:
            job["docs"] = None

    return job


def _chat_convo_disk_path(conversation_id: str) -> Path:
    """Path to persisted chat JSON for a conversation id (disk persistence backend)."""
    return _CHAT_CONVO_DIR / f"{conversation_id}.json"


def _persist_chat_conversation(
    conversation_id: str, *, audio_id: str, messages: list[dict[str, str]],
) -> None:
    """Write conversation messages plus audio id to disk (best-effort)."""
    try:
        _chat_convo_disk_path(conversation_id).write_text(
            json.dumps({"audioId": audio_id, "messages": messages}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def _load_chat_conversation(
    conversation_id: str, *, audio_id: str,
) -> Optional[list[dict[str, str]]]:
    """Load messages from disk if the file exists and matches the expected audio id."""
    p = _chat_convo_disk_path(conversation_id)
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    if str(raw.get("audioId") or "") != str(audio_id):
        return None
    msgs = raw.get("messages")
    if not isinstance(msgs, list):
        return None
    out: list[dict[str, str]] = []
    for m in msgs:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "")
        content = str(m.get("content") or "")
        if role not in ("user", "assistant") or not content:
            continue
        out.append({"role": role, "content": content})
    return out


def _now() -> float:
    """Return a unix timestamp (seconds since epoch).

    We store timestamps as floats for simplicity and JSON-friendliness.
    """
    return time.time()


def _require_openai_key() -> None:
    """Fail fast if diarization is requested without an OpenAI API key.

    The diarization pipeline calls OpenAI; this avoids background jobs silently failing later.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="Missing OPENAI_API_KEY for diarization")


def _job_to_response(audio_id: str, job: dict[str, Any]) -> AudioJobResponse:
    """Convert an internal job dict into the public API response shape."""
    return AudioJobResponse(
        audioId=audio_id,
        status=job.get("status", "uploaded"),
        createdAt=job.get("createdAt", 0.0),
        updatedAt=job.get("updatedAt", 0.0),
        # Intentionally do not return transcript/report text during polling.
        # We still generate/persist the report for CRI/CEI extraction into SQL.
        transcript=None,
        analysis=None,
        finalStrategy=job.get("finalStrategy"),
        errorMessage=job.get("errorMessage"),
    )


def _get_job(audio_id: str) -> dict[str, Any]:
    """Fetch an audio job from in-memory storage.

    Raises:
      - 404 if the `audioId` does not exist.
    """
    with _LOCK:
        job = _AUDIO_JOBS.get(audio_id)
        if job:
            return dict(job)

    if _PERSIST_BACKEND == "db":
        db_job = _db_get_audio_job(audio_id)
        if db_job is not None:
            with _LOCK:
                _AUDIO_JOBS.setdefault(audio_id, db_job)
                return dict(_AUDIO_JOBS[audio_id])

    disk_job = _load_audio_job_from_disk(audio_id)
    if disk_job is not None:
        with _LOCK:
            _AUDIO_JOBS.setdefault(audio_id, disk_job)
            return dict(_AUDIO_JOBS[audio_id])

    raise HTTPException(status_code=404, detail="audioId not found")


def _set_job(audio_id: str, patch: dict[str, Any]) -> None:
    """Patch an existing job in-place and refresh its `updatedAt` timestamp.

    This is the single write-path used by background workers + endpoints.
    """
    snapshot: Optional[dict[str, Any]] = None
    with _LOCK:
        if audio_id not in _AUDIO_JOBS:
            raise KeyError(audio_id)
        _AUDIO_JOBS[audio_id].update(patch)
        _AUDIO_JOBS[audio_id]["updatedAt"] = _now()
        snapshot = dict(_AUDIO_JOBS[audio_id])
    if snapshot is not None:
        if _PERSIST_BACKEND == "db":
            _db_put_audio_job(audio_id, snapshot)
        else:
            _persist_audio_job(audio_id, snapshot)


def _put_job(audio_id: str, job: dict[str, Any]) -> None:
    """Replace the full in-memory job and mirror it to the active persistence backend."""
    with _LOCK:
        _AUDIO_JOBS[audio_id] = dict(job)
    if _PERSIST_BACKEND == "db":
        _db_put_audio_job(audio_id, dict(job))
    else:
        _persist_audio_job(audio_id, dict(job))


def _safe_filename(name: str) -> str:
    """Sanitize a client-provided filename for filesystem usage.

    Why: uploaded filenames can contain path separators or odd characters.
    We keep it readable but safe, and we still generate our own unique ID.
    """
    keep = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._"
    cleaned = "".join([c if c in keep else "_" for c in (name or "audio")])
    return cleaned[:180] or "audio"


def _lazy_import_kgrag():
    """Import KG RAGQuery lazily to avoid loading heavy ML deps at startup."""
    from src.KG import RAGQuery as KGRAG  # type: ignore

    return KGRAG


def _lazy_import_logic_rag():
    """Import LogicRAG lazily to avoid loading heavy ML deps at startup."""
    from src.RAG_logic import RAGQuery as LogicRAG  # type: ignore

    return LogicRAG


_OPENAI_SINGLETON: Optional[OpenAI] = None
_LOGIC_RAG_SINGLETON = None
_LOGIC_RAG_LOCK = threading.Lock()


def _get_openai() -> OpenAI:
    """Return a singleton OpenAI client (fallback when KG/RAG is unavailable)."""
    global _OPENAI_SINGLETON
    if _OPENAI_SINGLETON is not None:
        return _OPENAI_SINGLETON
    timeout = float(os.getenv("OPENAI_TIMEOUT", "90"))
    _OPENAI_SINGLETON = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=timeout)
    return _OPENAI_SINGLETON


def _get_logic_rag():
    """Return a singleton LogicRAG instance (avoids re-loading embeddings/Pinecone/Cohere on every chat/report)."""
    global _LOGIC_RAG_SINGLETON
    with _LOGIC_RAG_LOCK:
        if _LOGIC_RAG_SINGLETON is not None:
            return _LOGIC_RAG_SINGLETON
        LogicRAG = _lazy_import_logic_rag()
        _LOGIC_RAG_SINGLETON = LogicRAG(
            index_name=PINECONE_INDEX_NAME,
            embedding_model_name=HF_EMBED_MODEL,
        )
        return _LOGIC_RAG_SINGLETON


def _openai_chat(*, system: str, messages: list[dict[str, str]]) -> str:
    """Single chat completion via OpenAI when LogicRAG/Cohere path is unavailable."""
    client = _get_openai()
    model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
    res = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, *messages],
        temperature=0.2,
    )
    return (res.choices[0].message.content or "").strip()



def _generate_report_from_segments(
    *,
    audio_id: str,
    segments: list[dict[str, Any]],
    user_context: Optional[str],
) -> str:
    """Generate an initial coaching report from diarized segments.

    This is the "analysis" step: take diarization output and ask the coach LLM to produce
    actionable feedback, grounded in quotes (with timestamps).

    Notes:
    - `audio_id` is currently unused in the prompt; it is included to make it easy to
      add auditing/tracing later.
    - This uses `rag.llm` (Cohere via LangChain in your current implementation).
    """
    lines: list[str] = []
    for s in segments:
        spk = str(s.get("speaker", "Unknown"))
        start = float(s.get("start", 0.0))
        text = str(s.get("text", "")).strip()
        if not text:
            continue
        lines.append(f"[{start:0.2f}s] {spk}: {text}")

    transcript_block = "\n".join(lines) if lines else "(no segments)"
    context_block = user_context.strip() if user_context else "None"

    from langchain_core.messages import HumanMessage, SystemMessage  # type: ignore

    system = f"""You are a World-Class Human-Centric Cognitive Coach.

You will be given:
- User context (what they care about / what they want to improve)
- A diarized conversation transcript (speaker-labeled)

Your job:
- Identify 3-6 high-leverage coaching opportunities
- Ground feedback in specific quotes (include timestamps)
- Provide concrete next-step experiments/questions

Return a concise but actionable report.
"""

    human = f"""USER CONTEXT:
{context_block}

TRANSCRIPT (diarized):
{transcript_block}
"""

    try:
        logic_rag = _get_logic_rag()
        res = logic_rag.llm.invoke([SystemMessage(content=system), HumanMessage(content=human)])
        return res.content if hasattr(res, "content") else str(res)
    except Exception:
        try:
            return _openai_chat(system=system, messages=[{"role": "user", "content": human}])
        except Exception as e2:
            raise HTTPException(status_code=500, detail=f"Report generation failed: {e2}") from e2


def _insights_namespace() -> str:
    """Pinecone namespace name for embedded transcript highlight vectors."""
    return (os.getenv("PINECONE_INSIGHTS_NAMESPACE") or "transcript_insights").strip() or "transcript_insights"


def _segments_to_timestamped_lines(segments: list[dict[str, Any]], *, limit_chars: int = 12000) -> str:
    """Flatten diarization segments into a truncated, timestamped transcript block for prompts."""
    lines: list[str] = []
    for s in segments:
        try:
            spk = str(s.get("speaker", "Unknown"))
            start = float(s.get("start", 0.0))
            txt = str(s.get("text", "")).strip()
        except Exception:
            continue
        if not txt:
            continue
        lines.append(f"[{start:0.2f}s] {spk}: {txt}")
    block = "\n".join(lines)
    return block[:limit_chars]


def _extract_json_array(text: str) -> list[Any]:
    """Best-effort: parse a JSON array from an LLM response."""
    raw = (text or "").strip()
    if not raw:
        return []
    # Strip ``` fences if present
    if raw.startswith("```"):
        raw = raw.strip().strip("`").strip()
    a = raw.find("[")
    b = raw.rfind("]")
    if a == -1 or b == -1 or b <= a:
        return []
    candidate = raw[a : b + 1]
    try:
        v = json.loads(candidate)
        return v if isinstance(v, list) else []
    except Exception:
        return []


def _compute_transcript_highlights_and_tags(
    *,
    logic_rag: Any,
    user_name: str,
    user_context: str,
    segments: list[dict[str, Any]],
    max_items: int = 8,
) -> list[dict[str, Any]]:
    """Use the LLM to extract highlight+tag pairs grounded in the transcript."""
    from langchain_core.messages import HumanMessage, SystemMessage  # type: ignore

    transcript_block = _segments_to_timestamped_lines(segments, limit_chars=12000)
    if not transcript_block.strip():
        return []

    system = f"""You are Guidepost's Evidence Tagger.

Read the speaker-labeled transcript and extract highlight segments that show coachable communication patterns.
You MUST ground highlights in exact quotes from the transcript.

Return ONLY valid JSON: an array of objects with these keys:
- speaker: string
- start_s: number
- end_s: number (>= start_s; if unknown, repeat start_s)
- quote: string (exact quote from transcript, <= 220 chars)
- guidepost_tag: string (e.g., "Pattern Detected: Diminishing Language (CBT Distortion: Minimizing).")
- pattern: string (short, e.g., "Diminishing language")
- cbt_distortion: string|null (e.g., "Minimizing")
- confidence: number (0-1)

Constraints:
- Between 4 and {max_items} items.
- Focus on patterns like: minimizing, dismissiveness, blame shifting, catastrophizing, mind reading, defensiveness, stonewalling, unclear asks, vague commitments.
- Do NOT invent words that are not in the transcript.
- Do NOT use the phrase "the user".
"""

    human = f"""USER NAME: {user_name}
USER CONTEXT: {user_context or "None"}

TRANSCRIPT:
{transcript_block}
"""

    res = logic_rag.llm.invoke([SystemMessage(content=system), HumanMessage(content=human)])
    txt = res.content if hasattr(res, "content") else str(res)
    items = _extract_json_array(str(txt))
    out: list[dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        quote = str(it.get("quote") or "").strip()
        tag = str(it.get("guidepost_tag") or "").strip()
        speaker = str(it.get("speaker") or "").strip() or "Unknown"
        try:
            start_s = float(it.get("start_s"))
        except Exception:
            start_s = 0.0
        try:
            end_s = float(it.get("end_s"))
        except Exception:
            end_s = start_s
        if not quote or not tag:
            continue
        if len(quote) > 240:
            quote = quote[:237] + "..."
        out.append(
            {
                "speaker": speaker,
                "start_s": start_s,
                "end_s": end_s if end_s >= start_s else start_s,
                "quote": quote,
                "guidepost_tag": tag,
                "pattern": str(it.get("pattern") or "").strip(),
                "cbt_distortion": (str(it.get("cbt_distortion")).strip() if it.get("cbt_distortion") is not None else None),
                "confidence": float(it.get("confidence")) if isinstance(it.get("confidence"), (int, float)) else None,
            }
        )
    out.sort(key=lambda x: float(x.get("start_s") or 0.0))
    return out[:max_items]


def _index_transcript_insights(
    *,
    logic_rag: Any,
    audio_id: str,
    user_name: str,
    insights: list[dict[str, Any]],
) -> int:
    """Upsert transcript insights into Pinecone under a dedicated namespace."""
    ns = _insights_namespace()
    if not insights:
        return 0

    # Remove previous insights for this audio_id to avoid stale leftovers.
    try:
        logic_rag.index.delete(  # type: ignore[attr-defined]
            filter={"type": {"$eq": "transcript_insight"}, "audio_id": {"$eq": audio_id}, "user_name": {"$eq": user_name}},
            namespace=ns,
        )
    except Exception:
        pass

    texts: list[str] = []
    metas: list[dict[str, Any]] = []
    ids: list[str] = []

    for i, it in enumerate(insights):
        speaker = str(it.get("speaker") or "Unknown")
        start_s = float(it.get("start_s") or 0.0)
        end_s = float(it.get("end_s") or start_s)
        quote = str(it.get("quote") or "").strip()
        tag = str(it.get("guidepost_tag") or "").strip()
        if not quote or not tag:
            continue

        embed_text = (
            f'Highlight: "{quote}"\n'
            f"Guidepost Tag: {tag}\n"
            f"Speaker: {speaker}\n"
            f"Time: {start_s:0.2f}s–{end_s:0.2f}s\n"
            f"User: {user_name}"
        )
        texts.append(embed_text)

        digest = hashlib.sha1(f"{audio_id}:{i}".encode("utf-8")).hexdigest()[:16]
        ids.append(f"insight_{audio_id}_{digest}")

        metas.append(
            {
                "type": "transcript_insight",
                "audio_id": audio_id,
                "user_name": user_name,
                "speaker": speaker,
                "start_s": start_s,
                "end_s": end_s,
                "quote": quote,
                "guidepost_tag": tag,
                "pattern": str(it.get("pattern") or "").strip(),
                "cbt_distortion": it.get("cbt_distortion"),
            }
        )

    if not texts:
        return 0

    embeddings = logic_rag.embedding_model.encode(texts).tolist()  # type: ignore[attr-defined]
    vectors = []
    for vid, emb, meta in zip(ids, embeddings, metas):
        vectors.append({"id": vid, "values": emb, "metadata": meta})
    logic_rag.index.upsert(vectors=vectors, namespace=ns)  # type: ignore[attr-defined]
    return len(vectors)


def _retrieve_transcript_insights_for_chat(*, logic_rag: Any, user_name: str, query: str, top_k: int = 5) -> str:
    """Retrieve relevant transcript highlights for chat and format for prompt injection."""
    ns = _insights_namespace()
    q = (query or "").strip()
    if not q:
        return ""
    try:
        emb = logic_rag.embedding_model.encode(q).tolist()  # type: ignore[attr-defined]
        res = logic_rag.index.query(  # type: ignore[attr-defined]
            vector=emb,
            top_k=top_k,
            namespace=ns,
            include_metadata=True,
            filter={"type": {"$eq": "transcript_insight"}, "user_name": {"$eq": user_name}},
        )
        matches = getattr(res, "matches", None) or []
    except Exception:
        return ""

    lines: list[str] = []
    for m in matches:
        md = getattr(m, "metadata", None) or {}
        tag = str(md.get("guidepost_tag") or "").strip()
        speaker = str(md.get("speaker") or "Unknown")
        quote = str(md.get("quote") or "").strip()
        start_s = md.get("start_s")
        t = f"{float(start_s):0.2f}s" if isinstance(start_s, (int, float)) else "n/a"
        if quote and tag:
            lines.append(f'INSIGHT: [{speaker} @ {t}] "{quote}" — {tag}')
        elif tag:
            lines.append(f"INSIGHT: [{speaker} @ {t}] {tag}")
    return "\n".join(lines[:top_k]).strip()

def _process_audio_job(audio_id: str) -> None:
    """Background worker: diarize/transcribe an uploaded audio file.

    Flow:
    - Mark job as `processing`
    - Run diarization/transcription using `Diarize().diarize_audio(...)`
    - Optionally generate a coaching report from the diarized segments
    - Store results in-memory for polling + chat

    Why background:
    - Diarization can take long enough that you don't want to block the upload request.
    """
    try:
        _require_openai_key()
        diarizer = Diarize()

        job = _get_job(audio_id)
        audio_path = _materialize_audio_to_local(job)
        user_context = job.get("userContext")
        _set_job(audio_id, {"status": "processing"})

        target_name = str(job.get("targetName") or "target")
        target_ref = _materialize_voice_ref_to_local(job, target_name=target_name)

        if target_ref:
            diar = diarizer.diarize_target_vs_other(
                audio_path,
                target_name=target_name,
                target_reference_audio=str(target_ref),
                two_pass=False,
            )
        else:
            diar = diarizer.diarize_audio(audio_path)

        # Convert diarization segments into LangChain Documents for KG pipeline compatibility.
        try:
            from langchain_core.documents import Document  # type: ignore

            docs = []
            for s in diar.segments:
                text = str(s.get("text", "")).strip()
                if not text:
                    continue
                docs.append(
                    Document(
                        page_content=text,
                        metadata={
                            "speaker": str(s.get("speaker", "Unknown")),
                            "timestamp": str(s.get("start", "N/A")),
                            "source_type": "Diarization",
                        },
                    )
                )
        except Exception:
            docs = None

        _set_job(
            audio_id,
            {
                "status": "ready",
                "transcript": diar.text,
                "segments": diar.segments,
                # KG pipeline expects a list of Documents; keep segments separately for the API.
                "docs": docs,
                # Report is generated by calling the same logic as `/api/report`.
                "analysis": None,
            },
        )

        # IMPORTANT: Do NOT auto-generate a coaching report here.
        # This function runs after diarization/transcription and previously called
        # `create_report(...)`, which triggers the KG/Pinecone/PDF retrieval pipeline.
        # The report must be generated only on explicit user action (e.g. clicking
        # "Generate report" in the UI) via POST `/api/report`.

        # Precompute home summary so the dashboard can load instantly.
        try:
            precompute = str(os.getenv("HOME_SUMMARY_PRECOMPUTE_ON_UPLOAD", "1")).strip().lower() in (
                "1",
                "true",
                "yes",
            )
            if precompute:
                _schedule_home_summary_refresh(target_name=target_name)
        except Exception:
            pass
    except Exception as e:
        try:
            _set_job(audio_id, {"status": "error", "errorMessage": str(e)})
        except Exception:
            pass

def _persona_instructions(persona_style: str) -> str:
    """Map persona choice (1/2/3) to system-prompt tone instructions; default if unknown."""
    if "1" in persona_style:
        return "Be succinct and direct. Use minimal words."
    elif "2" in persona_style:
        return "Be empathetic and caring. Validate feelings and use warm language."
    elif "3" in persona_style:
        return "Be detailed and analytical. Provide structured, thoughtful responses."
    return "Be concise, warm, and professional."


app = FastAPI(title="Guidepost API", version="0.1.0")


@app.on_event("startup")
def ensure_db_tables():
    """Create DB tables (e.g. sessions, users) if they do not exist.  Best-effort: app works without Postgres."""
    try:
        Base.metadata.create_all(bind=engine)
        # Lightweight schema evolution for MVP: add new user profile columns if missing.
        from sqlalchemy import text

        ddl = [
            'ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "rankedSkills" TEXT',
            'ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "otherFocus" TEXT',
            'ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "voiceRecorded" BOOLEAN',
            'ALTER TABLE "sessions" ADD COLUMN IF NOT EXISTS "audio_id" TEXT',
        ]
        with engine.begin() as conn:
            for stmt in ddl:
                conn.execute(text(stmt))
    except Exception as e:
        logger.warning("Could not create/migrate DB tables (Postgres may not be running): %s", e)


app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """GET /health: lightweight liveness probe that avoids loading ML or RAG dependencies."""
    return {"ok": True}



@app.post("/api/audio", response_model=AudioUploadResponse)
async def upload_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    targetName: Optional[str] = Form(default=None),
    userContext: Optional[str] = Form(default=None),
    userEmail: Optional[str] = Form(default=None),
    userId: Optional[str] = Form(default=None),
    targetReferenceAudio: Optional[UploadFile] = File(default=None),
):
    """POST /api/audio: save uploaded audio (and optional voice reference), enqueue diarization, return `audioId` for polling."""
    audio_id = uuid.uuid4().hex
    safe_name = _safe_filename(file.filename or "audio")
    ext = Path(safe_name).suffix or ".bin"
    out_path = _AUDIO_DIR / f"{audio_id}{ext}"

    target_reference_path: Optional[str] = None
    target_reference_s3_key: Optional[str] = None
    transcript_text = ""
    all_docs = None
    audio_s3_key: Optional[str] = None

    try:
        contents = await file.read()
        if _s3_enabled():
            audio_s3_key = f"audio_uploads/{audio_id}{ext}"
            _s3_put_bytes(key=audio_s3_key, body=contents, content_type=file.content_type)
        else:
            out_path.write_bytes(contents)

        if targetReferenceAudio is not None:
            safe_target = _safe_filename(targetName or "target")
            safe_ref_name = _safe_filename(targetReferenceAudio.filename or "reference")
            ref_ext = Path(safe_ref_name).suffix or ".webm"
            ref_path = _VOICE_REF_DIR / f"{safe_target}-{audio_id}{ref_ext}"
            ref_bytes = await targetReferenceAudio.read()
            if _s3_enabled():
                target_reference_s3_key = f"voice_references/{safe_target}-{audio_id}{ref_ext}"
                _s3_put_bytes(
                    key=target_reference_s3_key,
                    body=ref_bytes,
                    content_type=targetReferenceAudio.content_type,
                )
            else:
                ref_path.write_bytes(ref_bytes)
                target_reference_path = str(ref_path)
            if targetName:
                with _LOCK:
                    if target_reference_path:
                        _VOICE_REFS[str(targetName)] = target_reference_path
                if _PERSIST_BACKEND == "db":
                    _db_put_voice_reference(
                        str(targetName),
                        s3_bucket=_S3_BUCKET if target_reference_s3_key else None,
                        s3_key=target_reference_s3_key,
                        local_path=target_reference_path,
                    )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to save upload: {e}") from e

    created = _now()
    job = {
        "status": "uploaded",
        "createdAt": created,
        "updatedAt": created,
        "path": None if audio_s3_key else str(out_path),
        "filename": safe_name,
        "transcript": transcript_text,
        "docs": all_docs,
        "segments": None,
        "analysis": None,
        "errorMessage": None,
        "userContext": userContext,
        "targetName": targetName,
        "userEmail": userEmail,
        "userId": userId,
        "audioS3Bucket": _S3_BUCKET if audio_s3_key else None,
        "audioS3Key": audio_s3_key,
        "targetReferencePath": target_reference_path,
        "targetReferenceS3Bucket": _S3_BUCKET if target_reference_s3_key else None,
        "targetReferenceS3Key": target_reference_s3_key,
    }
    _put_job(audio_id, job)

    # IMPORTANT: do not rely on FastAPI BackgroundTasks here.
    # If the client navigates away mid-upload or the connection closes before the
    # response fully completes, BackgroundTasks may never run.
    # Starting a daemon thread ensures processing continues once the file is saved.
    try:
        t = threading.Thread(target=_process_audio_job, args=(audio_id,), daemon=True)
        t.start()
    except Exception:
        # Fall back to BackgroundTasks if thread start fails for some reason.
        background_tasks.add_task(_process_audio_job, audio_id)
    return AudioUploadResponse(audioId=audio_id)


@app.post("/api/voice_reference")
async def upload_voice_reference(
    targetName: str = Form(...),
    file: UploadFile = File(...),
):
    """POST /api/voice_reference: persist a speaker sample for `targetName` so future uploads can diarize against it."""
    ref_id = uuid.uuid4().hex
    safe_target = _safe_filename(targetName)
    safe_ref_name = _safe_filename(file.filename or "reference")
    ext = Path(safe_ref_name).suffix or ".webm"
    out_path = _VOICE_REF_DIR / f"{safe_target}-{ref_id}{ext}"
    try:
        body = await file.read()
        if _s3_enabled():
            key = f"voice_references/{safe_target}-{ref_id}{ext}"
            _s3_put_bytes(key=key, body=body, content_type=file.content_type)
            if _PERSIST_BACKEND == "db":
                _db_put_voice_reference(targetName, s3_bucket=_S3_BUCKET, s3_key=key, local_path=None)
        else:
            out_path.write_bytes(body)
            if _PERSIST_BACKEND == "db":
                _db_put_voice_reference(targetName, s3_bucket=None, s3_key=None, local_path=str(out_path))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to save voice reference: {e}") from e

    if not _s3_enabled():
        with _LOCK:
            _VOICE_REFS[targetName] = str(out_path)

    return {"ok": True, "targetName": targetName}


@app.get("/api/audio/{audio_id}", response_model=AudioJobResponse)
def get_audio_status(audio_id: str):
    """GET /api/audio/{audio_id}: poll job status; omits full transcript/analysis in the response shape."""
    job = _get_job(audio_id)
    return _job_to_response(audio_id, job)


@app.post("/api/report", response_model=ReportResponse)
def create_report(req: ReportRequest):
    """POST /api/report: generate and persist a coaching report for a ready audio job.
    Uses KG plus PDF retrieval and LogicRAG history when configured; otherwise falls back gracefully."""
    job = _get_job(req.audioId)
    if job["status"] != "ready":
        raise HTTPException(status_code=409, detail="Audio is not ready yet")


    # Chat History
    current_chat_text = "No current chat history."
    if req.conversationId:
        with _LOCK:
            raw_history = _CONVERSATIONS.get(req.conversationId, [])
            if raw_history:
                formatted_lines = []
                for turn in raw_history:
                    role = "User" if turn["role"] == "user" else "Coach AI"
                    formatted_lines.append(f"{role}: {turn['content']}")
                current_chat_text = "\n".join(formatted_lines)

    user_context = (req.userContext or job.get("userContext") or "").strip()
    target_name = (req.targetName or job.get("targetName") or "User").strip() or "User"
    aligned_focus = (req.alignedFocus or job.get("alignedFocus") or "").strip()
    if aligned_focus:
        user_context = (
            f"USER SELF-ASSESSMENT (what {target_name} believes happened — use this as "
            f"a baseline to contrast against what the transcript actually shows): "
            f"{aligned_focus}\n\n"
            f"Additional user context: {user_context or 'None'}"
        )

    docs = job.get("docs")
    segments = job.get("segments") or []

    # If docs are missing but we have diarization segments, convert to Documents for KG compatibility.
    if not docs and segments:
        try:
            from langchain_core.documents import Document  # type: ignore

            docs = [
                Document(
                    page_content=str(s.get("text", "")).strip(),
                    metadata={
                        "speaker": str(s.get("speaker", "Unknown")),
                        "timestamp": str(s.get("start", "N/A")),
                        "source_type": "Diarization",
                    },
                )
                for s in segments
                if str(s.get("text", "")).strip()
            ]
        except Exception:
            docs = None

    report_stage_1: str = ""
    retrieved_context = "No additional scientific context retrieved."

    # Step 1-2: KG diagnostic + retrieval (best effort)
    try:
        KGRAG = _lazy_import_kgrag()
        #print("In KGRAG:CLOUD_NEO4J_URI :",CLOUD_NEO4J_URI)
        #print("In CLOUD_NEO4J_USERNAME :",CLOUD_NEO4J_USERNAME)
        #print("In CLOUD_NEO4J_PASSWORD :",CLOUD_NEO4J_PASSWORD)
       # print("In PINECONE_INDEX_NAME :",PINECONE_INDEX_NAME)
        #print("In HF_EMBED_MODEL :",HF_EMBED_MODEL)
        #print("KGRAG starting ")
        rag = KGRAG(
            index_name=PINECONE_INDEX_NAME,
            embedding_model_name=HF_EMBED_MODEL,
            neo4j_uri=CLOUD_NEO4J_URI,
            neo4j_user=CLOUD_NEO4J_USERNAME,
            neo4j_password=CLOUD_NEO4J_PASSWORD,
        )
        #print("KGRAG initialized")
        logger.info("retrieved KG RAGQuery :")
        try:
            if docs:
                
                opening, middle, closing = rag.get_strategic_segments(docs, window_size=15)

                logger.info("Computed strategic segments for report (opening/middle/closing).")
                report_stage_1 = rag.run_trend_analysis(
                    opening, middle, closing, segments, user_input=user_context or "None"
                )
                logger.info("Generated stage-1 report (chars=%d).", len(report_stage_1 or ""))
                try:
                    search_queries = rag._extract_queries(report_stage_1)  # type: ignore[attr-defined]
                    logger.info("Extracted %d retrieval query(ies) from stage-1 report.", len(search_queries or []))

                except Exception:
                    search_queries = []
                if search_queries:
                    retrieved_context = rag.get_pdf_knowledge_optimised(queries=search_queries)

                    logger.info("Retrieved additional context (chars=%d).", len(retrieved_context or ""))

            elif segments:
                logger.info("segments are not None")
                report_stage_1 = _generate_report_from_segments(
                    audio_id=req.audioId, segments=segments, user_context=user_context
                )
                logger.info("Generated stage-1 report from segments (chars=%d).", len(report_stage_1 or ""))
            else:
                report_stage_1 = "(no transcript available)"
                logger.info("No transcript available; generated placeholder stage-1 report.")

        finally:
            try:
                rag.close()
                logger.info("rag.close() is called")
            except Exception:
                pass
    except Exception as e:
        # If KG cannot initialize, fall back to the lightweight report generator.
        logger.error("KG PIPELINE FAILED: %s", e)
        if segments:
            logger.info("segments are not None")
            report_stage_1 = _generate_report_from_segments(
                audio_id=req.audioId, segments=segments, user_context=user_context
            )
        else:
            raise HTTPException(status_code=500, detail="Report generation failed: missing transcript/segments")

    # Prepare evidence-backed transcript highlights for synthesis + indexing (best effort).
    insights: list[dict[str, Any]] = []
    insights_block = ""
    try:
        if segments:
            logic_rag_tmp = _get_logic_rag()
            logic_rag_tmp.current_user_name = target_name
            insights = _compute_transcript_highlights_and_tags(
                logic_rag=logic_rag_tmp,
                user_name=target_name,
                user_context=user_context or "",
                segments=segments,
                max_items=int(os.getenv("TRANSCRIPT_INSIGHTS_MAX_ITEMS", "8")),
            )
            if insights:
                lines = []
                for it in insights:
                    speaker = str(it.get("speaker") or "Unknown")
                    start_s = float(it.get("start_s") or 0.0)
                    quote = str(it.get("quote") or "").strip()
                    tag = str(it.get("guidepost_tag") or "").strip()
                    if quote and tag:
                        lines.append(f'- [{speaker} @ {start_s:0.2f}s] \"{quote}\" — {tag}')
                insights_block = "\n".join(lines)[:2500]
    except Exception:
        insights = []
        insights_block = ""

    # Step 3-5: History-aware synthesis & memory (best effort)
    final_strategy = report_stage_1
    try:
        logic_rag = _get_logic_rag()
        logic_rag.current_user_name = target_name

        past_matches = logic_rag.retrieve_context(
            query=f"Coaching history for {target_name}",
            top_k=5,
            namespace=getattr(logic_rag, "mem_namespace", None),
        )
        past_history_text = (
            "\n---\n".join([getattr(m, "metadata", {}).get("text", "") for m in past_matches])
            if past_matches
            else "No history found."
        )

        final_strategy = logic_rag.execute_final_synthesis(
            current_report=report_stage_1,
            past_history_text=past_history_text,
            pdf_context_text=retrieved_context,
            current_chat_history=current_chat_text,
            transcript_insights=insights_block or "No transcript highlights available.",
            user_name=target_name,
        )

        # print("final_strategy from logic_rag is: ", final_strategy)

        try:
            logic_rag.save_to_memory(report=report_stage_1, final_strategy=final_strategy)
        except Exception:
            pass
    except Exception as e:
        # If LogicRAG fails (e.g. Cohere timeout, Pinecone), return stage-1 only; log so we can debug.
        logger.warning(
            "LogicRAG final synthesis skipped (report will be stage-1 only): %s",
            e,
            exc_info=True,
        )
        final_strategy = report_stage_1

    try:
        _set_job(
            req.audioId,
            {
                "analysis": final_strategy,
                "finalStrategy": final_strategy,
                "report_stage_1": report_stage_1,
                "retrieved_context": retrieved_context,
            },
        )
    except Exception:
        pass

    # Index transcript highlights + Guidepost tags into Pinecone (best effort).
    # This is used later to surface evidence-backed "highlight + tag" snippets in chat.
    try:
        if segments and insights:
            logic_rag = _get_logic_rag()
            logic_rag.current_user_name = target_name
            upserted = _index_transcript_insights(
                logic_rag=logic_rag,
                audio_id=req.audioId,
                user_name=target_name,
                insights=insights,
            )
            logger.info("Indexed %d transcript insight(s) to Pinecone namespace=%r.", upserted, _insights_namespace())
    except Exception as e:
        logger.warning("Transcript insight indexing skipped: %s", e)

    # Persist CRI/CEI to Postgres sessions for dashboarding (best effort).
    try:
        cri_match = re.search(r"CRI[^0-9]*([0-9]+(?:\.[0-9]+)?)", final_strategy, re.IGNORECASE)
        cei_match = re.search(r"CEI[^0-9]*([0-9]+(?:\.[0-9]+)?)", final_strategy, re.IGNORECASE)
        cri_val = float(cri_match.group(1)) if cri_match else None
        cei_val = float(cei_match.group(1)) if cei_match else None

        # Clamp to 1-5 as requested.
        if cri_val is not None:
            cri_val = max(1.0, min(5.0, cri_val))
        if cei_val is not None:
            cei_val = max(1.0, min(5.0, cei_val))

        job_user_id = job.get("userId")
        job_user_email = (job.get("userEmail") or "").strip().lower()

        resolved_user_id = None
        if job_user_id:
            try:
                resolved_user_id = uuid.UUID(str(job_user_id))
            except Exception:
                resolved_user_id = None
        if not resolved_user_id and job_user_email:
            with SessionLocal() as db:
                u = db.query(DbUser).filter(DbUser.email == job_user_email).first()
                resolved_user_id = getattr(u, "id", None) if u else None

        if resolved_user_id and cri_val is not None and cei_val is not None:
            from src.save_session import create_session_data

            # Avoid duplicate rows for the same audio_id if /api/report is called twice.
            with SessionLocal() as db:
                existing = (
                    db.query(DbSession)
                    .filter(DbSession.user_id == resolved_user_id, DbSession.audio_id == req.audioId)
                    .first()
                )
                if not existing:
                    create_session_data(resolved_user_id, job.get("transcript") or "", cri_val, cei_val, audio_id=req.audioId)
    except Exception:
        pass

    return ReportResponse(report=final_strategy, finalStrategy=final_strategy)
    



_ALIGNED_FOCUS_MARKER = "ALIGNED_FOCUS:"


def _build_alignment_system_prompt(
    target_name: str, context: str, transcript: str, personaStyle: str,
) -> str:
    """System prompt for the alignment phase: gather self-assessment before coaching analysis."""
    transcript_for_prompt = transcript[:12000]
    if len(transcript) > 12000:
        transcript_for_prompt += "\n\n(Transcript truncated for context window.)"

    return f"""
COMMUNICATION STYLE:
{personaStyle}
You are a warm professional development coach. You are in a CONTEXT-GATHERING phase \
— your job is to understand the situation and capture {target_name}'s self-perception \
before the system runs its own independent analysis.

PURPOSE:
The system will analyze this conversation for blind spots — patterns {target_name} \
uses without realizing it. To do that well, we need to know what {target_name} \
*thinks* happened. The gap between self-perception and what the transcript reveals \
is where the most valuable insights live.

RULES:
- On your FIRST turn: ask {target_name} two things in a warm, conversational way: \
(1) what was the goal of this conversation, and (2) how they feel it went. Keep it \
to 2-3 sentences total. Do NOT analyze the transcript yet.
- On SUBSEQUENT turns: listen and ask ONE short follow-up that deepens your \
understanding of their perspective. Good follow-ups: "What made you feel that way?" \
or "Was there a moment that stood out to you?" Do NOT offer observations from the \
transcript — just listen.
- After 2-3 exchanges (or sooner if {target_name} gives clear answers), summarize \
what you heard on its own line in exactly this format:
  {_ALIGNED_FOCUS_MARKER} <one sentence capturing {target_name}'s self-assessment — what they believe the conversation was about and how they think it went>
- After the {_ALIGNED_FOCUS_MARKER} line, transition warmly: "Thanks for sharing that. \
Let me take a closer look at the conversation and put together some insights for you."
- Keep every response to 2-4 sentences. Be curious, not analytical.
- Do NOT give advice, identify patterns, or reference specific transcript moments \
during this phase. Save that for coaching.

User name: {target_name}
User's stated concern: {context or "None provided"}

Transcript (available to you for reference, but do NOT analyze or quote it during this phase):
{transcript_for_prompt}
"""


def _build_coaching_system_prompt(
    target_name: str, context: str, transcript: str, analysis: str,
    aligned_focus: str, personaStyle: str,
    retrieved_highlights: str = "",
) -> str:
    """System prompt for coaching: blind-spot feedback using transcript, report, and optional RAG highlights."""
    transcript_for_prompt = transcript[:12000]
    if len(transcript) > 12000:
        transcript_for_prompt += "\n\n(Transcript truncated for context window.)"
    analysis_for_prompt = analysis[:8000]
    if len(analysis) > 8000:
        analysis_for_prompt += "\n\n(Analysis truncated for context window.)"

    highlights_block = ""
    if (retrieved_highlights or "").strip():
        highlights_block = (
            "\nGuidepost transcript highlights (evidence from the conversation):\n"
            f"{retrieved_highlights.strip()}\n"
        )

    return f"""
COMMUNICATION STYLE:
{personaStyle}
You are a warm but incisive communication coach. Your job is to help \
{target_name} see patterns in their own communication that they cannot see themselves.

CORE PRINCIPLE:
{target_name} told you how they think the conversation went (see "Self-assessment" below). \
Your most valuable insights will come from the gap between that self-perception and what \
the transcript actually shows. When {target_name} says "it went fine" but the transcript \
shows hedge language or avoidance, that gap IS the blind spot.

RESPONSE RULES:
- When {target_name} makes a claim about the other person (e.g., "they have poor \
communication skills"), gently redirect: what in {target_name}'s OWN language or \
behavior might be contributing? Quote a specific moment from the transcript to ground it.
- When {target_name} asks how to fix someone else, reframe around what {target_name} \
can control: their own phrasing, tone, or approach. Use a brief transcript quote to \
show the pattern.
- Name the psychological concept when relevant (CBT distortions, NVC, Ladder of \
Inference, Gottman, etc.) and explain it in one plain sentence. Do not assume \
{target_name} knows these frameworks.
- Keep responses to 2-4 sentences unless {target_name} asks for more detail.
- End with exactly ONE follow-up question that probes deeper into {target_name}'s \
own behavior or assumptions — not the other person's.
- Write naturally. No headers, no bullet lists, no markdown.
- If {target_name} asks a broad question, pick the single most important blind-spot \
pattern and go deep. Do not enumerate multiple points.

User name: {target_name}
Self-assessment (what {target_name} believes happened): {aligned_focus or "No self-assessment captured yet."}
User's stated concern: {context or "None provided"}

Evidence available to you (reference as needed, do NOT dump):
- Transcript: {transcript_for_prompt}
- Prior analysis: {analysis_for_prompt}
{highlights_block}
"""


def _extract_aligned_focus(reply: str) -> Optional[str]:
    """Parse the ALIGNED_FOCUS: marker from an LLM reply, if present."""
    if _ALIGNED_FOCUS_MARKER not in reply:
        return None
    after_marker = reply.split(_ALIGNED_FOCUS_MARKER, 1)[1]
    focus = after_marker.strip().split("\n")[0].strip()
    return focus if focus else None


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """POST /api/chat: run alignment or coaching turn for a ready audio job, persist history, and return the reply."""

    job = _get_job(req.audioId)
    if job["status"] != "ready":
        raise HTTPException(status_code=409, detail="Audio is not ready yet")

    transcript = job.get("transcript") or ""
    analysis = job.get("analysis") or ""
    context = (req.userContext or job.get("userContext") or "").strip()
    target_name = (req.targetName or job.get("targetName") or "User").strip() or "User"
    aligned_focus = job.get("alignedFocus") or ""
    personaStyle = job.get("personaStyle")
    if personaStyle is not None:
        print("Current Persona: " + personaStyle)
    # Default to alignment immediately after upload until an aligned focus is set.
    phase = req.phase or ("alignment" if not aligned_focus else "coaching")

    conversation_id = req.conversationId or uuid.uuid4().hex
    history: list[dict[str, str]] = []
    with _LOCK:
        if conversation_id in _CONVERSATIONS:
            history = list(_CONVERSATIONS.get(conversation_id) or [])
    if not history and req.conversationId:
        if _PERSIST_BACKEND == "db":
            db_history = _db_get_chat_conversation(conversation_id, audio_id=req.audioId)
            if db_history is not None:
                with _LOCK:
                    _CONVERSATIONS[conversation_id] = db_history
                history = list(db_history)
        else:
            disk_history = _load_chat_conversation(conversation_id, audio_id=req.audioId)
            if disk_history is not None:
                with _LOCK:
                    _CONVERSATIONS[conversation_id] = disk_history
                history = list(disk_history)

    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage  # type: ignore

    #Persona
    if phase == "alignment" and not personaStyle:
        user_input = req.message.strip()

        # If user just picked persona
        if user_input in ["1", "2", "3"]:
            personaStyle = _persona_instructions(user_input)

            with _LOCK:
                if req.audioId in _AUDIO_JOBS:
                    _AUDIO_JOBS[req.audioId]["personaStyle"] = personaStyle

        else:
            # Force persona selection (DO NOT CALL LLM)
            return ChatResponse(
                reply=
"""Before we start, how would you like me to communicate?

Choose one:
1) Succinct & direct — quick and to the point  
2) Empathetic & caring — supportive and understanding  
3) Detailed & analytical — thorough and structured 

Just reply with 1, 2, or 3.""",
            conversationId=conversation_id,
            phase=phase,
            alignedFocus=None,
        )

    if phase == "alignment":
        system = _build_alignment_system_prompt(target_name, context, transcript, personaStyle)
    else:
        retrieved_highlights = ""
        try:
            logic_rag = _get_logic_rag()
            logic_rag.current_user_name = target_name
            retrieved_highlights = _retrieve_transcript_insights_for_chat(
                logic_rag=logic_rag, user_name=target_name, query=req.message, top_k=5
            )
        except Exception:
            retrieved_highlights = ""

        system = _build_coaching_system_prompt(
            target_name, context, transcript, analysis, aligned_focus, personaStyle, retrieved_highlights
        )

    messages: list[Any] = [SystemMessage(content=system)]
    for m in history[-12:]:
        if m["role"] == "user":
            messages.append(HumanMessage(content=m["content"]))
        else:
            messages.append(AIMessage(content=m["content"]))
    messages.append(HumanMessage(content=req.message))

    try:
        logic_rag = _get_logic_rag()
        logic_rag.current_user_name = target_name
        res = logic_rag.llm.invoke(messages)
        reply = res.content if hasattr(res, "content") else str(res)
    except Exception:
        oa_messages: list[dict[str, str]] = []
        for m in history[-12:]:
            role = "user" if m["role"] == "user" else "assistant"
            oa_messages.append({"role": role, "content": m["content"]})
        oa_messages.append({"role": "user", "content": req.message})
        try:
            reply = _openai_chat(system=system, messages=oa_messages)
        except Exception as e2:
            raise HTTPException(status_code=500, detail=f"Chat failed: {e2}") from e2

    convo_snapshot: Optional[list[dict[str, str]]] = None
    with _LOCK:
        _CONVERSATIONS.setdefault(conversation_id, []).extend(
            [{"role": "user", "content": req.message}, {"role": "assistant", "content": reply}]
        )
        convo_snapshot = list(_CONVERSATIONS.get(conversation_id) or [])
    if convo_snapshot is not None:
        if _PERSIST_BACKEND == "db":
            _db_put_chat_conversation(conversation_id, audio_id=req.audioId, messages=convo_snapshot)
        else:
            _persist_chat_conversation(conversation_id, audio_id=req.audioId, messages=convo_snapshot)

    response_phase = phase
    response_aligned_focus: Optional[str] = None

    if phase == "alignment":
        parsed_focus = _extract_aligned_focus(reply)
        if parsed_focus:
            response_aligned_focus = parsed_focus
            response_phase = "coaching"
            try:
                _set_job(req.audioId, {"alignedFocus": parsed_focus})
            except Exception:
                pass

    return ChatResponse(
        reply=reply,
        conversationId=conversation_id,
        phase=response_phase,
        alignedFocus=response_aligned_focus,
    )


def _home_summary_disk_path(*, target_name: str) -> Path:
    """Stable JSON path for cached home summary text (disk persistence backend)."""
    safe = _safe_filename((target_name or "").strip().lower() or "user")
    return _HOME_SUMMARY_DIR / f"{safe}.json"


def _disk_get_home_summary(*, target_name: str) -> Optional[dict[str, Any]]:
    """Read cached summary payload from disk, or None if missing or invalid."""
    try:
        p = _home_summary_disk_path(target_name=target_name)
        if not p.exists():
            return None
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else None
    except Exception:
        return None


def _disk_put_home_summary(
    *,
    target_name: str,
    summary: str,
    source_updated_at: Optional[str],
) -> None:
    """Write summary text and metadata timestamps to the user's home-summary JSON file."""
    try:
        payload = {
            "targetName": (target_name or "").strip(),
            "summary": (summary or "").strip(),
            "computedAt": _now(),
            "sourceUpdatedAt": (source_updated_at or "").strip(),
        }
        _home_summary_disk_path(target_name=target_name).write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def _db_get_home_summary(*, target_name: str) -> Optional[dict[str, Any]]:
    """Load cached home summary row for `target_name` from Postgres."""
    try:
        with SessionLocal() as db:
            row = db.query(DbHomeSummary).filter(DbHomeSummary.target_name == target_name).first()
            if not row:
                return None
            return {
                "targetName": str(getattr(row, "target_name", "") or ""),
                "summary": str(getattr(row, "summary", "") or ""),
                "computedAt": getattr(row, "computed_at", None).timestamp() if getattr(row, "computed_at", None) else None,
                "sourceUpdatedAt": str(getattr(row, "source_updated_at", "") or ""),
            }
    except Exception:
        return None


def _db_put_home_summary(
    *,
    target_name: str,
    summary: str,
    source_updated_at: Optional[str],
) -> None:
    """Upsert home summary text and source timestamp in `home_summaries` (best-effort)."""
    try:
        with SessionLocal() as db:
            row = db.query(DbHomeSummary).filter(DbHomeSummary.target_name == target_name).first()
            if not row:
                row = DbHomeSummary(target_name=target_name)
                db.add(row)
            row.summary = (summary or "").strip()
            row.source_updated_at = (source_updated_at or "").strip()
            db.commit()
    except Exception:
        pass


def _get_cached_home_summary(*, target_name: str) -> Optional[dict[str, Any]]:
    """Read home summary from the active backend (db vs disk) for fast dashboard responses."""
    if not (target_name or "").strip():
        return None
    if _PERSIST_BACKEND == "db":
        return _db_get_home_summary(target_name=target_name)
    return _disk_get_home_summary(target_name=target_name)


def _put_cached_home_summary(*, target_name: str, summary: str, source_updated_at: Optional[str]) -> None:
    """Persist a freshly computed summary through the same backend as `_get_cached_home_summary`."""
    if not (target_name or "").strip():
        return
    if _PERSIST_BACKEND == "db":
        _db_put_home_summary(target_name=target_name, summary=summary, source_updated_at=source_updated_at)
    else:
        _disk_put_home_summary(target_name=target_name, summary=summary, source_updated_at=source_updated_at)


def _is_home_summary_fresh(cached: dict[str, Any]) -> bool:
    """True if `computedAt` is within the configured TTL (avoids blocking on every dashboard load)."""
    try:
        computed_at = float(cached.get("computedAt") or 0.0)
    except Exception:
        computed_at = 0.0
    if not computed_at:
        return False
    return (_now() - computed_at) <= _HOME_SUMMARY_TTL_S


def _get_recent_transcripts_for_user(
    *,
    target_name: str,
    limit: int = 8,
    max_chars_per_transcript: int = 2200,
) -> list[dict[str, Any]]:
    """Return recent uploaded transcripts for a user (best effort).

    We key by `target_name` because the UI uploads audio with `targetName=userName`.
    Source of truth depends on persistence backend:
    - db: query `audio_jobs` table
    - disk: scan recent job JSON files under `_AUDIO_JOB_DIR`
    """
    target_norm = (target_name or "").strip()
    if not target_norm:
        return []

    out: list[dict[str, Any]] = []

    if _PERSIST_BACKEND == "db":
        try:
            with SessionLocal() as db:
                rows = (
                    db.query(DbAudioJob)
                    .filter(
                        func.lower(DbAudioJob.target_name) == target_norm.lower(),
                        DbAudioJob.status == "ready",
                    )
                    .order_by(DbAudioJob.updated_at.desc())
                    .limit(int(limit))
                    .all()
                )
                for r in rows:
                    t = (getattr(r, "transcript", None) or "").strip()
                    if not t:
                        continue
                    out.append(
                        {
                            "audioId": str(getattr(r, "audio_id", "") or ""),
                            "updatedAt": str(getattr(r, "updated_at", "") or ""),
                            "alignedFocus": (getattr(r, "aligned_focus", None) or "").strip(),
                            "userContext": (getattr(r, "user_context", None) or "").strip(),
                            "transcript": t[:max_chars_per_transcript],
                        }
                    )
        except Exception:
            return []
        return out

    # disk mode: scan most recent job files by mtime (bounded)
    max_scan = int(os.getenv("HOME_SUMMARY_MAX_DISK_SCAN", "200"))
    try:
        candidates = list(_AUDIO_JOB_DIR.glob("*.json"))
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        if max_scan > 0:
            candidates = candidates[:max_scan]
        for p in candidates:
            if len(out) >= int(limit):
                break
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(raw, dict):
                continue
            if str(raw.get("status") or "") != "ready":
                continue
            if str(raw.get("targetName") or "").strip().lower() != target_norm.lower():
                continue
            t = str(raw.get("transcript") or "").strip()
            if not t:
                continue
            out.append(
                {
                    "audioId": str(p.stem),
                    "updatedAt": str(raw.get("updatedAt") or ""),
                    "alignedFocus": str(raw.get("alignedFocus") or "").strip(),
                    "userContext": str(raw.get("userContext") or "").strip(),
                    "transcript": t[:max_chars_per_transcript],
                }
            )
    except Exception:
        return []

    return out


def _schedule_home_summary_refresh(*, target_name: str) -> None:
    """Debounced background refresh to keep dashboard fast."""
    name = (target_name or "").strip()
    if not name:
        return
    with _LOCK:
        t = _HOME_SUMMARY_TIMERS.get(name)
        if t is not None:
            try:
                t.cancel()
            except Exception:
                pass
        timer = threading.Timer(_HOME_SUMMARY_REFRESH_DEBOUNCE_S, lambda: _refresh_home_summary(target_name=name))
        timer.daemon = True
        _HOME_SUMMARY_TIMERS[name] = timer
        timer.start()


def _refresh_home_summary(*, target_name: str) -> None:
    """Compute + persist home summary. Runs in background; never raises."""
    try:
        summary_text, source_updated_at = _compute_home_summary(
            userName=target_name, conversationId=None, current_chat_text=""
        )
        if summary_text:
            _put_cached_home_summary(target_name=target_name, summary=summary_text, source_updated_at=source_updated_at)
    except Exception:
        return


def _compute_home_summary(
    *,
    userName: str,
    conversationId: Optional[str],
    current_chat_text: str,
) -> tuple[str, Optional[str]]:
    """Synthesize a dashboard paragraph from recent transcripts (and optional history); returns summary plus source hint."""
    logic_rag = _get_logic_rag()
    logic_rag.current_user_name = userName

    # Pull recent uploaded transcripts so the model can detect patterns across conversations.
    # Keep this smaller to reduce prompt size + latency.
    transcript_limit = int(os.getenv("HOME_SUMMARY_TRANSCRIPT_LIMIT", "8"))
    recent_transcripts = _get_recent_transcripts_for_user(target_name=userName, limit=transcript_limit)

    transcripts_block = ""
    newest_source_updated_at: Optional[str] = None
    if isinstance(recent_transcripts, list) and recent_transcripts:
        blocks: list[str] = []
        for i, r in enumerate(recent_transcripts, start=1):
            meta = []
            if r.get("updatedAt"):
                meta.append(f"updatedAt={r['updatedAt']}")
                if newest_source_updated_at is None:
                    newest_source_updated_at = str(r["updatedAt"])
            if r.get("audioId"):
                meta.append(f"audioId={r['audioId']}")
            if r.get("alignedFocus"):
                meta.append(f"alignedFocus={r['alignedFocus']}")
            if r.get("userContext"):
                meta.append(f"userContext={r['userContext']}")
            header = f"[Conversation {i}] " + (" | ".join(meta) if meta else "")
            blocks.append(f"{header}\n{r.get('transcript','')}")
        transcripts_block = "\n\n---\n\n".join(blocks)[:12000]

    # Optional: Past reports via vector store can be slow; default off for dashboard performance.
    include_past = str(os.getenv("HOME_SUMMARY_INCLUDE_PAST_REPORTS", "0")).strip().lower() in ("1", "true", "yes")
    past_reports_text = ""
    if include_past:
        try:
            past_matches = logic_rag.retrieve_context(
                query=f"Full performance history and behavioral reports for {userName}",
                top_k=6,
                namespace=getattr(logic_rag, "mem_namespace", None),
            )
            past_reports_text = "\n---\n".join(
                [getattr(m, "metadata", {}).get("text", "") for m in (past_matches or [])]
            )[:6000]
        except Exception:
            past_reports_text = ""

    if not past_reports_text and not transcripts_block and not (current_chat_text or "").strip():
        return (f"Hey {userName}, great to see you! Start by uploading your first audio conversation to get started.", None)

    def _name_possessive(name: str) -> str:
        """Return a simple possessive form for `name` (used when rewriting generic 'the user' phrasing)."""
        n = (name or "").strip()
        if not n:
            return "your"
        return f"{n}'" if n[-1].lower() == "s" else f"{n}'s"

    def _personalize_home_summary(text: str, *, name: str) -> str:
        """Ensure summary refers to the user by name (or 'you'), not 'the user'."""
        t = (text or "").strip()
        if not t or not (name or "").strip():
            return t
        nm = (name or "").strip()
        # Replace common generic phrasing.
        t = re.sub(r"\b[Tt]he user's\b", _name_possessive(nm), t)
        t = re.sub(r"\b[Tt]he user\b", nm, t)
        return t

    summary_prompt = f"""
    [ROLE] 
    You are a warm, tech-savvy, and slightly witty Personal Performance Coach. 
    You are synthesizing the progress of the user across the various audio files they upload.

    [SOURCE 0: RECENT UPLOADED CONVERSATION TRANSCRIPTS (MOST RECENT FIRST)]
    {transcripts_block or "No transcripts available."}

    [SOURCE 1: HISTORICAL REPORTS (MAY BE EMPTY)]
    {past_reports_text or "No historical reports available."}

    [SOURCE 2: CURRENT LIVE CHAT HISTORY (MAY BE EMPTY)]
    {current_chat_text or "No current chat history."}

    [TASK]
    Write a single, cohesive paragraph (60-80 words) summarizing the user's status. Your goal is to 
    identify underlying communication patterns, perspectives, and behaviors that
    the user engages in across conversations. Use the transcripts as the primary evidence when available.
    As you uncover these patterns, highlight them and explain how they impact the user's communication.

    [STRICT GUIDELINES]
    1. **The Content**: 
       - Analyze patterns across multiple conversations and report on the user's communication patterns, perspectives, and behaviors.
       - Mention 1-2 concrete examples (short quotes) only if the transcript contains them clearly.
    2. **The Vibe**: Human-centric, professional but not overly formal.
    3. **Constraint**: NO bullet points. NO "In summary" or "Based on...". Just one natural paragraph. 60-80 words total.
    4. **Naming**: Refer to the person as "{userName}" or "you". Do NOT write "the user".

    [LANGUAGE] English.
    """

    res = logic_rag.llm.invoke(summary_prompt)
    summary_result = res.content if hasattr(res, "content") else str(res)
    final_text = _personalize_home_summary(str(summary_result or ""), name=userName)
    return (final_text.strip(), newest_source_updated_at)


@app.get("/api/home-summary", response_model=YTDSummaryResponse)
async def get_home_summary(userName: str, conversationId: Optional[str] = None):
    """GET /api/home-summary: return a short dashboard blurb, using cache when possible and optional live chat context."""
    current_chat_text = ""
    
    if conversationId:
        raw_history: list[dict[str, str]] = []
        with _LOCK:
            raw_history = list(_CONVERSATIONS.get(conversationId, []) or [])

        # If the container restarted (ECS/Fargate), conversation history may only exist in persistence.
        if not raw_history:
            try:
                if _PERSIST_BACKEND == "db":
                    with SessionLocal() as db:
                        row = (
                            db.query(DbChatConversation)
                            .filter(DbChatConversation.conversation_id == conversationId)
                            .first()
                        )
                        if row and getattr(row, "messages_json", None):
                            msgs = json.loads(row.messages_json)
                            if isinstance(msgs, list):
                                raw_history = [
                                    {"role": str(m.get("role") or ""), "content": str(m.get("content") or "")}
                                    for m in msgs
                                    if isinstance(m, dict) and str(m.get("role") or "") in ("user", "assistant")
                                ]
                else:
                    p = _chat_convo_disk_path(conversationId)
                    if p.exists():
                        raw = json.loads(p.read_text(encoding="utf-8"))
                        msgs = raw.get("messages") if isinstance(raw, dict) else None
                        if isinstance(msgs, list):
                            raw_history = [
                                {"role": str(m.get("role") or ""), "content": str(m.get("content") or "")}
                                for m in msgs
                                if isinstance(m, dict) and str(m.get("role") or "") in ("user", "assistant")
                            ]
            except Exception:
                raw_history = []

        if raw_history:
            formatted_lines = [
                f"{'User' if t.get('role') == 'user' else 'Coach AI'}: {t.get('content') or ''}"
                for t in raw_history
            ]
            current_chat_text = "\n".join(formatted_lines)

    try:
        # Fast path for dashboard: serve cached summary if available.
        # If stale, return cached immediately and refresh in background.
        if not conversationId:
            cached = _get_cached_home_summary(target_name=userName)
            if cached and str(cached.get("summary") or "").strip():
                if not _is_home_summary_fresh(cached):
                    _schedule_home_summary_refresh(target_name=userName)
                return YTDSummaryResponse(summary=str(cached.get("summary") or "").strip())

        summary_text, source_updated_at = _compute_home_summary(
            userName=userName, conversationId=conversationId, current_chat_text=current_chat_text
        )
        if summary_text:
            _put_cached_home_summary(target_name=userName, summary=summary_text, source_updated_at=source_updated_at)
        return YTDSummaryResponse(summary=summary_text)

    except Exception as e:
        logger.error(f"Home Summary generation failed: {e}")
        return YTDSummaryResponse(summary=f"Heyy {userName}, great to see you! Ready to dive into some growth today? 🔥")



@app.post("/api/updateUser", response_model=list[SessionsReponse])
def create_user(req: UserInput):
    """POST /api/updateUser: bootstrap user from onboarding fields and return prior session rows for the UI."""
    Base.metadata.create_all(bind=engine)

    from src.save_session import create_update_user

    sessions, userId = create_update_user(
        name=req.name,
        email=req.email,
        occupation=req.occupation,
        seniorityLevel=req.seniorityLevel
    )
    global currentUserId
    currentUserId = userId

    return sessions


def _db_user_to_profile(u: DbUser) -> UserProfile:
    """Convert a `users` ORM row into the API `UserProfile`, parsing ranked skills JSON when present."""
    ranked: Optional[list[str]] = None
    raw_ranked = getattr(u, "rankedSkills", None)
    if isinstance(raw_ranked, str) and raw_ranked.strip():
        try:
            v = json.loads(raw_ranked)
            if isinstance(v, list):
                ranked = [str(x) for x in v]
        except Exception:
            ranked = None
    return UserProfile(
        id=str(getattr(u, "id")),
        email=str(getattr(u, "email")),
        name=getattr(u, "name", None),
        occupation=getattr(u, "occupation", None),
        seniorityLevel=getattr(u, "seniorityLevel", None),
        rankedSkills=ranked,
        otherFocus=getattr(u, "otherFocus", None),
        voiceRecorded=getattr(u, "voiceRecorded", None),
    )


@app.post("/api/user", response_model=UserProfile)
def upsert_user(req: UpsertUserRequest):
    """POST /api/user: create or update profile fields keyed by email and set `currentUserId`."""
    email = (req.email or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="email is required")

    with SessionLocal() as db:
        u = db.query(DbUser).filter(DbUser.email == email).first()
        if not u:
            u = DbUser(email=email)
            db.add(u)

        if req.name is not None:
            u.name = req.name
        if req.occupation is not None:
            u.occupation = req.occupation
        if req.seniorityLevel is not None:
            u.seniorityLevel = req.seniorityLevel
        if req.otherFocus is not None:
            u.otherFocus = req.otherFocus
        if req.voiceRecorded is not None:
            u.voiceRecorded = bool(req.voiceRecorded)
        if req.rankedSkills is not None:
            u.rankedSkills = json.dumps([str(x) for x in req.rankedSkills], ensure_ascii=False)

        # Touch last_login
        try:
            u.last_login = datetime.utcnow()
        except Exception:
            pass

        db.commit()
        db.refresh(u)

        global currentUserId
        currentUserId = str(getattr(u, "id"))

        return _db_user_to_profile(u)


@app.get("/api/user", response_model=UserProfile)
def get_user(email: str):
    """GET /api/user: load profile by query `email` and set `currentUserId` for later handlers."""
    email_norm = (email or "").strip().lower()
    if not email_norm:
        raise HTTPException(status_code=400, detail="email is required")

    with SessionLocal() as db:
        u = db.query(DbUser).filter(DbUser.email == email_norm).first()
        if not u:
            raise HTTPException(status_code=404, detail="user not found")

        global currentUserId
        currentUserId = str(getattr(u, "id"))
        return _db_user_to_profile(u)


@app.post("/api/reset_user")
def reset_user(req: ResetUserRequest):
    """POST /api/reset_user: remove a user and their sessions (intended for development)."""
    email_norm = (req.email or "").strip().lower()
    if not email_norm:
        raise HTTPException(status_code=400, detail="email is required")

    with SessionLocal() as db:
        u = db.query(DbUser).filter(DbUser.email == email_norm).first()
        if not u:
            return {"ok": True, "deleted": False}

        db.query(DbSession).filter(DbSession.user_id == u.id).delete(synchronize_session=False)
        db.delete(u)
        db.commit()

        global currentUserId
        if currentUserId and currentUserId == str(getattr(u, "id")):
            currentUserId = ""

        return {"ok": True, "deleted": True}


@app.get("/api/dashboard_metrics", response_model=DashboardMetricsResponse)
def dashboard_metrics(
    userId: Optional[str] = None,
    email: Optional[str] = None,
    start: Optional[str] = None,
    windowDays: int = 35,
):
    """GET /api/dashboard_metrics: aggregate CRI/CEI session scores into dashboard cards and time series.

    Default behavior is **since first interaction** (first valid session for the user).
    You can pin the start date by passing `start=YYYY-MM-DD` (naive UTC), or request a rolling window via `windowDays`.

    Rules:
    - CRI/CEI are stored as 1-5; map to 60-100 by: score = 50 + 10 * rating.
      (1→60, 2→70, 3→80, 4→90, 5→100)
    - Conversations analyzed: count of unique Session.id in the window.
    - Days active: count of unique created_at dates in the window.
    - Overall score: avg((CRI + CEI)/2) in the window, scaled to 0-100.
    - Progress over time: daily avg overall score in the window (fills missing days by carrying forward last known score).
    - Skills: Effective Communication = CEI; Conflict Resolution = CRI in the window, scaled.
    """

    def _day_start(dt: datetime) -> datetime:
        """Normalize a datetime to UTC midnight for consistent day-bucket comparisons."""
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)

    def _parse_start_yyyy_mm_dd(s: str) -> Optional[datetime]:
        """Parse `YYYY-MM-DD` into a naive UTC midnight datetime, or None if invalid."""
        try:
            s2 = (s or "").strip()
            if not s2:
                return None
            d = date.fromisoformat(s2)
            return datetime(d.year, d.month, d.day, 0, 0, 0, 0)
        except Exception:
            return None

    # DB column `sessions.created_at` is naive DateTime; use naive UTC timestamps for filters.
    now = datetime.utcnow()
    window_days = int(windowDays) if isinstance(windowDays, int) else 35
    if window_days < 1:
        window_days = 1
    if window_days > 365:
        window_days = 365

    parsed_start = _parse_start_yyyy_mm_dd(start or "")

    def _scale_1_to_5_to_100(x: Optional[float]) -> Optional[float]:
        """Map a 1–5 session rating to the dashboard's 60–100 scale; non-finite values become None."""
        if x is None:
            return None
        try:
            v = float(x)
            if not math.isfinite(v):
                return None
            # Map 1-5 to 60-100.
            # This is linear, so averaging ratings then mapping is equivalent to mapping then averaging.
            return 50.0 + (10.0 * v)
        except Exception:
            return None

    with SessionLocal() as db:
        resolved_user_id = None
        if userId:
            try:
                resolved_user_id = uuid.UUID(userId)
            except Exception:
                resolved_user_id = None
        elif email:
            u = db.query(DbUser).filter(DbUser.email == email).first()
            resolved_user_id = getattr(u, "id", None)
        elif currentUserId:
            try:
                resolved_user_id = uuid.UUID(currentUserId)
            except Exception:
                resolved_user_id = None

        if not resolved_user_id:
            return DashboardMetricsResponse(
                overallScore=0.0,
                overallChangePct=None,
                conversationsAnalyzedThisMonth=0,
                daysActiveThisMonth=0,
                progressOverTime=[],
                skills=[
                    DashboardSkillScore(skill="Effective Communication", score=0.0),
                    DashboardSkillScore(skill="Conflict Resolution", score=0.0),
                ],
                avgCri=None,
                avgCei=None,
            )

        valid_scores = and_(
            DbSession.cri.isnot(None),
            DbSession.cei.isnot(None),
            DbSession.cri >= 1,
            DbSession.cri <= 5,
            DbSession.cei >= 1,
            DbSession.cei <= 5,
        )

        # Resolve window:
        # - If `start` is provided, use it (window start pinned).
        # - Else, start from the user's first valid session date.
        # - If no sessions yet, fall back to a short rolling window.
        window_end = _day_start(now) + timedelta(days=1)  # exclusive
        if parsed_start is not None:
            window_start = parsed_start
        else:
            first_dt = (
                db.query(func.min(DbSession.created_at))
                .filter(DbSession.user_id == resolved_user_id, valid_scores)
                .scalar()
            )
            if first_dt:
                try:
                    window_start = _day_start(first_dt)
                except Exception:
                    window_start = _day_start(now) - timedelta(days=window_days - 1)
            else:
                window_start = _day_start(now) - timedelta(days=window_days - 1)

        # Previous period for change% uses a window of equal length.
        window_len_days = max(1, (window_end.date() - window_start.date()).days)
        prev_window_end = window_start
        prev_window_start = window_start - timedelta(days=window_len_days)

        base = and_(DbSession.user_id == resolved_user_id, valid_scores)
        in_window = and_(DbSession.created_at >= window_start, DbSession.created_at < window_end)
        in_prev_window = and_(DbSession.created_at >= prev_window_start, DbSession.created_at < prev_window_end)

        overall_expr = (DbSession.cri + DbSession.cei) / 2.0

        # Cards: overall score (window) and period-over-period change.
        avg_overall_this = db.query(func.avg(overall_expr)).filter(base, in_window).scalar()
        avg_overall_prev = db.query(func.avg(overall_expr)).filter(base, in_prev_window).scalar()
        overall_score = _scale_1_to_5_to_100(avg_overall_this) or 0.0

        overall_change_pct: Optional[float] = None
        if avg_overall_prev is not None and math.isfinite(float(avg_overall_prev)) and float(avg_overall_prev) > 0:
            try:
                num = float(avg_overall_this or 0.0)
                den = float(avg_overall_prev)
                if math.isfinite(num) and math.isfinite(den) and den != 0:
                    overall_change_pct = ((num - den) / den) * 100.0
            except Exception:
                overall_change_pct = None

        # Conversations analyzed (window): unique session ids.
        conversations_analyzed = (
            db.query(func.count(func.distinct(DbSession.id))).filter(DbSession.user_id == resolved_user_id, in_window).scalar()
            or 0
        )

        # Days active (window): unique dates with sessions.
        days_active = (
            db.query(func.count(func.distinct(func.date(DbSession.created_at))))
            .filter(DbSession.user_id == resolved_user_id, in_window)
            .scalar()
            or 0
        )

        # Progress over time: daily avg overall (window). Fill missing days by carry-forward.
        progress_rows = (
            db.query(func.date_trunc("day", DbSession.created_at).label("day"), func.avg(overall_expr).label("avg_overall"))
            .filter(base, in_window)
            .group_by("day")
            .order_by("day")
            .all()
        )
        by_iso_day: dict[str, float] = {}
        for day, avg_val in progress_rows:
            try:
                iso_day = day.date().isoformat() if hasattr(day, "date") else str(day)
            except Exception:
                iso_day = str(day)
            by_iso_day[str(iso_day)] = float(_scale_1_to_5_to_100(avg_val) or 0.0)

        progress: list[DashboardProgressPoint] = []
        # Initialize to the first observed score in range so the chart doesn't start at 0.
        first_score: Optional[float] = None
        start_iso = window_start.date().isoformat()
        if start_iso in by_iso_day:
            first_score = by_iso_day[start_iso]
        elif by_iso_day:
            try:
                first_key = sorted(by_iso_day.keys())[0]
                first_score = by_iso_day[first_key]
            except Exception:
                first_score = None
        last_known = float(first_score or 0.0)
        d = window_start.date()
        end_d = (window_end - timedelta(days=1)).date()
        while d <= end_d:
            iso = d.isoformat()
            if iso in by_iso_day:
                last_known = by_iso_day[iso]
            progress.append(DashboardProgressPoint(date=iso, overall=last_known))
            d = d + timedelta(days=1)

        # Skills (window): avg CEI and avg CRI, scaled.
        avg_cri_this = db.query(func.avg(DbSession.cri)).filter(base, in_window).scalar()
        avg_cei_this = db.query(func.avg(DbSession.cei)).filter(base, in_window).scalar()
        avg_cri_prev = db.query(func.avg(DbSession.cri)).filter(base, in_prev_window).scalar()
        avg_cei_prev = db.query(func.avg(DbSession.cei)).filter(base, in_prev_window).scalar()

        cei_change_pct: Optional[float] = None
        if avg_cei_prev is not None and math.isfinite(float(avg_cei_prev)) and float(avg_cei_prev) > 0:
            try:
                num = float(avg_cei_this or 0.0)
                den = float(avg_cei_prev)
                if math.isfinite(num) and math.isfinite(den) and den != 0:
                    cei_change_pct = ((num - den) / den) * 100.0
            except Exception:
                cei_change_pct = None

        cri_change_pct: Optional[float] = None
        if avg_cri_prev is not None and math.isfinite(float(avg_cri_prev)) and float(avg_cri_prev) > 0:
            try:
                num = float(avg_cri_this or 0.0)
                den = float(avg_cri_prev)
                if math.isfinite(num) and math.isfinite(den) and den != 0:
                    cri_change_pct = ((num - den) / den) * 100.0
            except Exception:
                cri_change_pct = None

        skills = [
            DashboardSkillScore(
                skill="Effective Communication",
                score=_scale_1_to_5_to_100(avg_cei_this) or 0.0,
                changePct=cei_change_pct,
            ),
            DashboardSkillScore(
                skill="Conflict Resolution",
                score=_scale_1_to_5_to_100(avg_cri_this) or 0.0,
                changePct=cri_change_pct,
            ),
        ]

        return DashboardMetricsResponse(
            overallScore=overall_score,
            overallChangePct=overall_change_pct,
            conversationsAnalyzedThisMonth=int(conversations_analyzed),
            daysActiveThisMonth=int(days_active),
            progressOverTime=progress,
            skills=skills,
            avgCri=float(avg_cri_this) if avg_cri_this is not None else None,
            avgCei=float(avg_cei_this) if avg_cei_this is not None else None,
        )


_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="ui")