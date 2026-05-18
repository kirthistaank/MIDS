"""
Knowledge retrieval: text mentions → SNOMED-linked annotations (Neo4j).

Supports three graph shapes (tried in order where applicable):

1. **Fever CPG mini-KG** (notebooks): ``(:Concept {pt, ...})`` where the SNOMED id is stored as
   **either** ``sctid`` **or** ``conceptId`` (same SNOMED SCTID value, different property names),
   with ``[:IS_A]`` and ``[:REL {typeId, typeTerm}]``.

2. **Snowstorm / ``store_snowmed`` loader:** ``Concept(conceptId)``, ``Description(term)`` via
   ``HAS_DESCRIPTION``, hierarchy on ``RELATED_TO`` where ``typeId`` = SNOMED *Is a* (116680003).

3. **Curated slice:** ``Concept(id, term)`` and ``[:IS_A*]->(:Concept)``.

Schema detection uses ``CALL db.labels()`` / ``db.propertyKeys()`` / ``db.relationshipTypes()`` so we
never run Cypher that references missing labels or property keys (avoids Neo4j 5 ``01N50`` / ``01N52``
warnings on Aura).
"""

from __future__ import annotations

from typing import Any

from neo4j import Driver

from caretrace.graph.neo4j_client import run_cypher

# SNOMED CT "Is a" relationship type identifier (string as stored by typical RF2 loaders)
SNOMED_IS_A_TYPE_ID = "116680003"

_CACHE_KEY = tuple[int, str]

_LABELS_CACHE: dict[_CACHE_KEY, frozenset[str]] = {}
_KEYS_CACHE: dict[_CACHE_KEY, frozenset[str]] = {}
_REL_TYPES_CACHE: dict[_CACHE_KEY, frozenset[str]] = {}


def _cache_key(driver: Driver | None, *, database: str | None) -> _CACHE_KEY:
    return (id(driver) if driver is not None else 0, database or "")


def _cached_labels(driver: Driver | None, *, database: str | None) -> frozenset[str]:
    if driver is None:
        return frozenset()
    key = _cache_key(driver, database=database)
    if key in _LABELS_CACHE:
        return _LABELS_CACHE[key]
    rows = run_cypher(
        driver,
        "CALL db.labels() YIELD label RETURN collect(label) AS labels",
        {},
        database=database,
    )
    raw = rows[0].get("labels") if rows else None
    labels = frozenset(str(x) for x in raw) if raw else frozenset()
    _LABELS_CACHE[key] = labels
    return labels


def _cached_property_keys(driver: Driver | None, *, database: str | None) -> frozenset[str]:
    if driver is None:
        return frozenset()
    key = _cache_key(driver, database=database)
    if key in _KEYS_CACHE:
        return _KEYS_CACHE[key]
    rows = run_cypher(
        driver,
        "CALL db.propertyKeys() YIELD propertyKey RETURN collect(propertyKey) AS keys",
        {},
        database=database,
    )
    raw = rows[0].get("keys") if rows else None
    keys = frozenset(str(x) for x in raw) if raw else frozenset()
    _KEYS_CACHE[key] = keys
    return keys


def _cached_relationship_types(driver: Driver | None, *, database: str | None) -> frozenset[str]:
    if driver is None:
        return frozenset()
    key = _cache_key(driver, database=database)
    if key in _REL_TYPES_CACHE:
        return _REL_TYPES_CACHE[key]
    rows = run_cypher(
        driver,
        "CALL db.relationshipTypes() YIELD relationshipType RETURN collect(relationshipType) AS types",
        {},
        database=database,
    )
    raw = rows[0].get("types") if rows else None
    types = frozenset(str(x) for x in raw) if raw else frozenset()
    _REL_TYPES_CACHE[key] = types
    return types


def _has_pt_snomed_slice(keys: frozenset[str]) -> bool:
    """Concept nodes use preferred term ``pt`` and SNOMED id on ``sctid`` and/or ``conceptId``."""
    if "pt" not in keys:
        return False
    return "sctid" in keys or "conceptId" in keys


def _graph_has_pt_concept_data(
    driver: Driver | None,
    *,
    database: str | None,
) -> bool:
    """True if at least one :Concept has pt plus an id property we can use."""
    if driver is None:
        return False
    keys = _cached_property_keys(driver, database=database)
    if not _has_pt_snomed_slice(keys):
        return False
    id_conds: list[str] = []
    if "sctid" in keys:
        id_conds.append("c.sctid IS NOT NULL")
    if "conceptId" in keys:
        id_conds.append("c.conceptId IS NOT NULL")
    if not id_conds:
        return False
    where_id = " OR ".join(id_conds)
    q = f"""
        MATCH (c:Concept)
        WHERE c.pt IS NOT NULL AND ({where_id})
        RETURN 1 AS ok
        LIMIT 1
        """
    rows = run_cypher(driver, q, {}, database=database)
    return bool(rows)


def _schema_is_pt_slice_without_description(
    keys: frozenset[str], labels: frozenset[str]
) -> bool:
    """Looks like CPG mini-KG in Aura (pt + sctid/conceptId, no separate Description index)."""
    if not _has_pt_snomed_slice(keys):
        return False
    if "Description" in labels:
        return False
    return True


def _concept_id_expr_c(keys: frozenset[str], alias: str = "c") -> str:
    """Expression for canonical string id from sctid and/or conceptId."""
    parts: list[str] = []
    if "sctid" in keys:
        parts.append(f"toString({alias}.sctid)")
    if "conceptId" in keys:
        parts.append(f"toString({alias}.conceptId)")
    if not parts:
        return "null"
    if len(parts) == 1:
        return parts[0]
    return "coalesce(" + ", ".join(parts) + ")"


def _where_concept_id_matches(keys: frozenset[str], alias: str = "c") -> str:
    """Predicate: node id equals $id (string SNOMED code)."""
    parts: list[str] = []
    if "sctid" in keys:
        parts.append(f"{alias}.sctid = $id")
        parts.append(f"toString({alias}.sctid) = $id")
    if "conceptId" in keys:
        parts.append(f"toString({alias}.conceptId) = $id")
        parts.append(f"{alias}.conceptId = $id")
    if not parts:
        return "false"
    return "(" + " OR ".join(parts) + ")"


def _find_concepts_pt_slice(
    driver: Driver | None,
    term: str,
    limit: int,
    keys: frozenset[str],
    *,
    database: str | None,
) -> list[dict[str, Any]]:
    id_null: list[str] = []
    if "sctid" in keys:
        id_null.append("c.sctid IS NOT NULL")
    if "conceptId" in keys:
        id_null.append("c.conceptId IS NOT NULL")
    where_id = " OR ".join(id_null) if len(id_null) > 1 else id_null[0]
    id_ret = _concept_id_expr_c(keys, "c")
    q = f"""
    MATCH (c:Concept)
    WHERE c.pt IS NOT NULL AND ({where_id})
      AND toLower(toString(c.pt)) CONTAINS toLower($term)
    RETURN {id_ret} AS id, toString(c.pt) AS term
    LIMIT $limit
    """
    return run_cypher(driver, q, {"term": term, "limit": limit}, database=database)


def _find_concepts_snowstorm(
    driver: Driver | None,
    term: str,
    limit: int,
    *,
    database: str | None,
) -> list[dict[str, Any]]:
    q = """
    MATCH (d:Description)
    WHERE toLower(d.term) CONTAINS toLower($term)
    MATCH (c:Concept {conceptId: d.conceptId})
    RETURN c.conceptId AS id, d.term AS term
    LIMIT $limit
    """
    return run_cypher(driver, q, {"term": term, "limit": limit}, database=database)


def _find_concepts_legacy(
    driver: Driver | None,
    term: str,
    limit: int,
    *,
    database: str | None,
) -> list[dict[str, Any]]:
    q = """
    MATCH (c:Concept)
    WHERE c.term IS NOT NULL AND toLower(toString(c.term)) CONTAINS toLower($term)
    RETURN coalesce(toString(c.id), c.conceptId) AS id, toString(c.term) AS term
    LIMIT $limit
    """
    return run_cypher(driver, q, {"term": term, "limit": limit}, database=database)


def find_concepts_by_term(
    driver: Driver | None,
    term: str,
    limit: int = 5,
    *,
    database: str | None = None,
) -> list[dict[str, Any]]:
    t = term.strip()
    labels = _cached_labels(driver, database=database)
    keys = _cached_property_keys(driver, database=database)

    if _has_pt_snomed_slice(keys):
        hits = _find_concepts_pt_slice(driver, t, limit, keys, database=database)
        if hits:
            return hits
        if _schema_is_pt_slice_without_description(keys, labels) or _graph_has_pt_concept_data(
            driver, database=database
        ):
            return []

    if "Description" in labels:
        hits = _find_concepts_snowstorm(driver, t, limit, database=database)
        if hits:
            return hits

    if "term" in keys:
        return _find_concepts_legacy(driver, t, limit, database=database)
    return []


def _ancestors_pt_slice(
    driver: Driver | None,
    concept_id: str,
    keys: frozenset[str],
    *,
    database: str | None,
) -> list[dict[str, Any]]:
    start = _where_concept_id_matches(keys, "c")
    id_a = _concept_id_expr_c(keys, "a")
    q = f"""
    MATCH (c:Concept)-[:IS_A*1..8]->(a:Concept)
    WHERE {start}
    RETURN DISTINCT {id_a} AS id, toString(a.pt) AS term
    LIMIT 40
    """
    return run_cypher(driver, q, {"id": concept_id}, database=database)


def _ancestors_related_to_is_a(
    driver: Driver | None,
    concept_id: str,
    *,
    database: str | None,
) -> list[dict[str, Any]]:
    q = """
    MATCH p = (c:Concept {conceptId: $id})-[:RELATED_TO*1..8]->(a:Concept)
    WHERE ALL(r IN relationships(p) WHERE r.typeId = $is_a)
    RETURN DISTINCT a.conceptId AS id, toString(a.conceptId) AS term
    LIMIT 40
    """
    return run_cypher(driver, q, {"id": concept_id, "is_a": SNOMED_IS_A_TYPE_ID}, database=database)


def _ancestors_is_a_edge(
    driver: Driver | None,
    concept_id: str,
    *,
    database: str | None,
) -> list[dict[str, Any]]:
    keys = _cached_property_keys(driver, database=database)
    clauses: list[str] = []
    if "conceptId" in keys:
        clauses.append("c.conceptId = $id")
        clauses.append("toString(c.conceptId) = $id")
    if "id" in keys:
        clauses.append("toString(c.id) = $id")
    if "sctid" in keys:
        clauses.append("c.sctid = $id")
        clauses.append("toString(c.sctid) = $id")
    if not clauses:
        return []

    where = " OR ".join(clauses)
    id_parts: list[str] = []
    if "sctid" in keys:
        id_parts.append("toString(a.sctid)")
    if "conceptId" in keys:
        id_parts.append("toString(a.conceptId)")
    if "id" in keys:
        id_parts.append("toString(a.id)")
    id_ret = "coalesce(" + ", ".join(id_parts) + ")" if id_parts else "null"
    term_parts: list[str] = []
    if "pt" in keys:
        term_parts.append("toString(a.pt)")
    if "term" in keys:
        term_parts.append("toString(a.term)")
    term_ret = (
        "coalesce(" + ", ".join(term_parts) + ")"
        if len(term_parts) > 1
        else (term_parts[0] if term_parts else "null")
    )

    q = f"""
    MATCH (c:Concept)-[:IS_A*1..8]->(a:Concept)
    WHERE {where}
    RETURN DISTINCT {id_ret} AS id, {term_ret} AS term
    LIMIT 40
    """
    return run_cypher(driver, q, {"id": concept_id}, database=database)


def ancestors_via_is_a(
    driver: Driver | None,
    concept_id: str,
    max_depth: int = 6,
    *,
    database: str | None = None,
) -> list[dict[str, Any]]:
    _ = max_depth
    labels = _cached_labels(driver, database=database)
    keys = _cached_property_keys(driver, database=database)
    rel_types = _cached_relationship_types(driver, database=database)

    if _has_pt_snomed_slice(keys):
        rows = _ancestors_pt_slice(driver, concept_id, keys, database=database)
        if rows:
            return rows
        if _schema_is_pt_slice_without_description(keys, labels) or _graph_has_pt_concept_data(
            driver, database=database
        ):
            return []

    if "RELATED_TO" in rel_types and "conceptId" in keys:
        rows = _ancestors_related_to_is_a(driver, concept_id, database=database)
        if rows:
            return rows
    return _ancestors_is_a_edge(driver, concept_id, database=database)


def generalize_symptom_mention(
    driver: Driver | None,
    mention: str,
    *,
    database: str | None = None,
) -> list[dict[str, Any]]:
    hits = find_concepts_by_term(driver, mention.strip(), limit=3, database=database)
    out: list[dict[str, Any]] = []
    for h in hits:
        cid = h.get("id")
        if not cid:
            continue
        anc = ancestors_via_is_a(driver, str(cid), database=database)
        out.append({"mention": mention, "concept": h, "ancestors": anc})
    return out


def annotate_case_mentions(
    driver: Driver | None,
    mentions: list[str],
    *,
    database: str | None = None,
) -> list[dict[str, Any]]:
    return [g for m in mentions for g in generalize_symptom_mention(driver, m, database=database)]
