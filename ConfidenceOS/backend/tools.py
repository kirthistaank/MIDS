"""
tools.py — all LangGraph tools with full logging and retrieval tracing.
Every Pinecone chunk and AuraDB node retrieved is logged so you can
tell exactly whether the LLM used retrieved knowledge or generated it.
"""

import json
import os
import glob
import requests

from langchain_core.tools import tool
from pinecone import Pinecone
from neo4j import GraphDatabase

import config
from logger import get_logger

log = get_logger(__name__)

# ── Pinecone singleton ────────────────────────────────────────────────────────

_pc    = None
_index = None

def _get_pinecone_index():
    global _pc, _index
    if _index is None:
        log.info("Initialising Pinecone client | index=%s", config.PINECONE_INDEX_NAME)
        try:
            _pc    = Pinecone(api_key=config.PINECONE_API_KEY)
            _index = _pc.Index(config.PINECONE_INDEX_NAME)
            log.info("Pinecone index ready")
        except Exception as e:
            log.error("Failed to initialise Pinecone: %s", e, exc_info=True)
            raise
    return _index


# ── Neo4j singleton ───────────────────────────────────────────────────────────

_neo4j_driver = None

def _get_neo4j_driver():
    global _neo4j_driver
    if _neo4j_driver is None:
        log.info("Initialising Neo4j driver | uri=%s", config.NEO4J_URI)
        try:
            _neo4j_driver = GraphDatabase.driver(
                config.NEO4J_URI,
                auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD),
            )
            log.info("Neo4j driver ready")
        except Exception as e:
            log.error("Failed to initialise Neo4j driver: %s", e, exc_info=True)
            raise
    return _neo4j_driver


# ── Chunk text loader ─────────────────────────────────────────────────────────

CHUNK_TEXTS_DIR = os.path.join(os.path.dirname(__file__), "..", "chunk_texts")
_chunk_cache: dict[str, dict] = {}

def _load_chunk_file(source_name: str) -> dict:
    if source_name in _chunk_cache:
        log.debug("Chunk cache hit | source=%s", source_name)
        return _chunk_cache[source_name]

    pattern = os.path.join(CHUNK_TEXTS_DIR, f"{source_name}_texts.json")
    matches = glob.glob(pattern)

    if not matches:
        all_files = glob.glob(os.path.join(CHUNK_TEXTS_DIR, "*.json"))
        matches   = [f for f in all_files if source_name.lower() in f.lower()]

    if not matches:
        log.warning("Chunk file not found | source=%s | pattern=%s", source_name, pattern)
        return {}

    log.debug("Loading chunk file | path=%s", matches[0])
    try:
        with open(matches[0], "r", encoding="utf-8") as f:
            data = json.load(f)

        normalized = {}
        for item in data:
            if isinstance(item, dict):
                chunk_num = item.get("chunk_id", "")
                text      = item.get("content") or item.get("text") or item.get("raw_text") or ""
                full_key  = f"{source_name}_chunk_{chunk_num}"
                normalized[full_key] = text

        _chunk_cache[source_name] = normalized
        log.info("Chunk file loaded | source=%s | chunks=%d", source_name, len(normalized))
        return normalized

    except Exception as e:
        log.error("Failed to load chunk file | source=%s | error=%s", source_name, e, exc_info=True)
        return {}


def _get_chunk_text(pinecone_id: str) -> str:
    if "_chunk_" not in pinecone_id:
        log.warning("Unrecognised chunk ID format | id=%s", pinecone_id)
        return "(chunk ID format not recognised)"

    source_name = pinecone_id.split("_chunk_")[0]
    chunks      = _load_chunk_file(source_name)
    text        = chunks.get(pinecone_id, "")

    if not text:
        log.warning("Chunk text not found | id=%s", pinecone_id)
        return f"(text not found for chunk: {pinecone_id})"

    return text


# ── Tool 1: Pinecone semantic search ──────────────────────────────────────────

@tool
def search_pinecone(query: str) -> str:
    """
    Search the Pinecone vector index for chunks most relevant to the query.
    Returns the top-3 text chunks with their similarity scores.
    Use this when the user asks a question that needs document/knowledge retrieval.
    """
    log.info("Pinecone search | query=%s", query)
    try:
        index = _get_pinecone_index()

        # Embed query
        log.debug("Embedding query via Ollama | model=nomic-embed-text")
        resp = requests.post(
            f"{config.OLLAMA_BASE_URL}/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": query},
            timeout=30,
        )
        resp.raise_for_status()
        embedding = resp.json()["embedding"]
        log.debug("Embedding generated | dim=%d", len(embedding))

        # Query Pinecone
        results = index.query(
            vector=embedding,
            top_k=3,
            include_metadata=True,
            namespace=config.PINECONE_NAMESPACE or None,
        )

        matches = results["matches"]
        if not matches:
            log.info("Pinecone returned no matches | query=%s", query)
            return "No relevant documents found in the knowledge base."

        log.info("Pinecone matched %d chunks | query=%s", len(matches), query)

        chunks = []
        for i, match in enumerate(matches, 1):
            chunk_id = match.id
            score    = round(match.score, 3)
            meta     = match.metadata or {}
            source   = meta.get("source", "Unknown source")
            title    = meta.get("title", "")
            themes   = meta.get("themes", [])
            best_for = meta.get("best_for", [])

            # ── Retrieval trace log ───────────────────────────────────────────
            log.info(
                "RETRIEVED CHUNK [%d/%d] | id=%s | source=%s | title=%s | score=%s | themes=%s | best_for=%s",
                i, len(matches), chunk_id, source, title or "—", score,
                ", ".join(themes[:3]) if themes else "—",
                ", ".join(best_for[:3]) if best_for else "—",
            )

            text   = _get_chunk_text(chunk_id)
            header = f"[{i}] {source}"
            if title:
                header += f" — {title}"
            header += f" (score={score})"
            chunks.append(f"{header}\n{text}")

        log.info("Pinecone search complete | chunks_returned=%d", len(chunks))
        return "\n\n".join(chunks)

    except requests.exceptions.RequestException as e:
        log.error("Embedding request failed | error=%s", e, exc_info=True)
        return f"Embedding failed: {e}"
    except Exception as e:
        log.error("Pinecone search failed | query=%s | error=%s", query, e, exc_info=True)
        return f"Pinecone search failed: {e}"


# ── Tool 2: AuraDB knowledge graph query ──────────────────────────────────────

@tool
def query_auradb(cypher_query: str) -> str:
    """
    Run a Cypher query against the Neo4j AuraDB knowledge graph.
    Use this when the user asks about relationships, entities, or graph-structured data.

    Graph schema:
    Node labels    : Chunk, Framework, Concept, Technique, Scenario, Emotion
    Relationships — EXACT valid patterns only:
      (Framework)-[:CONTAINS]->(Chunk)
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

    IMPORTANT naming: use full names e.g. 'Cognitive Behavior Therapy' not 'CBT'
    For partial matches: WHERE toLower(n.name) CONTAINS 'cbt'

    Valid example queries:
      MATCH (f:Framework) RETURN f.name LIMIT 10
      MATCH (f:Framework)-[:CONTAINS]->(c:Chunk) RETURN f.name, c.chunk_id LIMIT 5
      MATCH (c:Chunk)-[:USES]->(t:Technique) RETURN c.short_name, t.name LIMIT 5
      MATCH (c:Chunk)-[:APPLIES_TO]->(s:Scenario) RETURN c.short_name, s.name LIMIT 5
      MATCH (c:Chunk)-[:MENTIONS]->(con:Concept) RETURN c.short_name, con.name LIMIT 5
      MATCH (c:Chunk)-[:TRIGGERS]->(e:Emotion) RETURN c.short_name, e.name LIMIT 5
    """
    log.info("AuraDB query | cypher=%s", cypher_query)
    try:
        driver = _get_neo4j_driver()
        with driver.session() as session:
            result  = session.run(cypher_query)
            records = [dict(r) for r in result]

        if not records:
            log.info("AuraDB returned no results | cypher=%s", cypher_query)
            return (
                "Query returned no results. This is NOT an error — the data simply "
                "does not match. Try broadening the query or using a different property value. "
                "For example, use 'Cognitive Behavior Therapy' instead of 'CBT'."
            )

        # ── Retrieval trace log ───────────────────────────────────────────────
        log.info("RETRIEVED NODES | count=%d | cypher=%s", len(records), cypher_query)
        for i, record in enumerate(records[:5], 1):
            log.info("  NODE [%d] | %s", i, json.dumps(record, default=str))

        lines = [str(r) for r in records[:10]]
        log.info("AuraDB query complete | rows_returned=%d", len(lines))
        return "\n".join(lines)

    except Exception as e:
        log.error("AuraDB query failed | cypher=%s | error=%s", cypher_query, e, exc_info=True)
        return f"AuraDB query error: {type(e).__name__}: {e}"


# ── Tool 3: Weather ───────────────────────────────────────────────────────────

@tool
def get_weather(city: str) -> str:
    """Get the current weather for a given city (demo stub)."""
    log.info("Weather tool called | city=%s", city)
    fake_data = {
        "london":   "Cloudy, 12°C",
        "new york": "Sunny, 22°C",
        "tokyo":    "Rainy, 18°C",
    }
    result = fake_data.get(city.lower(), f"No weather data for '{city}'.")
    log.debug("Weather result | city=%s | result=%s", city, result)
    return result


# ── Tool 4: Hello ─────────────────────────────────────────────────────────────

@tool
def say_hello(name: str) -> str:
    """Say hello to someone by name."""
    log.info("Hello tool called | name=%s", name)
    return f"Hello, {name}! 👋 I'm ConfidenceOS, your interview confidence coach."


# ── Tool 5: Calculator ────────────────────────────────────────────────────────

@tool
def calculator(expression: str) -> str:
    """Evaluate a simple math expression like '2 + 2' or '10 * 5'."""
    log.info("Calculator tool called | expression=%s", expression)
    try:
        result = eval(expression, {"__builtins__": {}})
        log.debug("Calculator result | expression=%s | result=%s", expression, result)
        return f"{expression} = {result}"
    except Exception as e:
        log.warning("Calculator error | expression=%s | error=%s", expression, e)
        return f"Math error: {e}"


# ── Export ────────────────────────────────────────────────────────────────────

ALL_TOOLS = [search_pinecone, query_auradb, get_weather, say_hello, calculator]
