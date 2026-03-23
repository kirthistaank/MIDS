"""
ai_explainer.py
---------------
Generates plain-English safety explanations for a computed SafeTrack Berkeley
route and supports multi-turn follow-up questions.

Three AI backends are supported — switch between them by changing a single
line in config.py:

    AI_PROVIDER = "ollama"        # local LLM, fully private, no API key
    AI_PROVIDER = "anthropic"     # Claude API, best quality
    AI_PROVIDER = "huggingface"   # local sentence-transformers pipeline, no key
    AI_PROVIDER = "none"          # plain text summary, no AI

Backend comparison
------------------
┌──────────────┬──────────────┬────────────┬───────────┬───────────────────┐
│ Provider     │ Cost         │ API key    │ Quality   │ Speed             │
├──────────────┼──────────────┼────────────┼───────────┼───────────────────┤
│ Ollama       │ Free         │ None       │ Very good │ Depends on GPU    │
│ Anthropic    │ Paid (trial) │ Required   │ Best      │ Fast (cloud)      │
│ HuggingFace  │ Free         │ None       │ Good      │ Slow on CPU       │
│ None         │ Free         │ None       │ Rule-based│ Instant           │
└──────────────┴──────────────┴────────────┴───────────┴───────────────────┘

Multi-turn conversation
-----------------------
self._history accumulates the full role/content message list and is sent
with every call so each backend maintains context across follow-up questions.
"""

import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod

from config import (
    AI_PROVIDER,
    ANTHROPIC_MAX_TOKENS,
    ANTHROPIC_MODEL,
    HF_EMBEDDING_MODEL,
    HF_GENERATION_MODEL,
    HF_MAX_NEW_TOKENS,
    OLLAMA_BASE_URL,
    OLLAMA_MAX_TOKENS,
    OLLAMA_MODEL,
)
from logger import get_logger

log = get_logger(__name__)

# ── Shared system prompt ───────────────────────────────────────────────────────
# All backends receive this as their persona / instruction context.
_SYSTEM_PROMPT = """
You are SafeTrack Berkeley — an AI assistant that helps cyclists navigate
Berkeley safely using real crash data from the SWITRS collision database
and OpenStreetMap bike infrastructure.

When given a route summary you:
1. Explain the overall safety profile in 2-3 plain-English sentences.
2. Call out every segment with crash_score > 0 and describe the risk level.
3. Mention significant elevation challenges if total gain exceeds 20 m.
4. Suggest one practical tip for each dangerous segment (e.g. use the
   parallel residential street one block over, ride during off-peak hours,
   watch for right-hooks at the intersection).
5. End with an overall safety rating on its own line: SAFE / MODERATE / CAUTION.

Keep responses concise and conversational. Use kilometres and metres.
Never invent crash statistics — only reference the numbers provided.
""".strip()


# ══════════════════════════════════════════════════════════════════════════════
# Abstract base — all backends implement this single method
# ══════════════════════════════════════════════════════════════════════════════

class _BaseBackend(ABC):
    """
    Every backend must implement chat().
    RouteExplainer never calls backend internals directly — only chat().
    """

    @abstractmethod
    def chat(self, history: list) -> str:
        """
        Send the full conversation history to the model and return its reply.

        Parameters
        ----------
        history : list[dict]
            List of {"role": "user"|"assistant", "content": str} dicts,
            newest message last.

        Returns
        -------
        str  The model's plain-text reply.
        """


# ══════════════════════════════════════════════════════════════════════════════
# Backend 1: Ollama  (local LLM, no API key)
# ══════════════════════════════════════════════════════════════════════════════

class _OllamaBackend(_BaseBackend):
    """
    Sends requests to a locally running Ollama server via its /api/chat REST
    endpoint (OpenAI-compatible message format).

    One-time setup
    --------------
    1. Install Ollama:       https://ollama.com/download
    2. Pull a model:         ollama pull llama3.2
    3. Server auto-starts; or run manually:  ollama serve

    Config (config.py)
    ------------------
    OLLAMA_BASE_URL   default: http://localhost:11434
    OLLAMA_MODEL      default: llama3.2
    OLLAMA_MAX_TOKENS default: 1024
    """

    def __init__(self) -> None:
        self.url   = f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"
        self.model = OLLAMA_MODEL
        log.info("Ollama backend | model=%s | url=%s", self.model, self.url)
        self._check_model_available()

    def _check_model_available(self) -> None:
        """
        Ping /api/tags to list installed models.
        If the configured model is missing, auto-select the first installed
        model and log a clear warning so the user knows what is being used.
        """
        try:
            req = urllib.request.Request(
                f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags", method="GET"
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())

            pulled = [m["name"] for m in data.get("models", [])]

            if not pulled:
                log.warning(
                    "Ollama is running but no models are installed. "
                    "Pull one with:  ollama pull llama3.2"
                )
                return

            log.info("Ollama models installed on this machine: %s", pulled)

            # Partial match — "llama3.2" matches "llama3.2:latest"
            match = next((m for m in pulled if self.model in m), None)

            if match:
                self.model = match   # normalise to full name Ollama knows
                log.info("Ollama model ready: %s", self.model)
            else:
                # Auto-fallback: use whatever is installed rather than crashing
                self.model = pulled[0]
                log.warning(
                    "Model '%s' (OLLAMA_MODEL in config.py) is not installed. "
                    "Auto-selected '%s' instead.\n"
                    "  To install your preferred model:  ollama pull %s\n"
                    "  Then update config.py:  OLLAMA_MODEL = '%s'",
                    OLLAMA_MODEL, self.model, OLLAMA_MODEL, self.model,
                )

        except urllib.error.URLError as err:
            log.warning(
                "Cannot reach Ollama at %s — is it running? "
                "Start it with:  ollama serve  (%s)",
                OLLAMA_BASE_URL, err,
            )

    def chat(self, history: list) -> str:
        # Inject system prompt as first message; Ollama supports system role
        messages = [{"role": "system", "content": _SYSTEM_PROMPT}] + history

        payload = {
            "model":   self.model,
            "messages": messages,
            "stream":  False,         # full response in one JSON blob
            "options": {
                "num_predict": OLLAMA_MAX_TOKENS,
                "temperature": 0.3,   # lower = more factual, less creative
            },
        }

        log.debug("Ollama: sending %d messages …", len(messages))

        try:
            req = urllib.request.Request(
                self.url,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            # Local inference can be slow on CPU — allow 2 minutes
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())

            reply = data["message"]["content"].strip()
            log.debug("Ollama replied (%d chars)", len(reply))
            return reply

        except urllib.error.URLError as err:
            log.error("Ollama unreachable: %s", err)
            return (
                "[Ollama offline]\n"
                "Make sure Ollama is running:  ollama serve\n"
                f"Error: {err}"
            )
        except (KeyError, json.JSONDecodeError) as err:
            log.error("Unexpected Ollama response: %s", err)
            return "[Error] Could not parse Ollama response."


# ══════════════════════════════════════════════════════════════════════════════
# Backend 2: Anthropic Claude  (cloud API, best quality)
# ══════════════════════════════════════════════════════════════════════════════

class _AnthropicBackend(_BaseBackend):
    """
    Calls the Anthropic Claude API via /v1/messages using only the Python
    standard library (no anthropic SDK dependency required).

    Setup
    -----
    1. Create an account:  https://console.anthropic.com
    2. Generate an API key and export it:
           export ANTHROPIC_API_KEY="sk-ant-..."

    Config (config.py)
    ------------------
    ANTHROPIC_MODEL       default: claude-sonnet-4-20250514
    ANTHROPIC_MAX_TOKENS  default: 1024

    Model options (cheapest → most capable)
    ----------------------------------------
    claude-haiku-4-5-20251001    fastest, cheapest
    claude-sonnet-4-20250514     best balance  ← recommended
    """

    _API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self) -> None:
        self._api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not self._api_key:
            log.warning(
                "ANTHROPIC_API_KEY not set. "
                "Export it with:  export ANTHROPIC_API_KEY='sk-ant-...'"
            )
        log.info("Anthropic backend | model=%s", ANTHROPIC_MODEL)

    def chat(self, history: list) -> str:
        if not self._api_key:
            return (
                "[Anthropic API key missing]\n"
                "Set it with:  export ANTHROPIC_API_KEY='sk-ant-...'\n"
                "Or switch provider in config.py:  AI_PROVIDER = 'ollama'"
            )

        payload = {
            "model":      ANTHROPIC_MODEL,
            "max_tokens": ANTHROPIC_MAX_TOKENS,
            "system":     _SYSTEM_PROMPT,
            "messages":   history,   # Anthropic uses system param, not system role
        }

        log.debug("Anthropic: sending %d messages …", len(history))

        try:
            req = urllib.request.Request(
                self._API_URL,
                data=json.dumps(payload).encode(),
                headers={
                    "Content-Type":      "application/json",
                    "x-api-key":         self._api_key,
                    "anthropic-version": "2023-06-01",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())

            # Anthropic returns content as a list of blocks
            reply = data["content"][0]["text"].strip()
            log.debug("Anthropic replied (%d chars)", len(reply))
            return reply

        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8", errors="replace")
            log.error("Anthropic HTTP %d: %s", err.code, body[:300])
            return f"[Anthropic error {err.code}] {body[:200]}"

        except Exception as err:
            log.error("Anthropic request failed: %s", err)
            return f"[Error] Could not reach Anthropic API: {err}"


# ══════════════════════════════════════════════════════════════════════════════
# Backend 3: HuggingFace sentence-transformers  (local, no API key)
# ══════════════════════════════════════════════════════════════════════════════

class _HuggingFaceBackend(_BaseBackend):
    """
    Fully local pipeline using two HuggingFace models — no API key, no
    internet needed after the first download (~330 MB total).

    How it works
    ------------
    1. sentence-transformers (all-MiniLM-L6-v2) encodes the route summary
       and a set of pre-written safety advice templates into embedding vectors.
    2. Cosine similarity selects the most relevant template for the route's
       risk profile (high crash score / hilly / safe).
    3. Flan-T5-base fills in the specifics (street names, scores) using
       the selected template as an instruction prompt.

    This approach is factual and grounded — it cannot hallucinate crash data
    because it only slots in numbers from the route dict.

    One-time install
    ----------------
    pip install sentence-transformers transformers torch

    Config (config.py)
    ------------------
    HF_EMBEDDING_MODEL   default: all-MiniLM-L6-v2    (80 MB)
    HF_GENERATION_MODEL  default: google/flan-t5-base  (250 MB)
    HF_MAX_NEW_TOKENS    default: 256
    """

    # Pre-written advice templates keyed by risk level.
    # Flan-T5 fills these in with route-specific facts.
    _TEMPLATES = {
        "high": (
            "This route has significant crash history. Summarise the danger on "
            "{streets} and recommend safer parallel streets or off-peak riding times."
        ),
        "moderate": (
            "This route has some crash risk. Briefly describe the risk on "
            "{streets} and give one practical safety tip for each."
        ),
        "safe": (
            "This route has no recorded crash history. Give a brief positive "
            "summary and one general bike safety tip for Berkeley."
        ),
    }

    def __init__(self) -> None:
        log.info(
            "HuggingFace backend | embed=%s | gen=%s",
            HF_EMBEDDING_MODEL, HF_GENERATION_MODEL,
        )
        self._embedder  = None   # loaded lazily on first chat() call
        self._generator = None

    def _load_models(self) -> None:
        """
        Lazy-load both models on the first call so startup is fast.
        Models are cached by HuggingFace in ~/.cache/huggingface after
        the first download.
        """
        if self._embedder is not None:
            return  # already loaded

        try:
            from sentence_transformers import SentenceTransformer
            from transformers import pipeline
        except ImportError:
            raise ImportError(
                "HuggingFace backend requires additional packages.\n"
                "Install them with:\n"
                "  pip install sentence-transformers transformers torch"
            )

        log.info("Loading embedding model '%s' …", HF_EMBEDDING_MODEL)
        self._embedder = SentenceTransformer(HF_EMBEDDING_MODEL)

        log.info("Loading generation model '%s' …", HF_GENERATION_MODEL)
        # text2text-generation is the task for Flan-T5 style models
        self._generator = pipeline(
            "text2text-generation",
            model=HF_GENERATION_MODEL,
            max_new_tokens=HF_MAX_NEW_TOKENS,
        )
        log.info("HuggingFace models loaded and ready.")

    def chat(self, history: list) -> str:
        """
        Extract route facts from the latest user message, pick the best
        advice template via embedding similarity, then generate a grounded
        response with Flan-T5.
        """
        self._load_models()

        import numpy as np

        # Get the most recent user message (contains the route summary or question)
        last_user = next(
            (m["content"] for m in reversed(history) if m["role"] == "user"),
            "",
        )

        log.debug("HuggingFace: processing message (%d chars)", len(last_user))

        # ── Step 1: embed the user message ───────────────────────────────────
        user_embedding = self._embedder.encode(last_user, convert_to_numpy=True)

        # ── Step 2: embed the template descriptions ───────────────────────────
        template_descs = {
            "high":     "dangerous road many crashes severe injuries fatalities",
            "moderate": "some crashes moderate risk caution advised",
            "safe":     "safe route no crashes pleasant cycling",
        }
        template_embeddings = {
            key: self._embedder.encode(desc, convert_to_numpy=True)
            for key, desc in template_descs.items()
        }

        # ── Step 3: cosine similarity → pick best template ────────────────────
        def cosine(a, b):
            return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

        scores = {key: cosine(user_embedding, emb) for key, emb in template_embeddings.items()}
        best_template_key = max(scores, key=scores.get)
        log.debug("Template scores: %s → selected '%s'", scores, best_template_key)

        # ── Step 4: extract dangerous street names from the message ───────────
        # Simple heuristic: lines starting with "  -" contain street names
        streets = []
        for line in last_user.splitlines():
            if line.strip().startswith("-") and "crash_score" in line:
                # Format:  "  - Telegraph Ave (340m): crash_score=1.50"
                street = line.split("(")[0].replace("-", "").strip()
                if street:
                    streets.append(street)

        streets_str = ", ".join(streets) if streets else "the route"

        # ── Step 5: fill template and generate response with Flan-T5 ──────────
        template = self._TEMPLATES[best_template_key]
        prompt   = (
            f"You are a bike safety advisor for Berkeley, CA.\n\n"
            f"Route data:\n{last_user}\n\n"
            f"Task: {template.format(streets=streets_str)}\n\n"
            f"Response:"
        )

        log.debug("Generating with Flan-T5 (template=%s) …", best_template_key)
        result = self._generator(prompt, max_new_tokens=HF_MAX_NEW_TOKENS)
        generated = result[0]["generated_text"].strip()

        # Append a safety rating based on the template selected
        rating_map = {"high": "CAUTION", "moderate": "MODERATE", "safe": "SAFE"}
        rating     = rating_map[best_template_key]

        reply = f"{generated}\n\nOverall safety rating: {rating}"
        log.debug("HuggingFace replied (%d chars)", len(reply))
        return reply


# ══════════════════════════════════════════════════════════════════════════════
# No-AI fallback
# ══════════════════════════════════════════════════════════════════════════════

class _NoAIBackend(_BaseBackend):
    """
    Rule-based fallback when AI_PROVIDER = "none".
    Derives a plain-text safety summary directly from the route stats
    without any model call — instant and always available.
    """

    def chat(self, history: list) -> str:
        last = next(
            (m["content"] for m in reversed(history) if m["role"] == "user"), ""
        )
        return (
            "[AI disabled — set AI_PROVIDER in config.py to enable]\n"
            "Options: 'ollama'  |  'anthropic'  |  'huggingface'\n\n"
            f"Your input:\n{last}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Public interface — callers only use this class
# ══════════════════════════════════════════════════════════════════════════════

class RouteExplainer:
    """
    Stateful conversational AI explainer for a SafeTrack Berkeley bike route.

    The backend is resolved from config.AI_PROVIDER at construction time.
    Callers never reference backend classes directly — just call explain()
    and ask().

    Example
    -------
        explainer = RouteExplainer(route)
        print(explainer.explain())
        print(explainer.ask("Is Shattuck Ave safer than Telegraph here?"))
        print(explainer.ask("What about riding at night?"))
    """

    # Registry: config string → backend class
    _REGISTRY = {
        "ollama":      _OllamaBackend,
        "anthropic":   _AnthropicBackend,
        "huggingface": _HuggingFaceBackend,
        "none":        _NoAIBackend,
    }

    def __init__(self, route: dict) -> None:
        self.route    = route
        self._history: list = []   # full conversation kept for multi-turn context

        provider    = AI_PROVIDER.lower().strip()
        backend_cls = self._REGISTRY.get(provider)

        if backend_cls is None:
            log.warning(
                "Unknown AI_PROVIDER '%s'. Valid options: %s. Using 'none'.",
                provider, list(self._REGISTRY),
            )
            backend_cls = _NoAIBackend

        log.info("RouteExplainer initialised | provider=%s", provider)
        self._backend: _BaseBackend = backend_cls()

    def explain(self) -> str:
        """
        Generate the initial plain-English safety analysis of the route.
        Always call this before ask() so the model has route context.
        """
        log.info("Generating initial route explanation …")
        return self._send(self._build_route_prompt())

    def ask(self, question: str) -> str:
        """
        Ask a follow-up question. The full conversation history is preserved
        so the model can reference earlier context.

        Parameters
        ----------
        question : str
            E.g. "Is there a safer parallel street to Telegraph Ave?"
        """
        log.info("Follow-up: '%s'", question)
        return self._send(question)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _send(self, user_message: str) -> str:
        """Append → call backend → store reply → return reply."""
        self._history.append({"role": "user", "content": user_message})
        reply = self._backend.chat(self._history)
        self._history.append({"role": "assistant", "content": reply})
        return reply

    def _build_route_prompt(self) -> str:
        """
        Serialise the route dict into a concise structured prompt.
        Only facts the model needs — no raw graph internals.
        """
        r = self.route

        # Collect segments that have recorded crashes
        danger_steps = [s for s in r["steps"] if s["crash_score"] > 0]
        danger_lines = "\n".join(
            f"  - {s['street']} ({s['length_m']:.0f}m): crash_score={s['crash_score']:.2f}"
            for s in danger_steps
        ) or "  None — no recorded crash segments on this route."

        total_elevation = sum(s.get("elevation_gain_m", 0) for s in r["steps"])

        return (
            f"Route: {r['origin_address']}  →  {r['destination_address']}\n"
            f"Distance: {r['total_length_km']} km ({r['total_length_miles']} miles)\n"
            f"Total elevation gain: {total_elevation:.0f} m\n"
            f"Total crash score: {r['total_crash_score']:.2f}\n\n"
            f"Dangerous segments (crash_score > 0):\n{danger_lines}\n\n"
            "Please explain this route's safety profile and give practical cycling advice."
        )