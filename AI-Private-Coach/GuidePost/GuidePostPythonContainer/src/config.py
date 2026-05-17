"""
ingest/config.py
All environment variables and constants in one place.
Nothing else in the package calls os.getenv() directly.
"""
import os
from dotenv import load_dotenv

load_dotenv()


# ── Ollama ────────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL     = os.getenv("OLLAMA_BASE_URL",    "http://localhost:11434")
OLLAMA_EMBED_MODEL  = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text:latest")
OLLAMA_TRIPLE_MODEL = os.getenv("OLLAMA_TRIPLE_MODEL","qwen2.5:3b-instruct")#mistral-small:latest
EMBED_MAX_TOKENS    = int(os.getenv("EMBED_MAX_TOKENS", "8000"))
TRIPLE_TIMEOUT      = int(os.getenv("TRIPLE_TIMEOUT",  "45"))

# ── HuggingFace (ready for migration) ────────────────────────────────────────
def _normalize_embed_model(name: str) -> str:
    """Strip quotes/whitespace and ensure full sentence-transformers/ model id."""
    if not name:
        return "sentence-transformers/multi-qa-mpnet-base-dot-v1"
    name = name.strip().strip('"').strip("'")
    if not name.startswith("sentence-transformers/"):
        name = f"sentence-transformers/{name}"
    return name


HF_API_KEY          = os.getenv("HUGGING_FACE_API_KEY", "")
HF_EMBED_MODEL      = _normalize_embed_model(os.getenv("HUGGING_FACE_EMBED_MODEL", "sentence-transformers/multi-qa-mpnet-base-dot-v1"))
HF_LLM_MODEL        = os.getenv("HUGGING_FACE_LLM_MODEL",  "Qwen/Qwen2.5-0.5B-Instruct")
# Populated when deployed to SageMaker
HF_EMBED_ENDPOINT   = os.getenv("SAGEMAKER_EMBED_ENDPOINT", "")
HF_LLM_ENDPOINT     = os.getenv("SAGEMAKER_LLM_ENDPOINT",   "")
# ── LLM Client Switch ────────────────────────────────────────────────────────
LLM_CLIENT_SWITCH = os.getenv("LLM_CLIENT_SWITCH", "huggingface") # Switch this if you want either ollama(local) or huggingface(remote) or sageaker(remote)


# ── Neo4j — local ─────────────────────────────────────────────────────────────
LOCAL_NEO4J_URI      = os.getenv("LOCAL_NEO4J_URI",      "")
LOCAL_NEO4J_USERNAME = os.getenv("LOCAL_NEO4J_USERNAME", "")
LOCAL_NEO4J_PASSWORD = os.getenv("LOCAL_NEO4J_PASSWORD", "")
LOCAL_NEO4J_DATABASE = os.getenv("LOCAL_NEO4J_DATABASE", "lightrag")

# ── Neo4j — cloud / AuraDB ───────────────────────────────────────────────────
CLOUD_NEO4J_URI      = os.getenv("NEO4J_URI",      "")
CLOUD_NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "")
CLOUD_NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
CLOUD_NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# ── Pinecone Config ──────────────────────────────────────────
PINECONE_API_KEY    = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "delete-test-rag-ingest-git") #cbt-lightrag,hg-qwen-index
PINECONE_REGION     = os.getenv("PINECONE_REGION", "us-east-1")
PINECONE_CLOUD     = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "documents")


# ── LightRAG / Ollama Config ─────────────────────────────────
WORKING_DIR  = "./"
OLLAMA_HOST  = os.getenv("OLLAMA_HOST", "http://localhost:11434")
# Do not use phi3 model as it is Intel/CUDA optimized and does not leverage Apple Silicon MPS well
# Do not use nomic-embed-text ollama._types.ResponseError: "nomic-embed-text:latest" does not support chat (status code: 400)

# Model used for Ingestion
TRIPLE_MODEL = os.getenv("TRIPLE_MODEL", "qwen2.5:3b-instruct")
INGEST_LLM_MODEL    = os.getenv("LLM_MODEL",   "qwen2.5:7b-instruct")#qwen2.5:3b-instruct,qwen2.5:1.5b-instruct,qwen2.5:1.5b-instruct
INGEST_EMBED_MODEL  = os.getenv("EMBED_MODEL", "mxbai-embed-large") #nomic-embed-text - gace some dimension issues
# Model used for Retrieval
RETRIEVAL_MODEL = os.getenv("RETRIEVAL_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")#Qwen/Qwen2.5-7B-Instruct #Qwen/Qwen2.5-1.5B-Instruct
RETRIEVAL_EMBED_MODEL = os.getenv("RETRIEVAL_EMBED_MODEL", "sentence-transformers/all-mpnet-base-v2")#sentence-transformers/all-MiniLM-L6-v2
# LightRAG worker timeout: LLM_TIMEOUT is the base (seconds); worker execution timeout = LLM_TIMEOUT * 2.
# Default 180 → worker timeout 360s. Increase if Ollama is slow (e.g. 300 → 600s worker timeout).
LLM_TIMEOUT  = int(os.getenv("LLM_TIMEOUT", "120"))
EMBEDDING_TIMEOUT = int(os.getenv("EMBEDDING_TIMEOUT", "60"))

EMBED_DIM = 1024   # nomic-embed-text outputs 768 dims, NOT 1024

COHERE_API_KEY    = os.getenv("COHERE_API_KEY")

# If you ever switch models, use these dims:
# nomic-embed-text       → 768
# mxbai-embed-large      → 1024
# all-minilm             → 384
# text-embedding-3-small → 1536  (OpenAI)

def neo4j_credentials(mode: str) -> tuple[str, str, str, str]:
    """Return (uri, username, password, database) for the given mode."""
    if mode.strip().lower() == "local":
        print("Using local Neo4j credentials")
        return LOCAL_NEO4J_URI, LOCAL_NEO4J_USERNAME, LOCAL_NEO4J_PASSWORD, LOCAL_NEO4J_DATABASE
    return CLOUD_NEO4J_URI, CLOUD_NEO4J_USERNAME, CLOUD_NEO4J_PASSWORD, CLOUD_NEO4J_DATABASE

# Replace the last line of your config.py:

# ❌ Old — hardcoded False, ignores env var
# SKIP_ON_TIMEOUT = False

# ✅ New — reads from environment, defaults True so timeouts are always skipped
SKIP_ON_TIMEOUT = os.getenv("SKIP_ON_TIMEOUT", "true").strip().lower() in ("1", "true", "yes")


# Chat with coach assistant enabled or disabled
CHAT_WITH_COACH_ASSISTANT = False