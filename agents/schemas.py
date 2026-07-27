"""
Shared schemas for the multi-agent document intelligence pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DocumentContext:
    """Full context passed through the agent pipeline."""
    id: int
    filename: str
    file_path: str
    mime_type: str
    raw_bytes: bytes | None = None
    ocr_text: str = ""
    doc_type: str = "other"
    doc_type_confidence: float = 0.0
    extracted_fields: dict[str, Any] = field(default_factory=dict)
    confidence_scores: dict[str, float] = field(default_factory=dict)
    validation_errors: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)
    processing_time_ms: int = 0
    status: str = "uploaded"


@dataclass
class ClassificationResult:
    """Result from the document classifier agent."""
    doc_type: str
    confidence: float
    reasoning: str
    sub_type: str | None = None


@dataclass
class ExtractionResult:
    """Result from the entity extraction agent."""
    fields: dict[str, Any]
    confidence: dict[str, float]
    raw_text: str = ""
    agent_used: str = "llm"


@dataclass
class ValidationResult:
    """Result from the validation agent."""
    passed: bool
    field_errors: dict[str, list[str]]
    field_warnings: dict[str, list[str]]
    overall_confidence: float
    requires_human_review: bool = False
