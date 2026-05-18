"""
Optional baseline for course evaluation: a single conversational LLM without symbolic gates.

Compare against CareTrace on:
- provenance / dosing discipline
- stability under paraphrase
- refusal to fabricate local epidemiology
"""

from __future__ import annotations

from caretrace.config import Settings


def vanilla_llm_reply(settings: Settings, transcript: str) -> str:
    """Minimal baseline — swap in your evaluation harness."""
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as e:
        raise RuntimeError("langchain-openai required") from e

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=0.7,
        api_key=settings.openai_api_key,
    )
    sys = (
        "You are a helpful assistant for worried parents. "
        "This baseline intentionally has NO structured triage protocol — "
        "document failure modes vs CareTrace in your report."
    )
    return str(
        llm.invoke(
            [{"role": "system", "content": sys}, {"role": "user", "content": transcript}]
        ).content
    )
