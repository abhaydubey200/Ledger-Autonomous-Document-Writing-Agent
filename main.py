"""
Autonomous Document-Writing Agent - full-stack service.

Backend : FastAPI (this file + agent/)
Database: SQLite, one row per generated document (agent/database.py)
Frontend: static HTML/CSS/JS served from /static, mounted at "/"
AI Agent: agent/planner.py + agent/executor.py + agent/reflection.py + agent/llm_client.py

Pipeline per request:
    1. planner.create_plan()        -> document type + classification confidence
                                        + reasoning + assumptions + plan + sections
    2. executor.execute_plan()      -> drafts each section (retry+fallback protected)
    3. reflection.evaluate_sections() -> PURE assessment: which expected elements
                                        are missing / weak / strong, plus a score.
                                        No mutation, no LLM calls.
    4. reflection.repair_sections()   -> acts ONLY on the evaluation's findings:
                                        missing -> full regeneration, weak ->
                                        strengthen pass, strong -> left alone.
                                        Bounded by MAX_FIXES. Produces the final
                                        reflection confidence (distinct from the
                                        planner's classification confidence).
    5. self-check                     -> hard guardrail: refuse to ship empty sections
    6. docx_builder.build_docx()      -> assembles the final Word document, including
                                        an Agent Decision Summary and both confidence
                                        scores
    7. email_intent.detect_email_intent() -> deterministic, explicit-intent-only check:
                                        requires BOTH an email address AND a delivery
                                        verb in the request text. An address alone
                                        does not trigger sending.
    8. mailer.Mailer.send()            -> ONLY called if step 7 detected intent.
                                        Optional side effect: failure (including "not
                                        configured") never blocks the document response.
    9. database.save_document()       -> persists the full run for the History panel

Every stage logs structured events (agent/logutil.py: event_id, phase,
action, target, status, duration_ms, timestamp) rather than flat
sentences, so the frontend and this API can show real observability.

Run:
    python run.py
or:
    uvicorn main:app --reload
Then open:
    http://127.0.0.1:8000/          <- the app (frontend)
    http://127.0.0.1:8000/docs      <- interactive API docs
"""

from __future__ import annotations

import os
import time
import uuid

from dotenv import load_dotenv

# Load .env before anything else so all os.getenv() calls
# in the rest of the app pick up the right values.
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agent.schemas import (
    AgentRequest,
    AgentResponse,
    PlanStep,
    DocumentSection,
    ReflectionCheckModel,
    TimingBreakdown,
    LogEntry,
    AgentSummary,
    EmailResultModel,
    HistoryItem,
    HistoryDetail,
)
from agent.llm_client import LLMClient
from agent.planner import create_plan
from agent.executor import execute_plan
from agent.reflection import evaluate_sections, repair_sections
from agent.docx_builder import build_docx, patch_execution_time, patch_email_status
from agent.email_intent import detect_email_intent
from agent.mailer import Mailer
from agent import database, logutil
from backend.routes import router as api_router
from backend.database import init_db as init_platform_db

BASE_DIR = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(
    title="Autonomous Document Agent",
    description="An autonomous agent that plans, drafts, evaluates, and repairs its own output to produce a Word document from a natural language request.",
    version="3.0.0",
)

# Ensure the output directory exists on startup (not just at write time)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "uploads"), exist_ok=True)

database.init_db()
init_platform_db()


def build_summary(
    request_text: str,
    plan_result,
    execution_result,
    reflection_checks: list,
    reflection_confidence: float,
    total_ms: int,
) -> AgentSummary:
    """Compact, demo-friendly one-glance synthesis of the whole run."""
    regenerated = sum(1 for c in reflection_checks if c.status in ("regenerated", "strengthened"))
    issues = sum(1 for c in reflection_checks if c.status != "strong")
    return AgentSummary(
        intent=f"Create {plan_result.title}",
        detected_type=plan_result.document_type,
        classification_confidence=plan_result.classification_confidence,
        reflection_confidence=reflection_confidence,
        assumptions_count=len(plan_result.assumptions),
        reflection_issues=issues,
        sections_generated=len(execution_result.sections),
        sections_regenerated=regenerated,
        execution_time_ms=total_ms,
    )


@app.get("/health")
def health():
    return {
        "status": "ok",
        "llm_provider": os.getenv("LLM_PROVIDER", "groq"),
        "has_groq_key": bool(os.getenv("GROQ_API_KEY")),
        **database.stats(),
    }


@app.post("/agent", response_model=AgentResponse)
def run_agent(payload: AgentRequest):
    t_start = time.time()
    llm = LLMClient()
    structured_log: list[dict] = []

    # --- Step 1: autonomous planning -------------------------------------
    structured_log.append(logutil.event("planning", "start", "Planning started: classifying document type and drafting execution plan."))
    try:
        plan_result = create_plan(payload.request, llm)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Planning stage failed unrecoverably: {exc}")
    t_planning = time.time()
    planning_ms = int((t_planning - t_start) * 1000)
    structured_log.append(logutil.event(
        "planning", "classify",
        f"Classified as '{plan_result.document_type}' (confidence {plan_result.classification_confidence:.0%}). "
        f"{plan_result.classification_reasoning}",
        target=plan_result.document_type, status="success", duration_ms=planning_ms,
    ))

    if not plan_result.sections:
        raise HTTPException(status_code=502, detail="Planner produced no sections to draft.")

    # --- Step 2: execution (drafting) -------------------------------------
    execution_result = execute_plan(payload.request, plan_result, llm)
    t_drafting = time.time()
    drafting_ms = int((t_drafting - t_planning) * 1000)
    structured_log.extend(execution_result.log)

    # --- Step 3: reflection -- evaluate (pure assessment) ------------------
    evaluation = evaluate_sections(plan_result.document_type, execution_result.sections)

    # --- Step 4: reflection -- repair (acts only on evaluation findings) ---
    reflection_checks, reflection_events, reflection_confidence = repair_sections(
        plan_result.document_type, execution_result.sections, evaluation, llm
    )
    t_reflection = time.time()
    reflection_ms = int((t_reflection - t_drafting) * 1000)
    structured_log.extend(reflection_events)

    # --- Step 5: self-check guardrail before generating the file ------------
    missing = [s.title for s in execution_result.sections if not s.content.strip()]
    if missing:
        raise HTTPException(status_code=502, detail=f"Self-check failed: empty content for sections {missing}")

    # --- Step 6: build the plan step list + detect email intent -------------
    # Detection only, no side effect -- deliberately separated from the
    # actual send (further below, after persistence) so the plan records
    # the *decision* ("should this be delivered by email") independently
    # of the *action*, the same evaluate/act separation reflection.py uses
    # for content repair, applied here to tool invocation instead.
    plan_steps = [
        PlanStep(step_id=p.get("step_id", i + 1), name=p.get("name", ""), description=p.get("description", ""), status="done")
        for i, p in enumerate(plan_result.plan)
    ]
    intent = detect_email_intent(payload.request)
    next_step_id = len(plan_steps) + 1
    plan_steps.append(PlanStep(
        step_id=next_step_id, name="detect_email_intent",
        description=intent.reasoning, status="done",
    ))
    structured_log.append(logutil.event(
        "planning", "detect_email_intent", intent.reasoning,
        target=intent.recipient, status="success",
    ))
    if intent.requested:
        plan_steps.append(PlanStep(
            step_id=next_step_id + 1, name="send_email",
            description=f"Deliver the generated document to {intent.recipient}.", status="pending",
        ))

    # --- Step 7: document generation --------------------------------------
    file_stem = f"{plan_result.document_type}_{uuid.uuid4().hex[:8]}"
    t_docx_start = time.time()
    total_ms_estimate = int((t_docx_start - t_start) * 1000)  # for summary before docx timing is final
    summary = build_summary(payload.request, plan_result, execution_result, reflection_checks, reflection_confidence, total_ms_estimate)
    summary.email_requested = intent.requested
    summary.email_recipient = intent.recipient
    summary.email_status = "pending" if intent.requested else "not_requested"

    try:
        file_path = build_docx(
            payload.request, plan_result, execution_result, reflection_checks,
            reflection_confidence, summary.model_dump(), OUTPUT_DIR, file_stem,
        )
        file_name = os.path.basename(file_path)
        t_docx = time.time()
        docx_ms = int((t_docx - t_reflection) * 1000)
        total_ms = int((t_docx - t_start) * 1000)
        summary.execution_time_ms = total_ms
        patch_execution_time(file_path, total_ms)
    except Exception as exc:
        # Document assembly is filesystem I/O (disk full, permissions, a
        # locked/renamed output directory) -- exactly the kind of thing
        # that can fail independent of anything the agent decided. Fail
        # as a structured 502 with the request's context intact, not a
        # raw 500 stack trace.
        structured_log.append(logutil.event("docx", "assemble", f"Document assembly failed: {exc}", status="error"))
        raise HTTPException(status_code=502, detail=f"Document assembly failed: {exc}")

    structured_log.append(logutil.event("docx", "assemble", f"Document assembled -> {file_name}.", target=file_name, status="success", duration_ms=docx_ms))
    structured_log.append(logutil.event("docx", "complete", f"Run complete in {total_ms} ms.", status="success", duration_ms=total_ms))

    timing = TimingBreakdown(
        planning_ms=planning_ms,
        drafting_ms=drafting_ms,
        reflection_ms=reflection_ms,
        docx_ms=docx_ms,
        total_ms=total_ms,
    )

    sections = [DocumentSection(title=s.title, content=s.content) for s in execution_result.sections]
    reflection_models = [ReflectionCheckModel(label=c.label, status=c.status, note=c.note) for c in reflection_checks]

    # Placeholder result until the send is actually attempted (after
    # persistence, below). Nothing has been sent yet at this point.
    email_model = EmailResultModel(
        requested=intent.requested,
        recipient=intent.recipient,
        status="pending" if intent.requested else "not_requested",
    )
    log_models = [LogEntry(**e) for e in structured_log]

    # --- Step 8: persist to database FIRST ----------------------------------
    # The document and its database record must exist and be stable before
    # any optional side effect (email) is attempted. This guarantees: the
    # .docx exists on disk, the row has a stable id, and an email failure
    # can never roll back or orphan a successfully generated document. If
    # email later succeeds or fails, that update lands on this same row
    # rather than being bundled into a single all-or-nothing write.
    try:
        doc_id = database.save_document(
            request_text=payload.request,
            document_type=plan_result.document_type,
            title=plan_result.title,
            classification_confidence=plan_result.classification_confidence,
            classification_reasoning=plan_result.classification_reasoning,
            reflection_confidence=reflection_confidence,
            assumptions=plan_result.assumptions,
            plan=[p.model_dump() for p in plan_steps],
            sections=[s.model_dump() for s in sections],
            reflection=[r.model_dump() for r in reflection_models],
            timing=timing.model_dump(),
            execution_log=structured_log,
            email=email_model.model_dump(),
            llm_mode=execution_result.overall_mode,
            file_name=file_name,
        )
    except Exception as exc:
        # The document itself was already written successfully at this
        # point -- a DB failure shouldn't discard that. Log it, fall back
        # to an in-memory id, and let the caller still get their file;
        # it just won't show up in History until the DB issue is fixed.
        structured_log.append(logutil.event("docx", "persist", f"Database save failed, continuing without history entry: {exc}", status="error"))
        doc_id = -1

    # --- Step 9: email delivery -- ONLY after the document is persisted -----
    # This is the executor invoking a tool (mailer.py) based on the
    # planning-stage decision, not the planner sending anything itself.
    # Failure here is captured, never raised: the primary task (document
    # generation) already succeeded and that success is not reversed by an
    # optional delivery step failing.
    if intent.requested:
        mailer = Mailer()
        t_email = time.time()
        send_result = mailer.send(
            recipient=intent.recipient,
            subject=plan_result.title,
            body=(
                f"Attached: {plan_result.title} ({plan_result.document_type.replace('_', ' ')}), "
                f"generated by the autonomous document agent from the request:\n\n\"{payload.request}\""
            ),
            attachment_path=file_path,
        )
        email_duration_ms = int((time.time() - t_email) * 1000)

        email_model = EmailResultModel(
            requested=True,
            recipient=send_result.recipient,
            status=send_result.status,
            error=send_result.error,
        )
        summary.email_requested = True
        summary.email_recipient = send_result.recipient
        summary.email_status = send_result.status
        summary.email_duration_ms = email_duration_ms

        tool_event = logutil.event(
            "tool", "send_email",
            f"Email delivered with .docx attachment." if send_result.status == "sent" else f"Email delivery failed: {send_result.error}",
            target=intent.recipient,
            status="success" if send_result.status == "sent" else "failed",
            duration_ms=email_duration_ms,
        )
        structured_log.append(tool_event)
        log_models.append(LogEntry(**tool_event))
        for step in plan_steps:
            if step.name == "send_email":
                step.status = "done" if send_result.status == "sent" else "failed"

        # Update the already-persisted row in place -- never re-insert.
        if doc_id != -1:
            try:
                database.update_email_result(doc_id, email_model.model_dump(), plan=[p.model_dump() for p in plan_steps], execution_log=structured_log)
            except Exception as exc:
                structured_log.append(logutil.event("tool", "persist_email_status", f"Failed to persist email status update: {exc}", status="error"))

        # The .docx already on disk (and any copy already attached to the
        # email) can't retroactively know its own delivery outcome, but the
        # downloadable copy on disk can still be patched with the final
        # status for anyone who opens it after the fact.
        try:
            patch_email_status(file_path, email_model.model_dump(), email_duration_ms)
        except Exception:
            pass  # cosmetic patch only; never fail the request over it

    return AgentResponse(
        id=doc_id,
        status="success",
        document_type=plan_result.document_type,
        title=plan_result.title,
        classification_confidence=plan_result.classification_confidence,
        classification_reasoning=plan_result.classification_reasoning,
        reflection_confidence=reflection_confidence,
        assumptions=plan_result.assumptions,
        plan=plan_steps,
        sections=sections,
        reflection=reflection_models,
        timing=timing,
        execution_log=log_models,
        summary=summary,
        email=email_model,
        llm_mode=execution_result.overall_mode,
        file_name=file_name,
        download_url=f"/agent/download/{file_name}",
        message=f"Generated a {plan_result.document_type.replace('_', ' ')} titled '{plan_result.title}'.",
    )


@app.get("/agent/download/{file_name}")
def download(file_name: str):
    safe_name = os.path.basename(file_name)  # guard against path traversal
    file_path = os.path.join(OUTPUT_DIR, safe_name)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=safe_name,
    )


@app.get("/documents", response_model=list[HistoryItem])
def list_documents():
    records = database.list_documents()
    return [
        HistoryItem(
            id=r.id,
            request_text=r.request_text,
            document_type=r.document_type,
            title=r.title,
            llm_mode=r.llm_mode,
            file_name=r.file_name,
            download_url=f"/agent/download/{r.file_name}",
            created_at=r.created_at,
        )
        for r in records
    ]


@app.get("/documents/{doc_id}", response_model=HistoryDetail)
def get_document(doc_id: int):
    r = database.get_document(doc_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Document not found")

    reflection_models = [ReflectionCheckModel(**c) for c in r.reflection]
    regenerated = sum(1 for c in reflection_models if c.status in ("regenerated", "strengthened"))
    issues = sum(1 for c in reflection_models if c.status != "strong")
    timing = TimingBreakdown(**r.timing) if r.timing else TimingBreakdown(planning_ms=0, drafting_ms=0, reflection_ms=0, docx_ms=0, total_ms=0)

    summary = AgentSummary(
        intent=f"Create {r.title}",
        detected_type=r.document_type,
        classification_confidence=r.classification_confidence,
        reflection_confidence=r.reflection_confidence,
        assumptions_count=len(r.assumptions),
        reflection_issues=issues,
        sections_generated=len(r.sections),
        sections_regenerated=regenerated,
        execution_time_ms=timing.total_ms,
        email_requested=r.email.get("requested", False),
        email_recipient=r.email.get("recipient"),
        email_status=r.email.get("status", "not_requested"),
    )

    return HistoryDetail(
        id=r.id,
        status="success",
        document_type=r.document_type,
        title=r.title,
        classification_confidence=r.classification_confidence,
        classification_reasoning=r.classification_reasoning,
        reflection_confidence=r.reflection_confidence,
        assumptions=r.assumptions,
        plan=[PlanStep(**p) for p in r.plan],
        sections=[DocumentSection(**s) for s in r.sections],
        reflection=reflection_models,
        timing=timing,
        execution_log=[LogEntry(**e) for e in r.execution_log],
        summary=summary,
        email=EmailResultModel(**r.email),
        llm_mode=r.llm_mode,
        file_name=r.file_name,
        download_url=f"/agent/download/{r.file_name}",
        message=f"Generated a {r.document_type.replace('_', ' ')} titled '{r.title}'.",
        created_at=r.created_at,
    )


# --- Document Intelligence API (v1) --------------------------------------
# Mounted before the frontend so /api/v1/* routes take priority.
app.include_router(api_router)

# --- Frontend -----------------------------------------------------------
# Mounted last so it never shadows the API routes above; "html=True" makes
# "/" serve static/index.html and enables client-side deep links.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
