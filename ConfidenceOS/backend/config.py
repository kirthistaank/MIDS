"""
config.py — single source of truth for all env variables.
All other modules import from here; nothing touches os.environ directly.
"""

import os
from dotenv import load_dotenv

load_dotenv()   # reads .env from project root

# ── Ollama ────────────────────────────────────────────
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL:    str = os.getenv("OLLAMA_MODEL",    "qwen2.5:7b-instruct")
EMBED_MODEL:     str = os.getenv("EMBED_MODEL",     "nomic-embed-text")

# ── Pinecone ──────────────────────────────────────────
PINECONE_API_KEY:    str = os.getenv("PINECONE_API_KEY",    "")
PINECONE_INDEX_NAME: str = os.getenv("PINECONE_INDEX_NAME", "delete-test-rag-ingest-git")
PINECONE_NAMESPACE:  str = os.getenv("PINECONE_NAMESPACE",  "documents")

# ── Neo4j AuraDB ──────────────────────────────────────
NEO4J_URI:      str = os.getenv("NEO4J_URI",      "")
NEO4J_USERNAME: str = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")

# ── App ───────────────────────────────────────────────
APP_HOST:     str = os.getenv("APP_HOST",     "0.0.0.0")
APP_PORT:     int = int(os.getenv("APP_PORT", "8000"))
CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

# ── Agent behavior ────────────────────────────────────
SYSTEM_PROMPT: str = os.getenv(
    "SYSTEM_PROMPT",
    (
        "You are a concise research assistant. "
        "Use tools when needed for factual grounding. "
        "If a tool fails, state that clearly and continue with best effort. "
        "Cite retrieved evidence briefly and avoid fabricating facts."
    ),
)
