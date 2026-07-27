"""
Lightweight SQLite persistence layer.

Why SQLite and not Postgres/etc: this is a single-process internal tool
meant to be run with one command and handed to someone to try — a
zero-setup embedded database is the right tool here. The access pattern
(free functions wrapping stdlib `sqlite3`) is intentionally small and
swappable: every call goes through this module, so migrating to Postgres
later is a matter of changing this one file, not the API or frontend.

The Agent Decision Summary (agent/schemas.py: AgentSummary) is NOT stored
as its own column -- it's small and fully derivable from the other
columns, so it's recomputed on read (see main.py: build_summary()) rather
than persisted redundantly.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "agent_history.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_text TEXT NOT NULL,
    document_type TEXT NOT NULL,
    title TEXT NOT NULL,
    assumptions_json TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    sections_json TEXT NOT NULL,
    execution_log_json TEXT NOT NULL,
    llm_mode TEXT NOT NULL,
    file_name TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

# Columns added after the initial release. Added via ALTER TABLE on
# startup if missing, so older agent_history.db files upgrade in place
# instead of breaking. "confidence" is a legacy column from an earlier
# version, kept but unused so old databases don't need a destructive
# migration; new code reads/writes classification_confidence instead.
_MIGRATION_COLUMNS = {
    "confidence": "REAL NOT NULL DEFAULT 0",
    "classification_confidence": "REAL NOT NULL DEFAULT 0",
    "reflection_confidence": "REAL NOT NULL DEFAULT 0",
    "classification_reasoning": "TEXT NOT NULL DEFAULT ''",
    "timing_json": "TEXT NOT NULL DEFAULT '{}'",
    "reflection_json": "TEXT NOT NULL DEFAULT '[]'",
    "email_json": "TEXT NOT NULL DEFAULT '{\"requested\": false, \"status\": \"not_requested\"}'",
}


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute(SCHEMA)
        existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(documents)")}
        for col, decl in _MIGRATION_COLUMNS.items():
            if col not in existing_cols:
                conn.execute(f"ALTER TABLE documents ADD COLUMN {col} {decl}")


@dataclass
class DocumentRecord:
    id: int | None
    request_text: str
    document_type: str
    title: str
    classification_confidence: float
    classification_reasoning: str
    reflection_confidence: float
    assumptions: list
    plan: list
    sections: list
    reflection: list
    timing: dict
    execution_log: list
    email: dict
    llm_mode: str
    file_name: str
    created_at: str


def save_document(
    request_text: str,
    document_type: str,
    title: str,
    classification_confidence: float,
    classification_reasoning: str,
    reflection_confidence: float,
    assumptions: list,
    plan: list,
    sections: list,
    reflection: list,
    timing: dict,
    execution_log: list,
    email: dict,
    llm_mode: str,
    file_name: str,
) -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO documents
               (request_text, document_type, title, classification_confidence,
                classification_reasoning, reflection_confidence, assumptions_json,
                plan_json, sections_json, reflection_json, timing_json,
                execution_log_json, email_json, llm_mode, file_name, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                request_text,
                document_type,
                title,
                classification_confidence,
                classification_reasoning,
                reflection_confidence,
                json.dumps(assumptions),
                json.dumps(plan),
                json.dumps(sections),
                json.dumps(reflection),
                json.dumps(timing),
                json.dumps(execution_log),
                json.dumps(email),
                llm_mode,
                file_name,
                created_at,
            ),
        )
        return cur.lastrowid


def _row_to_record(row: sqlite3.Row) -> DocumentRecord:
    keys = row.keys()
    return DocumentRecord(
        id=row["id"],
        request_text=row["request_text"],
        document_type=row["document_type"],
        title=row["title"],
        classification_confidence=row["classification_confidence"] if "classification_confidence" in keys else 0.0,
        classification_reasoning=row["classification_reasoning"] if "classification_reasoning" in keys else "",
        reflection_confidence=row["reflection_confidence"] if "reflection_confidence" in keys else 0.0,
        assumptions=json.loads(row["assumptions_json"]),
        plan=json.loads(row["plan_json"]),
        sections=json.loads(row["sections_json"]),
        reflection=json.loads(row["reflection_json"]) if "reflection_json" in keys else [],
        timing=json.loads(row["timing_json"]) if "timing_json" in keys else {},
        execution_log=json.loads(row["execution_log_json"]),
        email=json.loads(row["email_json"]) if "email_json" in keys and row["email_json"] else {"requested": False, "status": "not_requested"},
        llm_mode=row["llm_mode"],
        file_name=row["file_name"],
        created_at=row["created_at"],
    )


def update_email_result(doc_id: int, email: dict, plan: list, execution_log: list) -> None:
    """
    Updates the email status on an ALREADY-persisted row, rather than
    re-inserting. Called only after save_document() has already given the
    document a stable id -- see main.py's ordering: persist first, then
    attempt the optional email side effect, then record its outcome here.
    Also refreshes plan_json/execution_log_json since those gained a
    send_email step/event that didn't exist at the original insert.
    """
    with _connect() as conn:
        conn.execute(
            "UPDATE documents SET email_json = ?, plan_json = ?, execution_log_json = ? WHERE id = ?",
            (json.dumps(email), json.dumps(plan), json.dumps(execution_log), doc_id),
        )


def list_documents(limit: int = 50) -> list[DocumentRecord]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM documents ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_record(r) for r in rows]


def get_document(doc_id: int) -> DocumentRecord | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return _row_to_record(row) if row else None


def stats() -> dict:
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM documents").fetchone()["c"]
        by_type = conn.execute(
            "SELECT document_type, COUNT(*) c FROM documents GROUP BY document_type"
        ).fetchall()
        live_count = conn.execute(
            "SELECT COUNT(*) c FROM documents WHERE llm_mode = 'live'"
        ).fetchone()["c"]
        return {
            "total_documents": total,
            "by_type": {r["document_type"]: r["c"] for r in by_type},
            "live_llm_runs": live_count,
        }
