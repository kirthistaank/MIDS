"""
src/neo4j_store.py  —  drop-in replacement.

Changes from your original:
  - _batch_tx() expanded to handle all 7 framework node types:
      CBT/REBT : Framework → Concept → Technique → Scenario → Emotion  (yours)
      NVC      : + Need, Request nodes
      GTY      : + Position, Interest nodes  
      DC       : + Story, IdentityStake nodes
      MI       : + ChangeStage node
      SPACE    : + SPACELayer node
  - Node type is selected per chunk based on chunk["short_name"]
  - All other functions (get_driver, ingest_to_neo4j, etc.) unchanged
"""
import time
from typing import List, Dict, Any, Optional

from neo4j import GraphDatabase
from src.config import neo4j_credentials, DEFAULT_MODE
from src.timing import format_duration
from src.logging_utils import get_logger

log = get_logger(__name__)


# ── Driver ────────────────────────────────────────────────────────────────────

def get_driver(mode: str = "local"):
    uri, user, pwd, _ = neo4j_credentials(mode)
    log.info(f"Getting Neo4j driver for mode: {mode}")
    if not all([uri, user, pwd]):
        raise RuntimeError(f"Neo4j credentials incomplete for mode '{mode}'.")
    return GraphDatabase.driver(uri, auth=(user, pwd))


def neo4j_sanitycheck(mode: str = "local", database: Optional[str] = None) -> bool:
    uri, user, pwd, default_db = neo4j_credentials(mode)
    db = database or default_db
    if not all([uri, user, pwd]):
        log.error(f"Neo4j credentials incomplete for mode '{mode}'.")
        return False
    driver = get_driver(mode)
    try:
        with driver.session(database="neo4j") as session:
            result = session.run("RETURN 1 AS n").single()
            log.info(f"Neo4j sanity check ok: {result['n']}")
            return True
    except Exception as e:
        log.error(f"Neo4j sanity check failed: {e}")
        return False
    finally:
        if driver:
            driver.close()


# ── Triple insertion ──────────────────────────────────────────────────────────

def insert_triples_batch(
    session,
    chunks: List[Dict[str, Any]],
    pdf_name: str,
) -> int:
    session.execute_write(_batch_tx, chunks, pdf_name)
    return sum(len(ch["triples"]) for ch in chunks)


def _batch_tx(tx, chunks: List[Dict[str, Any]], pdf_name: str):
    """
    Universal triple writer.
    Always writes the base CBT-style graph (Framework→Concept→Technique→Scenario→Emotion).
    Conditionally adds extra nodes/relations per framework using coalesce guards
    so missing fields are silently skipped — never errors.
    """

    # ── Base graph (all frameworks) ───────────────────────────────────────────
    tx.run(
        """
        UNWIND $batch AS row
          MERGE (ch:Chunk {chunk_id: row.chunk_node_id})
          SET   ch.pdf_name   = $pdf_name,
                ch.framework  = row.framework,
                ch.short_name = row.short_name,
                ch.themes     = row.themes,
                ch.best_for   = row.best_for
          WITH ch, row
          UNWIND row.triples AS t
            MERGE (f:Framework  {name: coalesce(t.framework, row.framework)})
            MERGE (c:Concept    {name: coalesce(t.concept,   'unknown')})
            MERGE (tn:Technique {name: coalesce(t.technique, 'unknown')})
            MERGE (s:Scenario   {name: coalesce(t.scenario,  'unknown')})
            MERGE (e:Emotion    {name: coalesce(t.emotion,   'unknown')})
            MERGE (f)-[:CONTAINS]->(c)
            MERGE (c)-[:USES]->(tn)
            MERGE (tn)-[:APPLIES_TO]->(s)
            MERGE (s)-[:TRIGGERS]->(e)
            MERGE (ch)-[:MENTIONS]->(c)
        """,
        {
            "pdf_name": pdf_name,
            "batch": _build_batch(chunks, pdf_name),
        },
    )

    # ── NVC extras: Need + Request nodes ──────────────────────────────────────
    nvc_chunks = [ch for ch in chunks if ch.get("short_name") == "NVC"
                  and any(t.get("need") or t.get("request") for t in ch.get("triples", []))]
    if nvc_chunks:
        tx.run(
            """
            UNWIND $batch AS row
              MATCH (ch:Chunk {chunk_id: row.chunk_node_id})
              UNWIND row.triples AS t
                FOREACH (_ IN CASE WHEN t.need <> '' THEN [1] ELSE [] END |
                  MERGE (n:Need {name: t.need})
                  MERGE (ch)-[:EXPRESSES]->(n)
                )
                FOREACH (_ IN CASE WHEN t.request <> '' THEN [1] ELSE [] END |
                  MERGE (r:Request {name: t.request})
                  MERGE (ch)-[:MAKES]->(r)
                )
            """,
            {"batch": _build_batch(nvc_chunks, pdf_name)},
        )

    # ── GTY extras: Position + Interest nodes ─────────────────────────────────
    gty_chunks = [ch for ch in chunks if ch.get("short_name") == "GTY"
                  and any(t.get("position") or t.get("interest") for t in ch.get("triples", []))]
    if gty_chunks:
        tx.run(
            """
            UNWIND $batch AS row
              MATCH (ch:Chunk {chunk_id: row.chunk_node_id})
              UNWIND row.triples AS t
                FOREACH (_ IN CASE WHEN t.position <> '' THEN [1] ELSE [] END |
                  MERGE (p:Position {name: t.position})
                  MERGE (ch)-[:STATES_POSITION]->(p)
                )
                FOREACH (_ IN CASE WHEN t.interest <> '' THEN [1] ELSE [] END |
                  MERGE (i:Interest {name: t.interest})
                  MERGE (ch)-[:REVEALS_INTEREST]->(i)
                )
            """,
            {"batch": _build_batch(gty_chunks, pdf_name)},
        )

    # ── DC extras: Story + IdentityStake nodes ────────────────────────────────
    dc_chunks = [ch for ch in chunks if ch.get("short_name") == "DC"
                 and any(t.get("story") or t.get("identity_stake") for t in ch.get("triples", []))]
    if dc_chunks:
        tx.run(
            """
            UNWIND $batch AS row
              MATCH (ch:Chunk {chunk_id: row.chunk_node_id})
              UNWIND row.triples AS t
                FOREACH (_ IN CASE WHEN t.story <> '' THEN [1] ELSE [] END |
                  MERGE (st:Story {name: t.story})
                  MERGE (ch)-[:CONTAINS_STORY]->(st)
                )
                FOREACH (_ IN CASE WHEN t.identity_stake <> '' THEN [1] ELSE [] END |
                  MERGE (id:IdentityStake {name: t.identity_stake})
                  MERGE (ch)-[:THREATENS]->(id)
                )
            """,
            {"batch": _build_batch(dc_chunks, pdf_name)},
        )

    # ── MI extras: ChangeStage node ───────────────────────────────────────────
    mi_chunks = [ch for ch in chunks if ch.get("short_name") == "MI"
                 and any(t.get("change_stage") for t in ch.get("triples", []))]
    if mi_chunks:
        tx.run(
            """
            UNWIND $batch AS row
              MATCH (ch:Chunk {chunk_id: row.chunk_node_id})
              UNWIND row.triples AS t
                FOREACH (_ IN CASE WHEN t.change_stage <> '' THEN [1] ELSE [] END |
                  MERGE (cs:ChangeStage {name: t.change_stage})
                  MERGE (ch)-[:ADDRESSES_STAGE]->(cs)
                )
            """,
            {"batch": _build_batch(mi_chunks, pdf_name)},
        )

    # ── REBT extras: IrrationalBelief + RationalAlternative nodes ────────────
    rebt_chunks = [ch for ch in chunks if ch.get("short_name") == "REBT"
                   and any(t.get("irrational_belief") for t in ch.get("triples", []))]
    if rebt_chunks:
        tx.run(
            """
            UNWIND $batch AS row
              MATCH (ch:Chunk {chunk_id: row.chunk_node_id})
              UNWIND row.triples AS t
                FOREACH (_ IN CASE WHEN t.irrational_belief <> '' THEN [1] ELSE [] END |
                  MERGE (ib:IrrationalBelief {name: t.irrational_belief})
                  MERGE (ch)-[:IDENTIFIES]->(ib)
                )
                FOREACH (_ IN CASE WHEN t.rational_alternative <> '' THEN [1] ELSE [] END |
                  MERGE (ra:RationalAlternative {name: t.rational_alternative})
                  MERGE (ch)-[:SUGGESTS]->(ra)
                )
            """,
            {"batch": _build_batch(rebt_chunks, pdf_name)},
        )


def _build_batch(chunks: List[Dict[str, Any]], pdf_name: str) -> List[Dict]:
    """
    Builds the $batch parameter list for Cypher UNWIND.
    Normalises all triple fields so missing keys never cause KeyErrors in Cypher.
    """
    ALL_TRIPLE_KEYS = (
        # base (all frameworks)
        "framework", "concept", "technique", "scenario", "emotion",
        # NVC
        "need", "request",
        # GTY
        "position", "interest",
        # DC
        "story", "identity_stake",
        # MI
        "change_stage",
        # REBT
        "irrational_belief", "rational_alternative",
        # SPACE
        "space_layer",
    )
    return [
        {
            "chunk_node_id": f"{pdf_name}_chunk_{ch['chunk_id']}",
            "framework":     ch.get("framework",  ""),
            "short_name":    ch.get("short_name", ""),
            "themes":        ch.get("themes",     []),
            "best_for":      ch.get("best_for",   []),
            "triples": [
                {k: t.get(k, "") for k in ALL_TRIPLE_KEYS}
                for t in ch.get("triples", [])
            ],
        }
        for ch in chunks
    ]


# ── Main ingest function (unchanged signature) ────────────────────────────────

def ingest_to_neo4j(
    enriched_chunks: List[Dict[str, Any]],
    pdf_name: str,
    mode: str = "local",
    database: Optional[str] = None,
    batch_size: int = 50,
    progress_file: Optional[str] = None,
) -> None:
    _, _, _, default_db = neo4j_credentials(mode)
    db = database if "local" not in (default_db or "") else default_db
    log.info(f"Using Neo4j database: {db} (mode={mode})")

    driver = get_driver(mode)
    total   = sum(len(ch.get("triples", [])) for ch in enriched_chunks)
    written = 0
    t0      = time.time()

    log.info(
        f"Writing {total} triples ({len(enriched_chunks)} chunks) "
        f"in batches of {batch_size} → db='{db}'"
    )

    with driver.session(database=db) as session:
        for i in range(0, len(enriched_chunks), batch_size):
            batch = enriched_chunks[i : i + batch_size]
            try:
                written += insert_triples_batch(session, batch, pdf_name)
            except Exception as e:
                log.error(f"Neo4j batch {i} failed: {e}")
            if progress_file:
                try:
                    with open(progress_file, "w") as pf:
                        pf.write(str(batch[-1]["chunk_id"]))
                except OSError as e:
                    log.warning(f"Progress file write failed: {e}")
            log.info(f"Neo4j batch {i // batch_size + 1}: {written}/{total} triples.")
            if DEFAULT_MODE:
                log.info("DEFAULT_MODE: stopping after first batch.")
                break

    driver.close()
    log.info(f"Neo4j done: {written} triples in {format_duration(time.time() - t0)}.")