

"""
src/evaluator.py
Retrieval quality evaluation: coherence, noise, strategy comparison.
Accepts generate_embedding as a plain callable so it works with any backend.
"""
import re
import numpy as np
from typing import List, Dict, Any, Callable

from src.chunking import chunk_with_hybrid, build_structure_chunks
from src.embedder import add_embeddings_to_chunks
from src.logging_utils import get_logger

log = get_logger(__name__)


def cosine_similarity(a: List[float], b: List[float]) -> float:
    va, vb = np.array(a), np.array(b)
    return float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb)))


def retrieve_top_k(
    query: str,
    chunks: List[Dict[str, Any]],
    generate_embedding: Callable,
    k: int = 3,
) -> List[tuple]:
    qe     = generate_embedding(query)
    scored = [(cosine_similarity(qe, ch["embedding"]), ch) for ch in chunks]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:k]


def evaluate_coherence(chunk_text: str, generate_embedding: Callable) -> float:
    sentences = [s.strip() for s in re.split(r"[.!?]", chunk_text) if s.strip()]
    if len(sentences) < 3:
        return 0.5
    embs = [generate_embedding(s) for s in sentences[:8]]
    sims = [cosine_similarity(embs[i], embs[i+1]) for i in range(len(embs)-1)]
    return float(np.mean(sims)) if sims else 0.0


def evaluate_noise(chunk_text: str, generate_embedding: Callable) -> float:
    sentences = [s.strip() for s in re.split(r"[.!?]", chunk_text) if s.strip()]
    if len(sentences) < 5:
        return 0.2
    embs     = np.array([generate_embedding(s) for s in sentences[:8]])
    centroid = embs.mean(axis=0)
    dists    = [1.0 - cosine_similarity(e.tolist(), centroid.tolist()) for e in embs]
    return float(np.mean(dists)) if dists else 0.0


def evaluate_strategy(
    queries: List[str],
    chunks: List[Dict[str, Any]],
    name: str,
    generate_embedding: Callable,
) -> Dict[str, Any]:
    sims, cohs, noises = [], [], []
    for q in queries:
        for score, ch in retrieve_top_k(q, chunks, generate_embedding, k=3):
            sims.append(score)
            cohs.append(evaluate_coherence(ch["content"], generate_embedding))
            noises.append(evaluate_noise(ch["content"], generate_embedding))
    all_chunks = [ch for q in queries
                  for _, ch in retrieve_top_k(q, chunks, generate_embedding, k=3)]
    return {
        "strategy":              name,
        "avg_similarity":        float(np.mean(sims))   if sims   else 0.0,
        "avg_coherence":         float(np.mean(cohs))   if cohs   else 0.0,
        "avg_noise":             float(np.mean(noises)) if noises else 0.0,
        "rag_pdf_context_chars": len("\n---\n".join(c["content"] for c in all_chunks)),
        "rag_retrieved_chunks":  len(all_chunks),
    }


def compare_chunk_strategies(
    cleaned_text: str,
    generate_embedding: Callable,
    queries: List[str] = None,
) -> Dict[str, Dict]:
    queries = queries or [
        "How to differentiate between Vista mode, Enter mode, and Tango mode?",
        "Cognitive biases in technical collaboration: Anchoring vs Confirmation bias.",
        "Coaching techniques for reframing divergent priorities in cross-functional teams.",
    ]
    log.info("=== Evaluating Hybrid chunking ===")
    hc, _ = add_embeddings_to_chunks(chunk_with_hybrid(cleaned_text), generate_embedding)
    log.info("=== Evaluating Structure-aware chunking ===")
    sc, _ = add_embeddings_to_chunks(build_structure_chunks(cleaned_text), generate_embedding)
    hr = evaluate_strategy(queries, hc, "HybridChunker",  generate_embedding)
    sr = evaluate_strategy(queries, sc, "StructureAware", generate_embedding)
    log.info(f"HybridChunker: {hr}")
    log.info(f"StructureAware: {sr}")
    return {"hybrid": hr, "structure_aware": sr}