"""
Database models for the Ledger Document Intelligence Platform.

Supports both SQLite (development) and PostgreSQL (production) via
the DATABASE_URL environment variable.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, JSON, Enum as SAEnum
from sqlalchemy.orm import declarative_base, sessionmaker
import enum

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ledger.db")
# SQLite needs check_same_thread=False for FastAPI
connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class DocType(str, enum.Enum):
    INVOICE = "invoice"
    PURCHASE_ORDER = "purchase_order"
    RECEIPT = "receipt"
    CONTRACT = "contract"
    BANK_STATEMENT = "bank_statement"
    TAX_DOCUMENT = "tax_document"
    IDENTITY_DOCUMENT = "identity_document"
    SHIPPING_DOCUMENT = "shipping_document"
    UTILITY_BILL = "utility_bill"
    OTHER = "other"


class ProcessingStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    OCR_PENDING = "ocr_pending"
    OCR_COMPLETE = "ocr_complete"
    CLASSIFYING = "classifying"
    CLASSIFIED = "classified"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    VALIDATING = "validating"
    VALIDATED = "validated"
    HUMAN_REVIEW = "human_review"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    filename = Column(String(512), nullable=False)
    file_path = Column(String(1024), nullable=False)
    file_size = Column(Integer, default=0)
    mime_type = Column(String(128), default="application/octet-stream")
    doc_type = Column(String(64), default="other")
    doc_type_confidence = Column(Float, default=0.0)
    status = Column(String(32), default="uploaded")
    ocr_text = Column(Text, default="")
    extracted_data = Column(JSON, default=dict)
    validation_results = Column(JSON, default=dict)
    confidence_scores = Column(JSON, default=dict)
    error_message = Column(String(1024), nullable=True)
    processing_time_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ExtractionResult(Base):
    __tablename__ = "extraction_results"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    document_id = Column(Integer, nullable=False, index=True)
    doc_type = Column(String(64), default="other")
    fields = Column(JSON, default=dict)  # {"field_name": {"value": "...", "confidence": 0.95, "source": "ai"}}
    raw_extraction = Column(JSON, default=dict)
    confidence_overall = Column(Float, default=0.0)
    agent_version = Column(String(32), default="1.0")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class WorkflowLog(Base):
    __tablename__ = "workflow_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    document_id = Column(Integer, nullable=False, index=True)
    action = Column(String(128), nullable=False)
    status = Column(String(32), default="pending")
    details = Column(JSON, default=dict)
    duration_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
