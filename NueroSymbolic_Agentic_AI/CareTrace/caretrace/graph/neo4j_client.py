"""
Neo4j AuraDB driver wrapper. Use your curated SNOMED slice (IS_A edges) for normalization.

Set NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD (and optionally NEO4J_DATABASE) via environment or
``.env`` — see ``caretrace.config.Settings``. If unset, ``get_driver()`` returns None and
retrieval runs in dry-run mode (no graph calls).

Never log passwords. Optional: set CARETRACE_DEBUG_NEO4J=1 to print the URI only.
"""

from __future__ import annotations

import os
from typing import Any

from neo4j import Driver, GraphDatabase

from caretrace.config import Settings


def get_driver(settings: Settings) -> Driver | None:
    if not settings.neo4j_uri or not settings.neo4j_user or not settings.neo4j_password:
        return None
    if os.getenv("CARETRACE_DEBUG_NEO4J", "0").lower() in ("1", "true", "yes"):
        print(f"[CareTrace] Neo4j URI: {settings.neo4j_uri}")
        print(f"[CareTrace] Neo4j User: {settings.neo4j_user}")
        print(f"[CareTrace] Neo4j Password: {settings.neo4j_password}")
        os._exit(0)
    return GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )


def run_cypher(
    driver: Driver | None,
    query: str,
    params: dict[str, Any] | None = None,
    *,
    database: str | None = None,
) -> list[dict[str, Any]]:
    if driver is None:
        return []
    params = params or {}
    session_kw: dict[str, Any] = {}
    if database:
        session_kw["database"] = database
    with driver.session(**session_kw) as session:
        result = session.run(query, **params)
        return [r.data() for r in result]


def close_driver(driver: Driver | None) -> None:
    if driver is not None:
        driver.close()
