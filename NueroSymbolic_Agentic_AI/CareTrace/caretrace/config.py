from __future__ import annotations

import os
import re
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

# Load `.env` from cwd first, then walk up from the repo root (…/CareTrace), skipping the
# inner `caretrace/` package folder so `CareTrace/.env` wins over `caretrace/.env`.
load_dotenv()
for _parent in islice(Path(__file__).resolve().parents, 1, None):
    _env = _parent / ".env"
    if _env.is_file():
        load_dotenv(_env, override=False)
        break


def _env_first(*keys: str) -> str | None:
    for k in keys:
        v = os.getenv(k)
        if v:
            return v
    return None


def _normalize_neo4j_database(raw: str | None, *, neo4j_uri: str | None) -> str | None:
    """
    Neo4j Aura hostnames look like ``67257d23.databases.neo4j.io``.
    Students often put that instance id into NEO4J_DATABASE_KGA; that is not a
    database name and triggers DatabaseNotFound. Real Aura default DB is ``neo4j``.

    Returns None to let the driver use the default database (correct for typical Aura).
    """
    if not raw:
        return None
    s = raw.strip()
    if not s:
        return None
    # 8-char lowercase hex = Aura instance id mistaken for DB name
    if len(s) == 8 and re.fullmatch(r"[0-9a-f]{8}", s, flags=re.IGNORECASE):
        return None
    if neo4j_uri:
        m = re.search(r"neo4j\+s?://([0-9a-f]{8})\.databases\.neo4j\.io", neo4j_uri, re.I)
        if m and s.lower() == m.group(1).lower():
            return None
    return s


@dataclass(frozen=True)
class Settings:
    """Environment-driven configuration. Never commit real secrets."""

    openai_api_key: str | None
    openai_model: str
    neo4j_uri: str | None
    neo4j_user: str | None
    neo4j_password: str | None
    neo4j_database: str | None
    use_mock_llm: bool
    skip_neo4j: bool
    exit_on_complete: bool
    use_lag: bool  # Logic-Augmented Generation: feed full symbolic context to LLM

    @staticmethod
    def from_env() -> "Settings":
        uri = _env_first("NEO4J_URI_KGA")
        db_raw = _env_first("NEO4J_DATABASE", "NEO4J_DATABASE_KGA")
        return Settings(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            neo4j_uri=uri,
            neo4j_user=_env_first("NEO4J_USERNAME_KGA"),
            neo4j_password=_env_first("NEO4J_PASSWORD_KGA"),
            #neo4j_database=_normalize_neo4j_database(db_raw, neo4j_uri=uri),
            neo4j_database=_env_first("NEO4J_DATABASE_KGA"),
            use_mock_llm=os.getenv("CARETRACE_MOCK_LLM", "0").lower()
            in ("1", "true", "yes"),
            skip_neo4j=os.getenv("CARETRACE_SKIP_NEO4J", "0").lower()
            in ("1", "true", "yes"),
            exit_on_complete=os.getenv("CARETRACE_EXIT_ON_COMPLETE", "1").lower()
            in ("1", "true", "yes"),
            use_lag=os.getenv("CARETRACE_USE_LAG", "0").lower()
            in ("1", "true", "yes"),
        )


Mode = Literal["interpretation", "explanation"]
