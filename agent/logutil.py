"""
Structured event log, not a flat list of sentences.

Every recorded event carries enough structure to be queried or aggregated
later (e.g. "average duration_ms of the regenerate action", "how often
does evaluate flag missing_sections for business_report") rather than
just being human prose. `message` is kept alongside the structured
fields purely for the UI/log-reading human -- the event_id/phase/action/
target/status/duration_ms/timestamp fields are the actual data model.
"""

from __future__ import annotations
import uuid
from datetime import datetime, timezone


def event(
    phase: str,
    action: str,
    message: str,
    target: str | None = None,
    status: str = "success",
    duration_ms: int | None = None,
) -> dict:
    """
    phase: planning | drafting | reflection | docx
    action: e.g. classify, draft_section, evaluate, regenerate, strengthen,
            assemble, complete
    target: what the action operated on (a section title, a checklist
            label) -- None for phase-level events
    status: success | error | info
    duration_ms: wall-clock time the action itself took, when known
    """
    return {
        "event_id": uuid.uuid4().hex[:12],
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "phase": phase,
        "action": action,
        "target": target,
        "status": status,
        "duration_ms": duration_ms,
        "message": message,
    }
