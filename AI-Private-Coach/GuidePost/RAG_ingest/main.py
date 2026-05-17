"""
main.py  —  RAG_ingest/main.py

Changes from your original (marked with # ← NEW):
  1. Imports book_registry.get_book_meta
  2. Passes book_meta to chunk_with_hybrid()
  3. Caps workers at 4 to avoid M5 Mac crashes
  4. Everything else identical to your original

Run from RAG_ingest/:
    python main.py --triple-workers 4 --embed-workers 4
    python main.py --triple-workers 4 --embed-workers 4 --index-name all-frameworks-v1 \
                   --neo4j-database all-frameworks-v1 --neo4j-mode cloud
"""
import argparse
import time
import traceback
from pathlib import Path
import json
import os
from src.config import (
    TRIPLE_WORKERS, EMBED_WORKERS, NEO4J_BATCH_SIZE,
    PINECONE_INDEX, PINECONE_NAMESPACE, LLM_CLIENT_SWITCH,
    DEFAULT_MODE, TRIPLE_BATCH_SIZE, CHUNKED_FOLDER_PATH,
)
from src.chunking         import chunk_with_hybrid
from src.embedder         import add_embeddings_to_chunks
from src.triple_generator import generate_all_triples_parallel
from src.pinecone_store   import get_or_create_index, upsert_chunks
from src.neo4j_store      import ingest_to_neo4j
from src.evaluator        import compare_chunk_strategies
from src.pdf_utils        import find_cbt_pdf, load_or_extract_text
from src.timing           import format_duration, log_step_duration
from src.logging_utils    import get_logger
from src.book_registry    import get_book_meta                        # ← NEW

_HERE = Path(__file__).resolve().parent
log   = get_logger(__name__, to_console=True)

# ── Worker safety cap for M5 Mac 24GB ─────────────────────────────────────────
# Ollama's HTTP connection pool saturates around 5–6 concurrent threads,
# causing timeouts that look like process kills. Hard cap at 4.
_MAX_SAFE_WORKERS = 4                                                    # ← NEW

# When scanning --data-dir, pick files with these extensions (case-insensitive).
_SUPPORTED_BOOK_SUFFIXES = frozenset({".pdf", ".epub"})  # add more extnsion here. Make sure docling supporting these extensions.


def parse_args():
    p = argparse.ArgumentParser(description="Framework PDF ingestion pipeline")
    p.add_argument("--data-dir",            type=str, default=None)
    p.add_argument("--pdf",                 type=str, default=None)
    p.add_argument("--index-name",          type=str, default=PINECONE_INDEX)
    p.add_argument("--namespace",           type=str, default=PINECONE_NAMESPACE)
    p.add_argument("--no-pinecone",         action="store_true")
    p.add_argument("--no-neo4j",            action="store_true")
    p.add_argument("--neo4j-mode",          choices=("local", "cloud"), default="local")
    p.add_argument("--neo4j-database",      type=str, default=None)
    p.add_argument("--neo4j-start-chunk",   type=int, default=0)
    p.add_argument("--neo4j-progress-file", type=str, default=None)
    p.add_argument("--neo4j-batch-size",    type=int, default=NEO4J_BATCH_SIZE)
    p.add_argument("--triple-workers",      type=int, default=TRIPLE_WORKERS)
    p.add_argument("--embed-workers",       type=int, default=EMBED_WORKERS)
    p.add_argument("--fast-embeddings",     action="store_true")
    p.add_argument("--compare-strategies",  action="store_true")
    return p.parse_args()


def main():
    t0   = time.time()
    args = parse_args()

    # ── Cap workers ───────────────────────────────────────────────────────────
    triple_workers = min(args.triple_workers, _MAX_SAFE_WORKERS)         # ← NEW
    embed_workers  = min(args.embed_workers,  _MAX_SAFE_WORKERS)         # ← NEW
    if triple_workers < args.triple_workers:
        log.warning(
            f"--triple-workers {args.triple_workers} capped to {triple_workers} "
            f"(M5 Mac safety limit). Use --triple-workers ≤4 to suppress this."
        )

    if args.fast_embeddings:
        import src.config as cfg
        cfg.OLLAMA_EMBED_MODEL = "all-minilm"
        cfg.EMBED_MAX_TOKENS   = 512
        log.info("[fast-embeddings] model=all-minilm, max_tokens=512")

    # ── Locate PDFs / EPUBs ───────────────────────────────────────────────────
    data_dir = Path(args.data_dir) if args.data_dir else _HERE / "data"
    if args.pdf:
        pdf_paths = [Path(args.pdf)]
    else:
        pdf_paths = sorted(
            p
            for p in data_dir.iterdir()
            if p.is_file() and p.suffix.lower() in _SUPPORTED_BOOK_SUFFIXES
        )
        if not pdf_paths:
            raise FileNotFoundError(
                f"No .pdf or .epub files found in: {data_dir}"
            )
    print("pdf_paths is: ", pdf_paths)
    
    # ── LLM backend ───────────────────────────────────────────────────────────
    if LLM_CLIENT_SWITCH == "huggingface":
        log.info("Huggingface client activated")
        from src import huggingface_client as llm_client
    elif LLM_CLIENT_SWITCH == "ollama":
        from src import ollama_client as llm_client
    elif LLM_CLIENT_SWITCH == "sagemaker":
        from src import sagemaker_client as llm_client
    else:
        raise ValueError(f"Invalid LLM client switch: {LLM_CLIENT_SWITCH}")

    if not llm_client.health_check():
        log.debug("*" * 50)
        log.info(str(LLM_CLIENT_SWITCH))
        log.error("LLM backend not ready. Aborting.")
        return
    
    # ── Per-PDF pipeline ──────────────────────────────────────────────────────
    for pdf_path in pdf_paths:
        t_doc_start = time.time()
        pdf_name   = pdf_path.stem
        mb         = pdf_path.stat().st_size / (1024 * 1024) if pdf_path.is_file() else 0
        book_meta  = get_book_meta(pdf_name)
        log.info(
            f"Document: {pdf_path.name} ({mb:.2f} MB) "
            f"| framework={book_meta['framework']} | short_name={book_meta['short_name']}"
        )
        print("&&&"*50)
        print("PDF path is: ", pdf_path)
        print("Pinecone Index Name is: ", args.index_name)
        print("&&"*50)
        
        # ── Step 1: Extract / load cached text ─────────────────────────────────
        try:
            t_step = time.time()
            cleaned_text = load_or_extract_text(pdf_path)
            log_step_duration(log, "Text extraction", time.time() - t_step)
        except Exception as e:
            log.error("Text extraction failed for %s: %s. Skipping document.", pdf_path.name, e)
            log.debug(traceback.format_exc())
            continue

        if not (cleaned_text and cleaned_text.strip()) or len(cleaned_text.strip()) < 100:
            log.warning(
                "Extracted text is empty or too short for %s (%d chars). Skipping document.",
                pdf_path.name, len(cleaned_text.strip()) if cleaned_text else 0,
            )
            continue

        if args.compare_strategies:
            try:
                compare_chunk_strategies(cleaned_text, llm_client.generate_embedding)
            except Exception as e:
                log.warning("compare_strategies failed: %s. Continuing.", e)

        # ── Step 2: Chunk ─────────────────────────────────────────────────────
        try:
            t_step = time.time()
            chunks  = chunk_with_hybrid(cleaned_text, book_meta=book_meta)
            if DEFAULT_MODE:
                chunks = chunks[:TRIPLE_BATCH_SIZE]
                log.info(f"DEFAULT_MODE: limited to {len(chunks)} chunks.")
            log_step_duration(log, "Chunking", time.time() - t_step)
            log.info("Chunking produced %d chunks.", len(chunks))
        except Exception as e:
            log.error("Chunking failed for %s: %s. Skipping document.", pdf_path.name, e)
            log.debug(traceback.format_exc())
            continue

        if not chunks:
            log.warning("No chunks produced for %s. Skipping rest of pipeline for this document.", pdf_path.name)
            log_step_duration(log, "Per-document total (skipped after chunking)", time.time() - t_doc_start)
            continue

        # ── Step 3: Persist chunks to JSON ─────────────────────────────────────
        chunk_dir = Path(CHUNKED_FOLDER_PATH)
        chunk_dir.mkdir(parents=True, exist_ok=True)
        chunks_json_path = chunk_dir / f"{pdf_name}_texts.json"
        try:
            t_step = time.time()
            with chunks_json_path.open("w", encoding="utf-8") as f:
                json.dump(
                    [{k: v for k, v in ch.items() if k != "embedding"} for ch in chunks],
                    f, ensure_ascii=False, indent=2,
                )
            log_step_duration(log, "Write chunks JSON", time.time() - t_step)
            log.info("Wrote chunks JSON → %s", chunks_json_path)
        except (TypeError, OSError) as e:
            log.warning("Failed to write chunks JSON for %s: %s. Continuing.", pdf_path.name, e)

        # ── Step 4: Embed ────────────────────────────────────────────────────
        try:
            t_step = time.time()
            chunks, dim = add_embeddings_to_chunks(
                chunks, llm_client.generate_embedding, workers=embed_workers,
            )
            log_step_duration(log, "Embeddings", time.time() - t_step)
            log.info("Embeddings: dim=%d, %d chunks.", dim, len(chunks))
        except Exception as e:
            log.error("Embeddings failed for %s: %s. Skipping Pinecone and Neo4j for this document.", pdf_path.name, e)
            log.debug(traceback.format_exc())
            log_step_duration(log, "Per-document total (failed at embeddings)", time.time() - t_doc_start)
            continue

        # ── Step 5: Pinecone ──────────────────────────────────────────────────
        if not args.no_pinecone:
            try:
                t_step = time.time()
                log.info("\n$$$$$ Pinecone Index Name is: %s", args.index_name)
                
                index = get_or_create_index(dim, index_name=args.index_name)
                upsert_chunks(chunks, pdf_name, index=index, namespace=args.namespace)
                log_step_duration(log, "Pinecone upsert", time.time() - t_step)
            except Exception as e:
                log.warning("Pinecone failed for %s: %s. Continuing to Neo4j.", pdf_path.name, e)
                log.debug(traceback.format_exc())
        else:
            log.info("Skipping Pinecone (--no-pinecone).")

        # ── Step 6: Neo4j ─────────────────────────────────────────────────────
        if not args.no_neo4j:
            try:
                t_step = time.time()
                log.info("Generating triples — %d chunks, %d workers...", len(chunks), triple_workers)
                enriched = generate_all_triples_parallel(
                    chunks,
                    llm_client.generate_triples,
                    workers=triple_workers,
                    start_chunk=args.neo4j_start_chunk,
                )
                log.info("Ingesting %d enriched chunks to Neo4j...", len(enriched))
                ingest_to_neo4j(
                    enriched, pdf_name,
                    mode=args.neo4j_mode,
                    database=args.neo4j_database,
                    batch_size=args.neo4j_batch_size,
                    progress_file=args.neo4j_progress_file,
                )
                log_step_duration(log, "Neo4j (triples + ingest)", time.time() - t_step)
            except Exception as e:
                log.warning("Neo4j failed for %s: %s. Continuing to next document.", pdf_path.name, e)
                log.debug(traceback.format_exc())
        else:
            log.info("Skipping Neo4j (--no-neo4j).")

        log_step_duration(log, "Per-document total", time.time() - t_doc_start)
        log.info("--- Completed document: %s ---", pdf_path.name)

    total_elapsed = time.time() - t0
    log.info(
        "=== Pipeline complete: %d document(s) | Total time: %s ===",
        len(pdf_paths),
        format_duration(total_elapsed),
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        _log = get_logger(__name__, to_console=True)
        _log.error("Unhandled error: %s", e)
        _log.error(traceback.format_exc())
        raise  # caller can catch; use sys.exit(1) here if you prefer no traceback