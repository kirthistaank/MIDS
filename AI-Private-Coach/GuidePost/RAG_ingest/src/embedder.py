
"""
src/embedder.py
Parallel embedding — calls generate_embedding() from whichever client is passed in.
Keeping this separate from the client means the parallelism logic never needs
to change when you swap Ollama → HuggingFace.
"""
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Tuple, Callable

from src.logging_utils import get_logger

_lock    = threading.Lock()
_counter = {"done": 0, "total": 0}
log = get_logger(__name__)


def _tick():
    with _lock:
        _counter["done"] += 1
        d, t = _counter["done"], _counter["total"]
        if d % 50 == 0 or d == t:
            log.info(f"  [embed] {d}/{t} ({100*d//t}%)")


def add_embeddings_to_chunks(
    chunks: List[Dict[str, Any]],
    generate_embedding: Callable[[str], List[float]],
    workers: int = 4,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Attach embeddings to each chunk in parallel.
    Accepts any generate_embedding function — Ollama, HF, SageMaker, etc.
    Returns (chunks, embedding_dimension).
    """
    log.info(f"Generating embeddings — {workers} workers, {len(chunks)} chunks...")
    _counter["done"]  = 0
    _counter["total"] = len(chunks)

    def _embed(ch):
        ch["embedding"] = generate_embedding(ch["content"])
        _tick()
        return ch

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_embed, ch): ch for ch in chunks}
        for f in as_completed(futures):
            try:
                f.result()
            except Exception as e:
                log.warning(f"Embedding failed: {e}")

    dim = len(chunks[0]["embedding"]) if chunks and "embedding" in chunks[0] else 0
    return chunks, dim

