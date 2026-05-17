"""
src/chunking.py  —  drop-in replacement for your existing file.

Only change from your original:
  - chunk_with_hybrid() now accepts optional book_meta dict
  - injects framework, short_name, themes, best_for into every chunk
  - framework no longer hardcoded as "CBT"
  - HybridChunker call and all other logic unchanged
"""
import re
from typing import List, Dict, Any, Optional

from .HybridChunker import HybridChunker as _HybridChunker
from src.config import (
    CHUNK_BASE_SIZE, CHUNK_OVERLAP_SIZE,
    CHUNK_SEMANTIC_THRESHOLD, CHUNK_EMBED_MODEL,
    CHUNK_STRUCT_MIN_TOKENS, CHUNK_STRUCT_MAX_TOKENS,
)
from src.logging_utils import get_logger

log = get_logger(__name__)


def chunk_with_hybrid(
    cleaned_text: str,
    book_meta: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Chunk cleaned plain text using HybridChunker.
    Accepts optional book_meta from book_registry.get_book_meta(pdf_stem).
    If not supplied, falls back to the old hardcoded "CBT" behaviour.
    Returns [] if input is empty or invalid so callers can handle gracefully.
    """
    if not (cleaned_text and cleaned_text.strip()):
        log.warning("chunk_with_hybrid: empty or whitespace-only text; returning no chunks.")
        return []
    # ── Safe defaults so existing callers without book_meta don't break ───────
    framework  = (book_meta or {}).get("framework",  "CBT")
    short_name = (book_meta or {}).get("short_name", "CBT")
    themes     = (book_meta or {}).get("themes",     [])
    best_for   = (book_meta or {}).get("best_for",   [])

    chunker = _HybridChunker(
        base_chunk_size=CHUNK_BASE_SIZE,
        overlap_size=CHUNK_OVERLAP_SIZE,
        semantic_threshold=CHUNK_SEMANTIC_THRESHOLD,
        embedding_model=CHUNK_EMBED_MODEL,
    )
    chunk_objs = chunker.chunk_document(cleaned_text)
    chunks, current_chapter = [], None

    for ch in chunk_objs:
        st = ch.section_title
        if st and st.strip().lower().startswith("chapter"):
            current_chapter = st.strip()

        # ── Build the content string with framework context prefix ─────────────
        # This prefix travels with the chunk into Pinecone metadata AND Neo4j,
        # so every retrieved passage carries its framework identity to the LLM.
        prefix = (
            f"[Framework: {framework}]\n"
            f"[Book: {short_name}]\n"
            f"[Themes: {', '.join(themes)}]\n"
            f"[Best for: {', '.join(best_for)}]\n\n"
        ) if themes else ""   # skip prefix if no metadata (fallback mode)

        chunks.append({
            # ── original fields — unchanged ───────────────────────────────────
            "content":    prefix + ch.text,
            "raw_text":   ch.text,           # clean text without prefix
            "chunk_id":   ch.chunk_id,
            "chapter":    current_chapter,
            "title":      st,
            # ── new metadata fields ───────────────────────────────────────────
            "framework":  framework,
            "short_name": short_name,
            "themes":     themes,
            "best_for":   best_for,
        })

    log.info(f"Built {len(chunks)} hybrid chunks [{short_name}].")
    return chunks


def build_structure_chunks(
    text: str,
    book_meta: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Unchanged logic — book_meta added for consistency."""
    framework  = (book_meta or {}).get("framework",  "CBT")
    short_name = (book_meta or {}).get("short_name", "CBT")
    themes     = (book_meta or {}).get("themes",     [])
    best_for   = (book_meta or {}).get("best_for",   [])

    pattern  = r"(?:^|\n)(#{1,3}\s.*)|(Principle No\.\s*\d+.*)|\n([A-Z][A-Z\s\-]{6,})\n"
    sections = [s.strip() for s in re.split(pattern, text) if s and s.strip()]
    chunks, buf, chapter, title = [], "", None, None

    for sec in sections:
        if sec.lower().startswith("chapter"):
            chapter = sec.strip()
        if "principle no." in sec.lower() or sec.startswith("#"):
            title = sec.strip()
        candidate = (buf + "\n" + sec).strip() if buf else sec
        if len(candidate.split()) <= CHUNK_STRUCT_MAX_TOKENS:
            buf = candidate
        else:
            if len(buf.split()) >= CHUNK_STRUCT_MIN_TOKENS:
                chunks.append({
                    "content":    buf.strip(),
                    "raw_text":   buf.strip(),
                    "chapter":    chapter,
                    "title":      title,
                    "framework":  framework,
                    "short_name": short_name,
                    "themes":     themes,
                    "best_for":   best_for,
                })
                buf = sec
            else:
                buf = candidate

    if buf.strip():
        chunks.append({
            "content":    buf.strip(),
            "raw_text":   buf.strip(),
            "chapter":    chapter,
            "title":      title,
            "framework":  framework,
            "short_name": short_name,
            "themes":     themes,
            "best_for":   best_for,
        })
    for i, ch in enumerate(chunks):
        ch["chunk_id"] = i

    log.info(f"Built {len(chunks)} structure-aware chunks [{short_name}].")
    return chunks