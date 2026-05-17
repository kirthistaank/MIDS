# RAG_ingest — build from this folder (guidepost/RAG_ingest):
#   docker build -t rag-ingest .
#
# Run pipeline (mount your PDFs/EPUBs and env for cloud APIs):
#   docker run --rm \
#     -v "$(pwd)/data:/app/data" \
#     -v "$(pwd)/cache:/app/cache" \
#     -v "$(pwd)/chunk_texts:/app/chunk_texts" \
#     --env-file .env \
#     rag-ingest python main.py --data-dir /app/data --triple-workers 4 --embed-workers 4
#
# EPUBs are converted to merged HTML under cache/epub_html/ before Docling; if Docling
# returns nothing, plain text is taken from that HTML (see src/epub_to_html.py).

FROM python:3.11-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# poppler: some PDF stacks; libgl/glib: common ML/doc tooling wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# Override with real arguments (Ollama/HF/Pinecone/Neo4j as in your .env).
CMD ["python", "main.py", "--help"]
