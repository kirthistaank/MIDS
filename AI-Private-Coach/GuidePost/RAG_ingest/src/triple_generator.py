

# =============================================================================
"""
src/triple_generator.py
Parallel triple generation — calls generate_triples() from whichever client is passed in.
Same pattern as embedder.py: parallelism is decoupled from the LLM backend.
"""
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Callable
from src.config import DEFAULT_MODE
from src.logging_utils import get_logger

_lock    = threading.Lock()
_counter = {"done": 0, "total": 0}
_last_progress_ts = 0.0
log = get_logger(__name__)


def _progress_line(done: int, total: int) -> str:
    if total <= 0:
        return "[triples] 0/0 (0%)"
    pct = int((done * 100) // total)
    width = 24
    filled = int((pct * width) // 100)
    bar = "█" * filled + "·" * (width - filled)
    return f"[triples] |{bar}| {pct:>3}% ({done}/{total})"


def _tick() -> None:
    """
    Thread-safe progress increment. Logs progress at most every ~2s,
    and always logs the final completion line.
    """
    global _last_progress_ts
    now = time.time()
    with _lock:
        _counter["done"] += 1
        done, total = _counter["done"], _counter["total"]
        should_log = (done == total) or (now - _last_progress_ts >= 2.0)
        if should_log:
            _last_progress_ts = now
            log.info(_progress_line(done, total))


def generate_all_triples_parallel(
    chunks: List[Dict[str, Any]],
    generate_triples: Callable[[str], List[Dict]],
    workers: int = 4,
    start_chunk: int = 0,
) -> List[Dict[str, Any]]:
    """
    Generate triples for eligible chunks.

    For this batch-mode configuration we:
      - Restrict to a single worker for determinism.
      - Process ONLY the first N eligible chunks in this run, then return.

    Attaches 'triples' key to each processed chunk. Returns only chunks that got triples.
    Accepts any generate_triples function — Ollama, HF, SageMaker, etc.
    """
    eligible = [ch for ch in chunks if ch["chunk_id"] >= start_chunk]

    if not eligible:
        log.info("No eligible chunks found for triple generation.")
        return []

    if DEFAULT_MODE:
        batch_size = int(os.getenv("TRIPLE_BATCH_SIZE", "10"))
        eligible = eligible[:batch_size]
        log.info(f"Using DEFAULT_MODE, limiting to first {len(eligible)} chunks (TRIPLE_BATCH_SIZE={batch_size}).")
        # Force single worker as requested.
        workers = 1
    else:
        # Respect caller-provided workers in non-default mode.
        workers = workers

    log.info(f"Generating triples — workers={workers}, chunks={len(eligible)} (DEFAULT_MODE={DEFAULT_MODE})...")
        
    _counter["done"]  = 0
    _counter["total"] = len(eligible)
    global _last_progress_ts
    _last_progress_ts = 0.0

    def _work(ch):
        triples = generate_triples(ch["content"])
        _tick()
        return ch["chunk_id"], triples

    results: Dict[int, List] = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_work, ch): ch for ch in eligible}
        for f in as_completed(futures):
            try:
                cid, triples = f.result()
                if triples:
                    results[cid] = triples
            except Exception as e:
                log.warning(f"Triple worker error: {e}")

    enriched: List[Dict[str, Any]] = []
    for ch in eligible:
        if ch["chunk_id"] in results:
            ch["triples"] = results[ch["chunk_id"]]
            enriched.append(ch)

    log.info(f"Triples done: {len(enriched)}/{len(eligible)} chunks had triples (batch_size={len(eligible)}).")
    return enriched
