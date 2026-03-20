"""
tools.py — all LangGraph tools live here.
Each tool is a plain Python function decorated with @tool.
"""

from langchain_core.tools import tool
from pinecone import Pinecone
from neo4j import GraphDatabase
import config
import json
import os
import glob
import logging

logger = logging.getLogger(__name__)

# ── Pinecone client (lazy singleton) ──────────────────────────────────────────

_pc = None
_index = None

def _get_pinecone_index():
    global _pc, _index
    if _index is None:
        if not config.PINECONE_API_KEY:
            raise ValueError("PINECONE_API_KEY is missing")
        _pc    = Pinecone(api_key=config.PINECONE_API_KEY)
        _index = _pc.Index(config.PINECONE_INDEX_NAME)
    return _index


# ── Chunk text loader ─────────────────────────────────────────────────────────

# Path to chunk_texts folder — one level above backend/
CHUNK_TEXTS_DIR = os.path.join(os.path.dirname(__file__), "..", "chunk_texts")

# Cache loaded JSON files in memory so we don't re-read on every query
_chunk_cache: dict[str, dict] = {}

def _load_chunk_file(source_name: str) -> dict:
    """Load and cache the JSON file matching the source name.
    Handles both dict format {chunk_id: text} and list format [{id: ..., text: ...}]
    """
    if source_name in _chunk_cache:
        return _chunk_cache[source_name]

    pattern = os.path.join(CHUNK_TEXTS_DIR, f"{source_name}_texts.json")
    matches = glob.glob(pattern)

    if not matches:
        all_files = glob.glob(os.path.join(CHUNK_TEXTS_DIR, "*.json"))
        matches = [f for f in all_files if source_name.lower() in f.lower()]

    if not matches:
        return {}

    with open(matches[0], "r", encoding="utf-8") as f:
        data = json.load(f)

    # Normalize list format to dict keyed by full chunk ID
    # All files are lists: [{"chunk_id": N, "content": "text..."}, ...]
    normalized = {}
    for item in data:
        if isinstance(item, dict):
            chunk_num = item.get("chunk_id", "")
            text = item.get("content") or item.get("text") or item.get("raw_text") or ""
            full_key = f"{source_name}_chunk_{chunk_num}"
            normalized[full_key] = text
    data = normalized
    
    _chunk_cache[source_name] = data
    return data

def _get_chunk_text(pinecone_id: str) -> str:
    """
    Given a Pinecone ID like 'Cognitive Behavior Therapy - Basics and Beyond_chunk_150',
    extract the source name, load the right JSON file, and return the chunk text.
    """
    # Split on '_chunk_' to get source name
    if "_chunk_" not in pinecone_id:
        return "(chunk ID format not recognized)"

    source_name = pinecone_id.split("_chunk_")[0]
    chunks = _load_chunk_file(source_name)

    # The key in the JSON is the full Pinecone ID
    text = chunks.get(pinecone_id, "")
    if not text:
        return f"(text not found for chunk: {pinecone_id})"
    return text


# ── Neo4j driver (lazy singleton) ─────────────────────────────────────────────

_neo4j_driver = None

def _get_neo4j_driver():
    global _neo4j_driver
    if _neo4j_driver is None:
        if not config.NEO4J_URI:
            raise ValueError("NEO4J_URI is missing. Set it in backend/.env")
        if not config.NEO4J_USERNAME:
            raise ValueError("NEO4J_USERNAME is missing. Set it in backend/.env")
        if not config.NEO4J_PASSWORD:
            raise ValueError("NEO4J_PASSWORD is missing. Set it in backend/.env")
        
        _neo4j_driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD),
        )
    return _neo4j_driver


# ── Tool 1: Pinecone semantic search ──────────────────────────────────────────

@tool
def search_pinecone(query: str) -> str:
    """
    Search the Pinecone vector index for chunks most relevant to the query.
    Returns the top-3 text chunks with their similarity scores.
    Use this when the user asks a question that needs document/knowledge retrieval.
    """
    try:
        import requests
        index = _get_pinecone_index()

        # Embed the query using the configured embedding model.
        resp = requests.post(
            f"{config.OLLAMA_BASE_URL}/api/embeddings",
            json={"model": config.EMBED_MODEL, "prompt": query},
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        embedding = payload.get("embedding")
        if not embedding:
            return f"Pinecone search failed: embedding response missing vector: {payload}"

        results = index.query(
            vector=embedding,
            top_k=3,
            include_metadata=True,
            namespace=config.PINECONE_NAMESPACE or None,
        )

        matches = results["matches"]
        if not matches:
            return "No relevant documents found in the knowledge base."

        chunks = []
        for i, match in enumerate(matches, 1):
            chunk_id = match.id
            score    = round(match.score, 3)
            meta     = match.metadata or {}

            source = meta.get("source", "Unknown source")
            title  = meta.get("title", "")

            text = _get_chunk_text(chunk_id)

            header = f"[{i}] {source}"
            if title:
                header += f" — {title}"
            header += f" (score={score})"
            chunks.append(f"{header}\n{text}")

        return "\n\n".join(chunks)

    except Exception as e:
        logger.exception("search_pinecone failed")
        return f"Pinecone search failed: {e}"


# ── Tool 2: AuraDB knowledge graph query ──────────────────────────────────────

@tool
def query_auradb(cypher_query: str) -> str:
    """
    Run a Cypher query against the Neo4j AuraDB knowledge graph.
    Use this when the user asks about relationships, entities, or graph-structured data.

    Graph schema:
    Node labels    : Chunk, Framework, Concept, Technique, Scenario, Emotion
    Relationships  : (Framework)-[:CONTAINS]->(Chunk)
                     (Chunk)-[:USES]->(Technique)
                     (Chunk)-[:APPLIES_TO]->(Scenario)
                     (Chunk)-[:TRIGGERS]->(Emotion)
                     (Chunk)-[:MENTIONS]->(Concept)

    Node properties:
      Framework : name (e.g. 'CBT', 'Cognitive Behavior Therapy')
      Chunk     : chunk_id, pdf_name, framework, short_name, themes, best_for
      Concept   : name
      Technique : name
      Scenario  : name
      Emotion   : name

    IMPORTANT naming conventions in this graph:
      - Framework names use full names: 'Cognitive Behavior Therapy', NOT 'CBT'
      - Use case-insensitive search when unsure: WHERE toLower(n.name) CONTAINS 'cbt'
      - For partial matches use: WHERE n.name =~ '(?i).*cbt.*'
      - NEVER use 'f CONTAINS (c:Chunk)' — that is not valid Cypher
      - ALWAYS traverse relationships like: (a)-[:REL]->(b)
      - ALWAYS declare every variable in MATCH before using it in RETURN
      - ALWAYS end with LIMIT to cap results

    Valid example queries:
      MATCH (f:Framework) RETURN f.name LIMIT 10
      MATCH (f:Framework)-[:CONTAINS]->(c:Chunk) RETURN f.name, c.chunk_id LIMIT 5
      MATCH (c:Chunk)-[:USES]->(t:Technique) RETURN c.short_name, t.name LIMIT 5
      MATCH (c:Chunk)-[:APPLIES_TO]->(s:Scenario) RETURN c.short_name, s.name LIMIT 5
      MATCH (c:Chunk)-[:MENTIONS]->(con:Concept) RETURN c.short_name, con.name LIMIT 5
      MATCH (c:Chunk)-[:TRIGGERS]->(e:Emotion) RETURN c.short_name, e.name LIMIT 5
      MATCH (f:Framework)-[:CONTAINS]->(c:Chunk)-[:USES]->(t:Technique)
        RETURN f.name, t.name, count(c) AS usage ORDER BY usage DESC LIMIT 10
    """
    try:
        print(f"[AuraDB] Running Cypher: {cypher_query}")
        driver = _get_neo4j_driver()
        with driver.session() as session:
            result  = session.run(cypher_query)
            records = [dict(r) for r in result]

        print(f"[AuraDB] Raw records: {records}")
        if not records:
            return (
                "Query returned no results. "
                "This is NOT an error — the data simply does not match. "
                "Try broadening the query or using a different property value. "
                "For example, use 'Cognitive Behavior Therapy' instead of 'CBT'."
            )

        lines = []
        for r in records[:10]:
            lines.append(str(r))
        return "\n".join(lines)
    except Exception as e:
        logger.exception("query_auradb failed")
        err_type = type(e).__name__
        return (
            "AURADB_QUERY_FAILED\n"
            f"type={err_type}\n"
            f"message={e}\n"
            f"uri={config.NEO4J_URI or '(missing)'}\n"
            "hints=Check NEO4J_URI/NEO4J_USERNAME/NEO4J_PASSWORD, network access to Aura, and Cypher syntax."
        )




# ── Tool 3: Weather (kept from hello-world) ───────────────────────────────────

@tool
def get_weather(city: str) -> str:
    """Get the current weather for a given city (demo stub)."""
    fake_data = {
        "london":   "Cloudy, 12°C",
        "new york": "Sunny, 22°C",
        "tokyo":    "Rainy, 18°C",
    }
    return fake_data.get(city.lower(), f"No weather data for '{city}'.")


# ── Tool 4: Hello (kept from hello-world) ─────────────────────────────────────

@tool
def say_hello(name: str) -> str:
    """Say hello to someone by name."""
    return f"Hello, {name}! 👋 I'm your local AI assistant powered by Ollama."


# ── Tool 5: Calculator (kept from hello-world) ────────────────────────────────

@tool
def calculator(expression: str) -> str:
    """Evaluate a simple math expression like '2 + 2' or '10 * 5'."""
    try:
        result = eval(expression, {"__builtins__": {}})
        return f"{expression} = {result}"
    except Exception as e:
        return f"Math error: {e}"


# ── Export list (imported by agent.py) ────────────────────────────────────────

ALL_TOOLS = [search_pinecone, query_auradb, get_weather, say_hello, calculator]
