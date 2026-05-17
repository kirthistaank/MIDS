"""
src/ollama_client.py

All Ollama communication: embeddings, triple generation, and health check.

To migrate to HuggingFace/SageMaker:
  1. Create src/huggingface_client.py with the same three functions:
       generate_embedding(text)  -> List[float]
       generate_triples(text)    -> List[Dict]
       health_check()            -> bool
  2. In main.py change:
       from src.ollama_client import ...
     to:
       from src.huggingface_client import ...
  Nothing else needs to change.
"""
import re
import sys
import json
import requests
from typing import List, Dict, Any, Optional

from src.config import (
    OLLAMA_BASE_URL,
    OLLAMA_EMBED_MODEL,
    OLLAMA_TRIPLE_MODEL,
    EMBED_MAX_TOKENS,
    TRIPLE_TIMEOUT,
)
from src.logging_utils import get_logger

log = get_logger(__name__)


_TRIPLE_PROMPT = """\
Extract CBT knowledge triples. Return ONLY a JSON array, no markdown, no explanation.
Schema: [{{"framework":"","concept":"","technique":"","scenario":"","emotion":""}}]
Text: {text}"""


def health_check() -> bool:
    """Verify Ollama is reachable and responding before the pipeline starts."""
    log.info("Checking Ollama server...")
    try:
        requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5).raise_for_status()
        log.info(f"Ollama reachable at {OLLAMA_BASE_URL}")
        # We only check reachability here. Model-specific /api/generate errors
        # (e.g. missing model) are handled later in generate_triples().
        return True
    except requests.exceptions.RequestException as e:
        log.error(f"Ollama unreachable: {e}")
        return False


def generate_embedding(text: str) -> List[float]:
    """Return an embedding vector for text using the configured Ollama embed model."""
    if len(text) > EMBED_MAX_TOKENS:
        text = text[:EMBED_MAX_TOKENS]
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/embeddings",
            json={"model": OLLAMA_EMBED_MODEL, "prompt": text},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]
    except Exception as e:
        log.error(f"generate_embedding error: {e}")
        raise


def generate_triples(chunk_text: str) -> List[Dict[str, Any]]:
    """
    Extract structured knowledge triples from a chunk of text.
    Returns a list of dicts with keys: framework, concept, technique, scenario, emotion.
    Returns [] on any failure — never raises.
    """
    try:
        log.debug("*" * 50)
        log.debug("Info for request POST")
        log.debug(f"OLLAMA BASE URL is: {OLLAMA_BASE_URL}")
        log.debug(f"OLLAMA TRIPLE MODEL is: {OLLAMA_TRIPLE_MODEL}")
        log.debug(f"OLLAMA TRIPLE PROMPT is: {_TRIPLE_PROMPT.format(text=chunk_text)}")
        log.debug(f"OLLAMA TRIPLE TIMEOUT is: {TRIPLE_TIMEOUT}")
        log.debug("*" * 50)
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model":  OLLAMA_TRIPLE_MODEL,
                "prompt": _TRIPLE_PROMPT.format(text=chunk_text),
                "stream": False,
                "options": {"temperature": 0, "num_predict": 512, "top_k": 1},
            },
            timeout=TRIPLE_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        log.warning(f"Triple gen timed out after {TRIPLE_TIMEOUT}s — skipping chunk")
        return []
    except Exception as e:
        log.error(f"Triple gen failed: {e}")
        return []

    return _parse_triples_json(resp.json().get("response", "").strip())


def _extract_first_json_array(s: str) -> Optional[str]:
    """Find the first '[' and return the substring up to the matching ']' (bracket-balanced)."""
    i = s.find("[")
    if i == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for j in range(i, len(s)):
        c = s[j]
        if escape:
            escape = False
            continue
        if in_string:
            if c == "\\":
                escape = True
            elif c == '"':
                in_string = False
            continue
        if c == '"':
            in_string = True
        elif c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return s[i : j + 1]
    return None


def _sanitize_json_string(s: str) -> str:
    """Replace ASCII control characters that break JSON parsing (e.g. literal newlines in strings)."""
    return "".join(
        " " if ord(c) < 32 and c != " " else c for c in s
    )


def _parse_triples_json(raw: str) -> List[Dict[str, Any]]:
    """Extract and parse a JSON array from raw LLM output. Tolerates extra text and control chars."""
    if not raw:
        return []
    raw = raw.strip()
    # Strip markdown code fence if present
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw).strip()
    # Extract only the first complete [...] to avoid "Extra data" when LLM returns multiple arrays
    json_str = _extract_first_json_array(raw)
    if json_str is None:
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        json_str = match.group(0) if match else raw
    json_str = _sanitize_json_string(json_str)
    try:
        triples = json.loads(json_str)
        log.info(f"Triples parsed: {triples}")
        return [triples] if isinstance(triples, dict) else triples
    except json.JSONDecodeError as e:
        log.warning(f"Failed to parse triples JSON: {e}")
        log.warning(f"JSON string: {json_str}")
        raise