"""
src/pinecone_store.py  —  drop-in replacement.

Only change from your original:
  - upsert_chunks() now includes short_name, themes, best_for in Pinecone metadata
  - everything else (batching, index creation, dimension check) unchanged
"""
import time
from typing import List, Dict, Any

from pinecone import Pinecone, ServerlessSpec
from src.config import (
    PINECONE_API_KEY, PINECONE_ENV,
    PINECONE_INDEX, PINECONE_NAMESPACE,
)
from src.timing import format_duration
from src.logging_utils import get_logger

log = get_logger(__name__)


def get_or_create_index(dimension: int, index_name: str = PINECONE_INDEX):
    pc       = Pinecone(api_key=PINECONE_API_KEY)
    existing = [i.name for i in pc.list_indexes()]
    if index_name not in existing:
        log.info(f"Creating Pinecone index '{index_name}' (dim={dimension})...")
        pc.create_index(
            name=index_name, dimension=dimension, metric="cosine",
            spec=ServerlessSpec(cloud="aws", region=PINECONE_ENV),
        )
    else:
        desc    = pc.describe_index(index_name)
        idx_dim = getattr(desc, "dimension", None)
        if idx_dim and idx_dim != dimension:
            raise ValueError(
                f"Dimension mismatch: model produces {dimension}, "
                f"index '{index_name}' expects {idx_dim}."
            )
        log.info(f"Using existing Pinecone index '{index_name}' (dim={idx_dim}).")
    return pc.Index(index_name)


def upsert_chunks(
    chunks: List[Dict[str, Any]],
    pdf_name: str,
    index=None,
    namespace: str = PINECONE_NAMESPACE,
) -> None:
    if index is None:
        raise RuntimeError("Call get_or_create_index() before upsert_chunks().")

    vectors = []
    for ch in chunks:
        # ── Pinecone metadata — all values must be str, int, float, or List[str] ──
        meta: Dict[str, Any] = {
            "source":     pdf_name,
            "chunk_id":   ch["chunk_id"],
            # ── original fields ────────────────────────────────────────────────
            "framework":  ch.get("framework",  ""),
            # ── new fields ─────────────────────────────────────────────────────
            "short_name": ch.get("short_name", ""),
            "themes":     ch.get("themes",     []),   # List[str] — Pinecone supports this
            "best_for":   ch.get("best_for",   []),
        }
        # optional fields — only add if present
        if ch.get("chapter"):
            meta["chapter"] = str(ch["chapter"])
        if ch.get("title"):
            meta["title"] = str(ch["title"])

        vectors.append({
            "id":       f"{pdf_name}_chunk_{ch['chunk_id']}",
            "values":   ch["embedding"],
            "metadata": meta,
        })

    total = len(vectors)
    t0    = time.time()
    log.info(f"Upserting {total} vectors (ns='{namespace}')...")
    for i in range(0, total, 100):
        batch = vectors[i : i + 100]
        index.upsert(vectors=batch, namespace=namespace)
        log.info(f"  batch {i}–{i+len(batch)-1} done")
    log.info(f"✓ Pinecone upsert: {total} vectors in {format_duration(time.time() - t0)}.")