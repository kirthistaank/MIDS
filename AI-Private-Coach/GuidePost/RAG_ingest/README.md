# RAG_ingest 🔍

A Python-based **Retrieval-Augmented Generation (RAG)** testing and experimentation framework. This repo explores various RAG pipeline strategies including hybrid chunking, knowledge graph integration, document ingestion, and AI coaching interfaces.

---

## 📁 Project Structure

```
RAG_ingest/
├── main.py                          # Entry point for the RAG pipeline
├── Chunk.py                         # Basic chunking logic
├── HybridChunker.py                 # Hybrid chunking strategy implementation
├── KG.py                            # Knowledge Graph (KG) integration
├── document_extractor.py            # Document extraction utilities
├── lightRAG_cluade_main.py          # LightRAG pipeline with Claude integration
├── retrieval_query.py               # Query and retrieval logic
├── ingest/                          # Ingestion scripts/modules
├── data/                            # Raw input data
├── transcripts/                     # Transcript files for processing
├── rawtext_json/                    # Extracted raw text in JSON format
├── rawtext_plain/                   # Extracted raw text in plain format
├── chunk_texts/                     # Chunked text outputs
├── cache/                           # Cached embeddings or intermediate results
├── requirements.txt                 # Python dependencies
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- An Anthropic API key (Claude) or equivalent LLM API key (Ollam/HuggingFace)

### Installation


1. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   source venv/bin/activate    # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up your API key in config.py**
   ```bash
   echo .env
   # Update api keys in this file
   ```

### Run with Docker

Build the image from the `RAG_ingest/` directory (where `Dockerfile` lives):

```bash
docker build -t rag-ingest .
```

Run `main.py` in a container with your data, cache, and chunk outputs on the host:

```bash
docker run --rm \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/cache:/app/cache" \
  -v "$(pwd)/chunk_texts:/app/chunk_texts" \
  --env-file .env \
  rag-ingest python main.py --data-dir /app/data --triple-workers 4 --embed-workers 4
```

The image sets `WORKDIR` and `PYTHONPATH` to `/app`. The default image `CMD` is `python main.py --help`; override it by passing `python main.py ...` as the container command (as above).

**Ollama on the host:** from inside the container, use the host’s Ollama URL, for example:

```bash
docker run --rm \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/cache:/app/cache" \
  --env-file .env \
  rag-ingest python main.py --data-dir /app/data --triple-workers 4 --embed-workers 4
```

On **Linux** without Docker Desktop, add `--add-host=host.docker.internal:host-gateway` so `host.docker.internal` resolves.

**EPUB:** Docling is driven via merged HTML in `cache/epub_html/` (see `src/epub_to_html.py`).

---

## 🧪 Usage

### Run the main RAG pipeline

Run from the `RAG_ingest/` directory:

```bash
python main.py --triple-workers 4 --embed-workers 4 --index-name <>
```

#### Arguments

| Argument | Type | Default | Description |
|---|---|---|---|
| `--data-dir` | str | `None` | Path to a directory of PDFs to ingest |
| `--pdf` | str | `None` | Path to a single PDF file to ingest |
| `--index-name` | str | `PINECONE_INDEX` | Pinecone index name to write vectors to |
| `--namespace` | str | `PINECONE_NAMESPACE` | Pinecone namespace |
| `--no-pinecone` | flag | `False` | Skip Pinecone vector upsert |
| `--no-neo4j` | flag | `False` | Skip Neo4j knowledge graph ingestion |
| `--neo4j-mode` | `local`/`cloud` | `local` | Use local Neo4j instance or AuraDB cloud |
| `--neo4j-database` | str | `None` | Target Neo4j database name |
| `--neo4j-start-chunk` | int | `0` | Resume ingestion from a specific chunk index |
| `--neo4j-progress-file` | str | `None` | File path to save/resume ingestion progress |
| `--neo4j-batch-size` | int | `NEO4J_BATCH_SIZE` | Number of triples per Neo4j batch write |
| `--triple-workers` | int | `TRIPLE_WORKERS` | Parallel workers for triple extraction |
| `--embed-workers` | int | `EMBED_WORKERS` | Parallel workers for embedding generation |
| `--fast-embeddings` | flag | `False` | Use faster (lower-quality) embedding mode |
| `--compare-strategies` | flag | `False` | Run and compare multiple chunking strategies |

#### Run Examples

**Basic ingestion with parallelism:**
```bash
python main.py --triple-workers 4 --embed-workers 4
```

**Ingest a single PDF:**
```bash
python main.py --pdf ./data/my_document.pdf --triple-workers 4 --embed-workers 4
```

**Ingest a directory of PDFs:**
```bash
python main.py --data-dir ./data --triple-workers 4 --embed-workers 4
```

**Ingest to a custom Pinecone index and Neo4j cloud database:**
```bash
python main.py --triple-workers 4 --embed-workers 4 \
               --index-name all-frameworks-v1 \
               --neo4j-database all-frameworks-v1 \
               --neo4j-mode cloud
```

**Skip vector DB and only populate knowledge graph:**
```bash
python main.py --no-pinecone --neo4j-mode cloud --triple-workers 4
```

**Resume an interrupted ingestion from chunk 150:**
```bash
python main.py --neo4j-start-chunk 150 --neo4j-progress-file progress.json
```

**Compare chunking strategies:**
```bash
python main.py --compare-strategies --triple-workers 2 --embed-workers 2
```

---

### Run the AI coaching interface
```bash
python ai_coach_v4.py
```

### Run retrieval queries
```bash
python retrieval_query.py
```

### `chunk_texts/` details and retrieval linkage

During ingest, each PDF is chunked and written to:

`chunk_texts/<pdf_stem>_chunks.json`

Each chunk entry carries a stable `chunk_id` plus framework metadata (`framework`, `short_name`, `themes`, `best_for`) and the chunk text used for embedding/triple generation.

How this connects to retrieval:

- **Pinecone index match:** vectors are upserted with IDs in the form  
  `"<pdf_name>_chunk_<chunk_id>"`, and metadata includes the same `chunk_id` + framework fields. Retrieval hits from Pinecone therefore map back directly to the chunk record in `chunk_texts/`.
- **KG match (Neo4j):** the same chunk is written as a `Chunk` node (via `chunk_node_id`) with identical framework metadata, and chunk-derived triples are attached to that node.
- **End-to-end behavior:** retrieval first returns semantically similar chunks (Pinecone), then uses framework-aware graph context from KG (Neo4j), both grounded on the same ingest-time chunk identity.

### Run individual files

#### Ingest and chunk documents
```bash
python document_extractor.py
python Chunk.py          # Basic chunking
python HybridChunker.py  # Hybrid chunking strategy
```

---

## ⚙️ Configuration — `ingest/config.py`

All environment variables and runtime constants are managed in a single place: `ingest/config.py`. No other module calls `os.getenv()` directly. You can configure the pipeline either via a `.env` file in the project root or by exporting environment variables in your shell.

### LLM Client Switch

Controls which LLM backend is used for triple extraction and embeddings:

```env
LLM_CLIENT_SWITCH=ollama        # Local inference via Ollama (default)
LLM_CLIENT_SWITCH=huggingface   # Remote HuggingFace Inference API
LLM_CLIENT_SWITCH=sagemaker     # AWS SageMaker endpoint
```

### Ollama (Local)

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=nomic-embed-text:latest
OLLAMA_TRIPLE_MODEL=qwen2.5:7b-instruct
EMBED_MAX_TOKENS=8000
TRIPLE_TIMEOUT=45
```

### HuggingFace / SageMaker (Remote)

```env
HUGGING_FACE_API_KEY=your_hf_key
HUGGING_FACE_EMBED_MODEL=sentence-transformers/multi-qa-mpnet-base-dot-v1
SAGEMAKER_EMBED_ENDPOINT=your_sagemaker_embed_endpoint
SAGEMAKER_LLM_ENDPOINT=your_sagemaker_llm_endpoint
```

### Pinecone (Vector Store)

```env
PINECONE_API_KEY=your_pinecone_key
PINECONE_ENVIRONMENT=us-east-1
PINECONE_INDEX_NAME=rag-ingest-test-chunksize
PINECONE_NAMESPACE=documents
```

### Neo4j — Local vs Cloud Mode

Switch between a local Neo4j instance and AuraDB cloud using `--neo4j-mode` at runtime, or pre-configure both sets of credentials:

```env
# Local Neo4j
LOCAL_NEO4J_URI=bolt://localhost:7687
LOCAL_NEO4J_USERNAME=neo4j
LOCAL_NEO4J_PASSWORD=your_local_password
LOCAL_NEO4J_DATABASE=neo4j

# Cloud / AuraDB
NEO4J_URI=neo4j+s://your-aura-instance.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_cloud_password
NEO4J_DATABASE=neo4j
```

Then select at runtime:
```bash
python main.py --neo4j-mode local    # uses LOCAL_NEO4J_* vars
python main.py --neo4j-mode cloud    # uses NEO4J_* (AuraDB) vars
```

### Chunking Parameters

```env
CHUNK_BASE_SIZE=1024             # Target chunk size in tokens
CHUNK_OVERLAP_SIZE=64            # Overlap between consecutive chunks
CHUNK_SEMANTIC_THRESHOLD=0.5     # Similarity threshold for semantic splitting
CHUNK_STRUCT_MIN_TOKENS=300      # Minimum tokens for structural chunks
CHUNK_STRUCT_MAX_TOKENS=700      # Maximum tokens for structural chunks
CHUNK_EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

### Parallelism

```env
TRIPLE_WORKERS=6     # Parallel workers for LLM triple extraction
EMBED_WORKERS=6      # Parallel workers for embedding generation
NEO4J_BATCH_SIZE=50  # Triples written to Neo4j per batch
```

### Default Mode (Debug / Low-Resource)

Set `DEFAULT_MODE=true` to run in a safe single-threaded mode — useful for debugging or running on low-resource machines:

```env
DEFAULT_MODE=true   # Forces TRIPLE_WORKERS=1, EMBED_WORKERS=1, TRIPLE_BATCH_SIZE=10
DEFAULT_MODE=false  # Full parallel mode (default)
```

### Logging

```env
RAG_LOG_TO_CONSOLE=true    # Stream logs to stdout (default)
RAG_LOG_TO_CONSOLE=false   # Write logs to file instead
```

---

## 🧠 Key Components

### Chunking Strategies
- **`Chunk.py`** — Standard fixed-size or sentence-based text chunking.
- **`HybridChunker.py`** — Combines multiple chunking strategies (e.g., semantic + fixed-size) for better retrieval performance.

### Knowledge Graph
- **`KG.py`** — Builds and queries a knowledge graph to augment retrieval with structured relational data.

### AI Coach Interface
- ai_coach_v4.py - AI powered coaching assistant that uses RAG to answer questions from ingested documents.

---

## 📄 Sample Data

The repo includes 3 PDF as a sample document to test ingestion, chunking, and retrieval pipelines end-to-end. See data folder. 

---

## 🛠️ Tech Stack

- **Language:** Python
- **LLM:** Anthropic Claude (via API)
- **RAG Framework:** LightRAG + custom pipeline
- **Document Processing:** PDF extraction, chunking, JSON/plain text conversion
- **Knowledge Graph:** Custom KG integration (`KG.py`)

---

## 📝 Notes

- This repository is primarily for **testing and experimentation** with RAG techniques.
- Multiple versioned files (e.g., `ai_coach_v4.py`, `v4.5`, `v4.8`) reflect iterative development — use the latest version for the most up-to-date behavior.
- The `cache/` folder stores intermediate results to speed up repeated runs.

---



