"""
retrieval.py — Hybrid search + reranking pipeline.

Pipeline:
  1. Dense search   — Pinecone vector similarity (semantic)
  2. Sparse search  — BM25 keyword matching (lexical)
  3. Merge          — Reciprocal Rank Fusion combines both result sets
  4. Rerank         — Cross-encoder scores each candidate by true relevance
  5. Return         — Top-k highest quality chunks

Install:
    pip install rank-bm25 sentence-transformers
"""

import os
import json
import glob
import math
import requests
from typing import Optional

from pinecone import Pinecone
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder

import config
from logger import get_logger

log = get_logger(__name__)

# ── Singletons ────────────────────────────────────────────────────────────────

_pc           = None
_pinecone_idx = None
_reranker     = None
_bm25_index   = None
_bm25_corpus  = []   # list of {"id": chunk_id, "text": text}


def _get_pinecone_index():
    global _pc, _pinecone_idx
    if _pinecone_idx is None:
        log.info("Initialising Pinecone | index=%s", config.PINECONE_INDEX_NAME)
        _pc          = Pinecone(api_key=config.PINECONE_API_KEY)
        _pinecone_idx = _pc.Index(config.PINECONE_INDEX_NAME)
    return _pinecone_idx


def _get_reranker():
    global _reranker
    if _reranker is None:
        model = "cross-encoder/ms-marco-MiniLM-L-6-v2"
        log.info("Loading reranker model | model=%s", model)
        _reranker = CrossEncoder(model)
        log.info("Reranker ready")
    return _reranker


def _get_bm25_index():
    """
    Build a BM25 index from all chunk_texts JSON files.
    Cached after first build — only runs once per server start.
    """
    global _bm25_index, _bm25_corpus
    if _bm25_index is not None:
        return _bm25_index, _bm25_corpus

    log.info("Building BM25 index from chunk_texts...")
    chunk_dir = os.path.join(os.path.dirname(__file__), "..", "chunk_texts")
    files     = glob.glob(os.path.join(chunk_dir, "*.json"))

    corpus = []
    for fpath in files:
        source_name = os.path.basename(fpath).replace("_texts.json", "")
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    chunk_id = f"{source_name}_chunk_{item.get('chunk_id', '')}"
                    text     = item.get("content") or item.get("text") or item.get("raw_text") or ""
                    if text:
                        corpus.append({"id": chunk_id, "text": text})
        except Exception as e:
            log.warning("Failed to load chunk file | file=%s | error=%s", fpath, e)

    tokenized = [doc["text"].lower().split() for doc in corpus]
    _bm25_corpus = corpus
    _bm25_index  = BM25Okapi(tokenized)
    log.info("BM25 index built | chunks=%d", len(corpus))
    return _bm25_index, _bm25_corpus


# ── Embedding ─────────────────────────────────────────────────────────────────

def _embed(query: str) -> list[float]:
    resp = requests.post(
        f"{config.OLLAMA_BASE_URL}/api/embeddings",
        json={"model": "nomic-embed-text", "prompt": query},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]


# ── Reciprocal Rank Fusion ────────────────────────────────────────────────────

def _rrf(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    """
    Merge multiple ranked lists using Reciprocal Rank Fusion.
    Higher score = better combined rank across all lists.
    """
    scores = {}
    for ranked_list in rankings:
        for rank, doc_id in enumerate(ranked_list):
            scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
    return scores


# ── Main hybrid search function ───────────────────────────────────────────────

def hybrid_search(
    query:      str,
    top_k:      int = 10,   # candidates before reranking
    final_k:    int = 3,    # chunks returned after reranking
    namespace:  Optional[str] = None,
) -> list[dict]:
    """
    Full hybrid retrieval pipeline:
      1. Dense search  (Pinecone)
      2. Sparse search (BM25)
      3. RRF merge
      4. Rerank
      5. Return top final_k chunks with text

    Returns list of dicts:
      {"id": chunk_id, "text": text, "score": rerank_score,
       "source": source_name, "title": title}
    """
    log.info("Hybrid search | query=%s | top_k=%d | final_k=%d", query, top_k, final_k)

    # ── 1. Dense search ───────────────────────────────────────────────────────
    dense_ids = []
    dense_meta = {}
    try:
        embedding = _embed(query)
        index     = _get_pinecone_index()
        results   = index.query(
            vector=embedding,
            top_k=top_k,
            include_metadata=True,
            namespace=namespace or config.PINECONE_NAMESPACE or None,
        )
        for match in results["matches"]:
            dense_ids.append(match.id)
            dense_meta[match.id] = match.metadata or {}
        log.info("Dense search returned %d results", len(dense_ids))
    except Exception as e:
        log.error("Dense search failed | error=%s", e, exc_info=True)

    # ── 2. Sparse search (BM25) ───────────────────────────────────────────────
    sparse_ids = []
    try:
        bm25, corpus = _get_bm25_index()
        tokenized_q  = query.lower().split()
        bm25_scores  = bm25.get_scores(tokenized_q)

        # Get top_k indices sorted by BM25 score
        top_indices = sorted(
            range(len(bm25_scores)),
            key=lambda i: bm25_scores[i],
            reverse=True
        )[:top_k]

        sparse_ids = [corpus[i]["id"] for i in top_indices if bm25_scores[i] > 0]
        log.info("BM25 search returned %d results", len(sparse_ids))
    except Exception as e:
        log.error("BM25 search failed | error=%s", e, exc_info=True)

    # ── 3. RRF merge ─────────────────────────────────────────────────────────
    if not dense_ids and not sparse_ids:
        log.warning("Both dense and sparse search returned no results")
        return []

    rrf_scores  = _rrf([dense_ids, sparse_ids])
    merged_ids  = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:top_k]
    log.info("RRF merged %d unique candidates", len(merged_ids))

    # ── 4. Load chunk texts for candidates ────────────────────────────────────
    chunk_dir = os.path.join(os.path.dirname(__file__), "..", "chunk_texts")
    _file_cache: dict[str, dict] = {}

    def _load_source(source_name: str) -> dict:
        if source_name in _file_cache:
            return _file_cache[source_name]
        pattern = os.path.join(chunk_dir, f"{source_name}_texts.json")
        matches = glob.glob(pattern)
        if not matches:
            all_f   = glob.glob(os.path.join(chunk_dir, "*.json"))
            matches = [f for f in all_f if source_name.lower() in f.lower()]
        if not matches:
            return {}
        with open(matches[0], "r", encoding="utf-8") as f:
            data = json.load(f)
        normalized = {}
        if isinstance(data, list):
            for item in data:
                key  = f"{source_name}_chunk_{item.get('chunk_id', '')}"
                text = item.get("content") or item.get("text") or item.get("raw_text") or ""
                normalized[key] = text
        _file_cache[source_name] = normalized
        return normalized

    candidates = []
    for cid in merged_ids:
        if "_chunk_" not in cid:
            continue
        source_name = cid.split("_chunk_")[0]
        chunks      = _load_source(source_name)
        text        = chunks.get(cid, "")
        if not text:
            continue
        meta   = dense_meta.get(cid, {})
        candidates.append({
            "id":     cid,
            "text":   text,
            "source": meta.get("source", source_name),
            "title":  meta.get("title", ""),
            "themes": meta.get("themes", []),
        })

    if not candidates:
        log.warning("No chunk texts found for merged candidates")
        return []

    # ── 5. Rerank ─────────────────────────────────────────────────────────────
    try:
        reranker    = _get_reranker()
        pairs       = [[query, c["text"]] for c in candidates]
        rerank_scores = reranker.predict(pairs)

        for i, c in enumerate(candidates):
            c["score"] = float(rerank_scores[i])

        candidates.sort(key=lambda x: x["score"], reverse=True)
        final = candidates[:final_k]

        log.info("Reranking complete | candidates=%d | returning=%d", len(candidates), len(final))
        for i, c in enumerate(final, 1):
            log.info(
                "RERANKED CHUNK [%d/%d] | id=%s | source=%s | title=%s | score=%.4f",
                i, len(final), c["id"], c["source"], c["title"] or "—", c["score"]
            )

        return final

    except Exception as e:
        log.error("Reranking failed | error=%s", e, exc_info=True)
        # Fall back to RRF-ordered candidates without reranking
        log.warning("Falling back to RRF order without reranking")
        for i, c in enumerate(candidates):
            c["score"] = rrf_scores.get(c["id"], 0.0)
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:final_k]