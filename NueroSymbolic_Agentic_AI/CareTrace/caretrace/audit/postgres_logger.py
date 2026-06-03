"""
Audit logging to Neon Postgres database.

Logs triage decisions, rules fired, medication flags, and KG evidence for compliance and analysis.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

import os

logger = logging.getLogger(__name__)


def _get_database_url() -> str | None:
    """Get Neon Postgres connection URL from environment or .env."""
    return os.getenv("DATABASE_URL")


def create_audit_table() -> bool:
    """Create audit_logs table if it doesn't exist. Returns True if successful."""
    import psycopg2

    db_url = _get_database_url()
    if not db_url:
        logger.warning("DATABASE_URL not set; audit logging disabled")
        return False

    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                turn_number INTEGER,
                disposition VARCHAR(50),
                rules_fired TEXT,
                med_flags TEXT,
                kg_evidence TEXT,
                case_fields TEXT,
                raw_user_input TEXT,
                out_of_scope_reason VARCHAR(100)
            )
        """)

        conn.commit()
        cursor.close()
        conn.close()
        logger.info("Audit table created/verified successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to create audit table: {e}")
        return False


def log_triage_decision(
    turn_number: int,
    disposition: str,
    rules_fired: list[str] | None,
    med_flags: list[str] | None,
    kg_evidence: list[dict[str, Any]] | None,
    case_fields: dict[str, Any] | None,
    raw_user_input: str | None,
    out_of_scope_reason: str | None,
) -> bool:
    """
    Log a triage decision to the audit database.

    Args:
        turn_number: Conversation turn number
        disposition: Triage disposition (ER_NOW, URGENT_SAME_DAY, HOME_MANAGEMENT, OUT_OF_SCOPE)
        rules_fired: List of rule IDs that fired
        med_flags: List of medication safety flags
        kg_evidence: Knowledge graph annotation list
        case_fields: Extracted case fields
        raw_user_input: Raw user message
        out_of_scope_reason: If OUT_OF_SCOPE, the reason (incomplete_intake, undetermined, etc.)

    Returns:
        True if logged successfully, False otherwise
    """
    import psycopg2

    db_url = _get_database_url()
    if not db_url:
        logger.warning("DATABASE_URL not set; audit logging skipped")
        return False

    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()

        # Serialize complex fields to JSON
        rules_json = json.dumps(rules_fired or [])
        flags_json = json.dumps(med_flags or [])
        evidence_json = json.dumps(kg_evidence or [])
        case_json = json.dumps(case_fields or {})

        cursor.execute("""
            INSERT INTO audit_logs
            (turn_number, disposition, rules_fired, med_flags, kg_evidence, case_fields, raw_user_input, out_of_scope_reason)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            turn_number,
            disposition,
            rules_json,
            flags_json,
            evidence_json,
            case_json,
            raw_user_input,
            out_of_scope_reason,
        ))

        conn.commit()
        cursor.close()
        conn.close()

        logger.info(f"Logged triage decision: turn={turn_number}, disposition={disposition}")
        return True

    except Exception as e:
        logger.error(f"Failed to log triage decision: {e}")
        return False


def get_audit_logs(limit: int = 100) -> list[dict[str, Any]] | None:
    """
    Retrieve recent audit logs. Useful for analysis and compliance review.

    Args:
        limit: Maximum number of records to retrieve

    Returns:
        List of audit log records or None if failed
    """
    import psycopg2

    db_url = _get_database_url()
    if not db_url:
        logger.warning("DATABASE_URL not set; cannot retrieve audit logs")
        return None

    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()

        cursor.execute(f"""
            SELECT id, created_at, turn_number, disposition, rules_fired, med_flags,
                   kg_evidence, case_fields, raw_user_input, out_of_scope_reason
            FROM audit_logs
            ORDER BY created_at DESC
            LIMIT %s
        """, (limit,))

        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        result = [dict(zip(columns, row)) for row in rows]

        cursor.close()
        conn.close()

        return result

    except Exception as e:
        logger.error(f"Failed to retrieve audit logs: {e}")
        return None
