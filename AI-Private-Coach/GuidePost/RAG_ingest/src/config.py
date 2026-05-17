"""
src/config.py
All environment variables and constants in one place.
Nothing else in the package calls os.getenv() directly.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Ollama ────────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL     = os.getenv("OLLAMA_BASE_URL",    "http://localhost:11434")
OLLAMA_EMBED_MODEL  = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text:latest")
OLLAMA_TRIPLE_MODEL = os.getenv("OLLAMA_TRIPLE_MODEL","qwen2.5:7b-instruct")#mistral-small:latest
EMBED_MAX_TOKENS    = int(os.getenv("EMBED_MAX_TOKENS", "8000"))
TRIPLE_TIMEOUT      = int(os.getenv("TRIPLE_TIMEOUT",  "45"))

# ── HuggingFace (ready for migration) ────────────────────────────────────────
HF_API_KEY          = os.getenv("HUGGING_FACE_API_KEY", "")
HF_EMBED_MODEL      = os.getenv("HUGGING_FACE_EMBED_MODEL", "sentence-transformers/multi-qa-mpnet-base-dot-v1")
HF_LLM_MODEL        = os.getenv("HUGGING_FACE_LLM_MODEL",  "sentence-transformers/multi-qa-mpnet-base-dot-v1")
# Populated when deployed to SageMaker
HF_EMBED_ENDPOINT   = os.getenv("SAGEMAKER_EMBED_ENDPOINT", "")
HF_LLM_ENDPOINT     = os.getenv("SAGEMAKER_LLM_ENDPOINT",   "")
# ── LLM Client Switch ────────────────────────────────────────────────────────
LLM_CLIENT_SWITCH = os.getenv("LLM_CLIENT_SWITCH", "ollama") # Switch this if you want either ollama(local) or huggingface(remote) or sageaker(remote)

# ── Pinecone ─────────────────────────────────────────────────────────────────
PINECONE_API_KEY    = os.getenv("PINECONE_API_KEY") or os.getenv("PINECONE_API", "")
PINECONE_ENV        = os.getenv("PINECONE_ENVIRONMENT", "us-east-1")
PINECONE_INDEX      = os.getenv("PINECONE_INDEX_NAME",  "delete-test-rag-ingest-git")
PINECONE_NAMESPACE  = os.getenv("PINECONE_NAMESPACE",   "documents")

# ── Neo4j — local ─────────────────────────────────────────────────────────────
LOCAL_NEO4J_URI      = os.getenv("LOCAL_NEO4J_URI",      "")
LOCAL_NEO4J_USERNAME = os.getenv("LOCAL_NEO4J_USERNAME", "")
LOCAL_NEO4J_PASSWORD = os.getenv("LOCAL_NEO4J_PASSWORD", "")
LOCAL_NEO4J_DATABASE = os.getenv("LOCAL_NEO4J_DATABASE", "neo4j")

# ── Neo4j — cloud / AuraDB ───────────────────────────────────────────────────
CLOUD_NEO4J_URI      = os.getenv("NEO4J_URI",      "")
CLOUD_NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "")
CLOUD_NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
CLOUD_NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# ── Parallelism ───────────────────────────────────────────────────────────────
TRIPLE_WORKERS   = int(os.getenv("TRIPLE_WORKERS",    "6")) # default 4 
EMBED_WORKERS    = int(os.getenv("EMBED_WORKERS",     "6"))
NEO4J_BATCH_SIZE = int(os.getenv("NEO4J_BATCH_SIZE", "50"))

# ── Chunking ──────────────────────────────────────────────────────────────────
CHUNK_BASE_SIZE          = int(os.getenv("CHUNK_BASE_SIZE",           "1024")) # 196,608 words
CHUNK_OVERLAP_SIZE       = int(os.getenv("CHUNK_OVERLAP_SIZE",          "64"))
CHUNK_SEMANTIC_THRESHOLD = float(os.getenv("CHUNK_SEMANTIC_THRESHOLD",  "0.5"))
CHUNK_EMBED_MODEL        = os.getenv("CHUNK_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
CHUNK_STRUCT_MIN_TOKENS  = int(os.getenv("CHUNK_STRUCT_MIN_TOKENS", "300"))
CHUNK_STRUCT_MAX_TOKENS  = int(os.getenv("CHUNK_STRUCT_MAX_TOKENS", "700"))
CHUNKED_FOLDER_PATH        = "./chunk_texts"


def neo4j_credentials(mode: str) -> tuple[str, str, str, str]:
    """Return (uri, username, password, database) for the given mode."""
    if mode.strip().lower() == "local":
        return LOCAL_NEO4J_URI, LOCAL_NEO4J_USERNAME, LOCAL_NEO4J_PASSWORD, LOCAL_NEO4J_DATABASE
    return CLOUD_NEO4J_URI, CLOUD_NEO4J_USERNAME, CLOUD_NEO4J_PASSWORD, CLOUD_NEO4J_DATABASE

# ── Logging ──────────────────────────────────────────────────────────────────
# Set to True to log to console, False to log to file
# Default is True
RAG_LOG_TO_CONSOLE = os.getenv("RAG_LOG_TO_CONSOLE", "true")
if RAG_LOG_TO_CONSOLE.lower() in ("1", "true", "yes", "on"):
    LOG_TO_CONSOLE = True
else:
    LOG_TO_CONSOLE = False

# ── Default Mode ──────────────────────────────────────────────────────────────
# Set to True to use default mode, False to use custom mode
# Default is False
DEFAULT_MODE = os.getenv("DEFAULT_MODE", "false")
if DEFAULT_MODE.lower() in ("1", "true", "yes", "on"):
    DEFAULT_MODE = True
    TRIPLE_BATCH_SIZE = 10
    TRIPLE_WORKERS = 1
    EMBED_WORKERS = 1
else:
    DEFAULT_MODE = False
    TRIPLE_BATCH_SIZE = None