"""
API Routes for the Ledger Document Intelligence Platform.

Endpoints:
- POST /api/v1/documents/upload - Upload a document for processing
- GET /api/v1/documents - List all documents
- GET /api/v1/documents/{id} - Get document details
- DELETE /api/v1/documents/{id} - Delete a document
- POST /api/v1/extract - Extract data from document
- GET /api/v1/extract/{id} - Get extraction results
- POST /api/v1/validate - Validate extracted data
- GET /api/v1/confidence/{id} - Get confidence scores
- POST /api/v1/workflows/run - Run a workflow
- GET /api/v1/workflows/history - Get workflow history
- GET /api/v1/system - System health and stats
"""

from __future__ import annotations

import os
import json
import time
import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse

from backend.database import Document, ExtractionResult, WorkflowLog, SessionLocal
from agents.orchestrator import Orchestrator
from agents.schemas import DocumentContext
from ocr.engine import OCREngine
from extraction.extractor import Extractor
from validation.validator import Validator
from workflows.engine import WorkflowEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")


def ensure_upload_dir():
    os.makedirs(UPLOAD_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a document for AI processing.
    Supports: PDF, PNG, JPG, TIFF, DOCX, TXT
    """
    ensure_upload_dir()
    file_id = uuid.uuid4().hex[:12]
    ext = os.path.splitext(file.filename or "unknown")[1] or ".bin"
    safe_name = f"{file_id}{ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)

    contents = await file.read()

    # Save file
    with open(file_path, "wb") as f:
        f.write(contents)

    # Save to database
    db = SessionLocal()
    try:
        doc = Document(
            filename=file.filename or safe_name,
            file_path=file_path,
            file_size=len(contents),
            mime_type=file.content_type or "application/octet-stream",
            status="uploaded",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        return {
            "id": doc.id,
            "filename": doc.filename,
            "status": "uploaded",
            "file_size": doc.file_size,
            "message": "Document uploaded successfully",
        }
    finally:
        db.close()


@router.get("/documents")
def list_documents(skip: int = 0, limit: int = 50):
    """List all uploaded documents."""
    db = SessionLocal()
    try:
        docs = (
            db.query(Document)
            .order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return [
            {
                "id": d.id,
                "filename": d.filename,
                "doc_type": d.doc_type,
                "status": d.status,
                "file_size": d.file_size,
                "confidence": d.doc_type_confidence,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in docs
        ]
    finally:
        db.close()


@router.get("/documents/{doc_id}")
def get_document(doc_id: int):
    """Get detailed document info including extraction results."""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        return {
            "id": doc.id,
            "filename": doc.filename,
            "file_path": doc.file_path,
            "file_size": doc.file_size,
            "mime_type": doc.mime_type,
            "doc_type": doc.doc_type,
            "doc_type_confidence": doc.doc_type_confidence,
            "status": doc.status,
            "extracted_data": doc.extracted_data,
            "validation_results": doc.validation_results,
            "confidence_scores": doc.confidence_scores,
            "processing_time_ms": doc.processing_time_ms,
            "error_message": doc.error_message,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        }
    finally:
        db.close()


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int):
    """Delete a document and its file."""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # Delete file
        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)

        db.delete(doc)
        db.commit()
        return {"message": "Document deleted", "id": doc_id}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Pipeline: Process (OCR -> Classify -> Extract -> Validate)
# ---------------------------------------------------------------------------


@router.post("/process/{doc_id}")
def process_document(doc_id: int):
    """
    Run the full AI pipeline on a document:
    OCR -> Classification -> Extraction -> Validation
    """
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        if doc.status == "failed":
            raise HTTPException(status_code=400, detail="Document previously failed processing")

        # Read file bytes
        with open(doc.file_path, "rb") as f:
            file_bytes = f.read()

        # Build document context
        ctx = DocumentContext(
            id=doc.id,
            filename=doc.filename,
            file_path=doc.file_path,
            mime_type=doc.mime_type,
            raw_bytes=file_bytes,
            status="processing",
        )

        # Run pipeline
        ocr = OCREngine()
        extractor = Extractor()
        validator = Validator()
        orchestrator = Orchestrator(ocr_engine=ocr, extractor=extractor, validator=validator)
        result = orchestrator.run_full_pipeline(ctx)

        # Update database
        doc.status = result.status
        doc.ocr_text = result.ocr_text[:10000] if result.ocr_text else ""
        doc.doc_type = result.doc_type
        doc.doc_type_confidence = result.doc_type_confidence
        doc.extracted_data = result.extracted_fields
        doc.confidence_scores = result.confidence_scores
        doc.processing_time_ms = result.processing_time_ms
        if result.validation_errors:
            doc.error_message = "; ".join(result.validation_errors)

        # Run validation separately for detailed results
        validation = validator.validate(result.doc_type, result.extracted_fields)
        doc.validation_results = {
            "passed": validation.passed,
            "overall_confidence": validation.overall_confidence,
            "requires_human_review": validation.requires_human_review,
            "field_errors": validation.field_errors,
            "field_warnings": validation.field_warnings,
        }

        # Save extraction result
        ext_result = ExtractionResult(
            document_id=doc.id,
            doc_type=result.doc_type,
            fields=result.extracted_fields,
            confidence_overall=validation.overall_confidence,
        )
        db.add(ext_result)

        # Log workflow step
        wf_log = WorkflowLog(
            document_id=doc.id,
            action="process_document",
            status="completed" if result.status != "failed" else "failed",
            details={
                "doc_type": result.doc_type,
                "confidence": result.doc_type_confidence,
                "processing_time_ms": result.processing_time_ms,
            },
        )
        db.add(wf_log)
        db.commit()

        return {
            "id": doc.id,
            "status": doc.status,
            "doc_type": doc.doc_type,
            "doc_type_confidence": doc.doc_type_confidence,
            "extracted_fields": result.extracted_fields,
            "confidence_scores": result.confidence_scores,
            "validation": doc.validation_results,
            "processing_time_ms": result.processing_time_ms,
            "errors": result.validation_errors,
            "warnings": result.validation_warnings,
        }
    except Exception as e:
        logger.exception(f"Processing failed for document {doc_id}")
        if doc:
            doc.status = "failed"
            doc.error_message = str(e)[:500]
            db.commit()
        raise HTTPException(status_code=500, detail=f"Processing failed: {e}")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Extraction results
# ---------------------------------------------------------------------------


@router.get("/extract/{doc_id}")
def get_extraction(doc_id: int):
    """Get extraction results for a document."""
    db = SessionLocal()
    try:
        result = (
            db.query(ExtractionResult)
            .filter(ExtractionResult.document_id == doc_id)
            .order_by(ExtractionResult.created_at.desc())
            .first()
        )
        if not result:
            raise HTTPException(status_code=404, detail="No extraction results found")

        return {
            "id": result.id,
            "document_id": result.document_id,
            "doc_type": result.doc_type,
            "fields": result.fields,
            "confidence_overall": result.confidence_overall,
            "agent_version": result.agent_version,
            "created_at": result.created_at.isoformat() if result.created_at else None,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------


@router.post("/workflows/run")
def run_workflow(doc_id: int = 0, workflow: str = "auto_archive"):
    """Run a workflow for a document."""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        engine = WorkflowEngine()
        result = engine.run_workflow(workflow, doc_id)

        # Log workflow steps
        for step in result.steps:
            wf_log = WorkflowLog(
                document_id=doc_id,
                action=step.name,
                status=step.status.value,
                details={"step": step.action, "assigned_to": step.assigned_to},
            )
            db.add(wf_log)
        db.commit()

        return {
            "workflow": result.workflow_name,
            "document_id": result.document_id,
            "status": result.status.value,
            "steps": [
                {"name": s.name, "action": s.action, "status": s.status.value}
                for s in result.steps
            ],
        }
    finally:
        db.close()


@router.get("/workflows/history")
def workflow_history(limit: int = 50):
    """Get workflow execution history."""
    db = SessionLocal()
    try:
        logs = (
            db.query(WorkflowLog)
            .order_by(WorkflowLog.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": log.id,
                "document_id": log.document_id,
                "action": log.action,
                "status": log.status,
                "duration_ms": log.duration_ms,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------


@router.get("/system")
def system_health():
    """System health and statistics."""
    db = SessionLocal()
    try:
        total_docs = db.query(Document).count()
        completed = (
            db.query(Document).filter(Document.status == "completed").count()
        )
        failed = db.query(Document).filter(Document.status == "failed").count()
        pending_review = (
            db.query(Document)
            .filter(Document.status == "human_review")
            .count()
        )
        return {
            "status": "ok",
            "version": "2.0.0",
            "documents": {
                "total": total_docs,
                "completed": completed,
                "failed": failed,
                "pending_review": pending_review,
            },
            "ocr_engine": os.getenv("OCR_ENGINE", "pymupdf"),
            "llm_provider": os.getenv("LLM_PROVIDER", "groq"),
            "has_groq_key": bool(os.getenv("GROQ_API_KEY")),
        }
    finally:
        db.close()
