"""
src/huggingface_client.py

Hugging Face / SageMaker implementation of the LLM client interface.
Implements the same three functions as src/ollama_client.py:

    generate_embedding(text)  -> List[float]
    generate_triples(text)    -> List[Dict]
    health_check()            -> bool

This file is designed to work with either:
  - Hugging Face Inference API (using HF_API_KEY and model ids), or
  - custom endpoints (HF_EMBED_ENDPOINT / HF_LLM_ENDPOINT), e.g. SageMaker.
"""

from __future__ import annotations

import json
import re
import sys
from typing import List, Dict, Any, Optional

from sentence_transformers import SentenceTransformer
from transformers import AutoModelForCausalLM, AutoTokenizer

from src.config import (
    HF_LLM_MODEL,
    EMBED_MAX_TOKENS,
    TRIPLE_TIMEOUT,
)
from src.logging_utils import get_logger


_TRIPLE_PROMPT = """\
Extract CBT knowledge triples. Return ONLY a JSON array, no markdown, no explanation.
Schema: [{{"framework":"","concept":"","technique":"","scenario":"","emotion":""}}]
Text: {text}"""


_EMBED_MODEL_NAME = "sentence-transformers/multi-qa-mpnet-base-dot-v1"

_embed_model: Optional[SentenceTransformer] = None
_llm_model = None
_llm_tokenizer: Optional[AutoTokenizer] = None
log = get_logger(__name__)


def _get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        log.info(f"Loading embedding model '{_EMBED_MODEL_NAME}'...")
        _embed_model = SentenceTransformer(_EMBED_MODEL_NAME)
    return _embed_model


def _get_llm():
    """
    Load a local Hugging Face causal LM for triple generation.
    Uses HF_LLM_MODEL from config as the model id.
    """
    global _llm_model, _llm_tokenizer
    if _llm_model is None or _llm_tokenizer is None:
        if not HF_LLM_MODEL:
            raise RuntimeError("HF_LLM_MODEL is not configured.")
        log.info(f"Loading LLM '{HF_LLM_MODEL}'...")
        _llm_tokenizer = AutoTokenizer.from_pretrained(HF_LLM_MODEL)
        _llm_model = AutoModelForCausalLM.from_pretrained(HF_LLM_MODEL)
    return _llm_model, _llm_tokenizer


def health_check() -> bool:
    """
    Verify that local Hugging Face models can be loaded before the pipeline starts.
    We try to instantiate both the embedding model and the LLM.
    """
    try:
        _ = _get_embed_model()
        _ = _get_llm()
        log.info("Local Hugging Face models loaded.")
        return True
    except Exception as e:
        log.error(f"Failed to load local Hugging Face models: {e}")
        return False


def generate_embedding(text: str) -> List[float]:
    """
    Return an embedding vector for text using a local SentenceTransformer model.
    Model: sentence-transformers/multi-qa-mpnet-base-dot-v1
    """
    if len(text) > EMBED_MAX_TOKENS:
        text = text[:EMBED_MAX_TOKENS]

    try:
        model = _get_embed_model()
        emb = model.encode(text)
        # SentenceTransformer returns numpy arrays; convert to list for JSON-serializable storage.
        return emb.tolist() if hasattr(emb, "tolist") else list(emb)
    except Exception as e:
        log.error(f"generate_embedding (HF local) error: {e}")
        raise


def generate_triples(chunk_text: str) -> List[Dict[str, Any]]:
    """
    Extract structured knowledge triples from a chunk of text using a local HF LLM.
    Returns a list of dicts with keys: framework, concept, technique, scenario, emotion.
    Returns [] on any failure — never raises.
    """
    try:
        model, tokenizer = _get_llm()
    except Exception as e:
        log.error(f"HF local LLM not available: {e}")
        return []

    try:
        prompt = _TRIPLE_PROMPT.format(text=chunk_text)
        inputs = tokenizer(prompt, return_tensors="pt")
        output_ids = model.generate(
            **inputs,
            max_new_tokens=512,
            do_sample=False,
            temperature=0.0,
        )
        # Decode only the newly generated tokens
        generated = tokenizer.decode(
            output_ids[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True,
        )
    except Exception as e:
        log.error(f"HF local triple gen failed: {e}")
        return []

    return _parse_triples_json(str(generated).strip())


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
    return "".join(" " if ord(c) < 32 and c != " " else c for c in s)


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
        log.info(f"HF triples parsed: {triples}")
        return [triples] if isinstance(triples, dict) else triples
    except json.JSONDecodeError as e:
        log.warning(f"Failed to parse HF triples JSON: {e}")
        #log.warning(f"JSON string: {json_str}")
        return []

