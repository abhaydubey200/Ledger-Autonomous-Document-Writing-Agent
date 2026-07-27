"""
Master Orchestrator Agent.

Coordinates the document intelligence pipeline:
Upload -> OCR -> Classify -> Extract -> Validate -> Complete

Each stage can be run independently or as part of the full pipeline.
"""

from __future__ import annotations

import time
import logging

from agents.schemas import DocumentContext, ClassificationResult, ExtractionResult, ValidationResult
from agents.classifier import classify as classify_document

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Coordinates the multi-agent document processing pipeline.

    Usage:
        orchestrator = Orchestrator()
        result = orchestrator.run_full_pipeline(document_id, file_path, file_bytes)
    """

    def __init__(self, ocr_engine=None, extractor=None, validator=None):
        self.ocr_engine = ocr_engine
        self.extractor = extractor
        self.validator = validator

    def run_full_pipeline(self, ctx: DocumentContext) -> DocumentContext:
        """
        Run the complete document intelligence pipeline end-to-end.
        """
        t_start = time.time()
        ctx.status = "processing"

        # Step 1: OCR
        ctx = self._run_ocr(ctx)
        if ctx.status == "failed":
            ctx.processing_time_ms = int((time.time() - t_start) * 1000)
            return ctx

        # Step 2: Classification
        ctx = self._run_classification(ctx)

        # Step 3: Extraction
        ctx = self._run_extraction(ctx)

        # Step 4: Validation
        ctx = self._run_validation(ctx)

        ctx.processing_time_ms = int((time.time() - t_start) * 1000)
        ctx.status = "completed"
        return ctx

    def _run_ocr(self, ctx: DocumentContext) -> DocumentContext:
        """Run OCR on the document."""
        ctx.status = "ocr_pending"
        if self.ocr_engine:
            try:
                result = self.ocr_engine.process(ctx.file_path, ctx.raw_bytes)
                ctx.ocr_text = result.text
                ctx.status = "ocr_complete"
            except Exception as e:
                ctx.status = "failed"
                ctx.validation_errors.append(f"OCR failed: {e}")
        else:
            # No OCR engine - try basic text extraction
            if ctx.mime_type == "text/plain" or not ctx.ocr_text:
                ctx.ocr_text = ctx.ocr_text or "(OCR not configured - text extraction unavailable)"
            ctx.status = "ocr_complete"
        return ctx

    def _run_classification(self, ctx: DocumentContext) -> DocumentContext:
        """Classify the document type from OCR text."""
        ctx.status = "classifying"
        try:
            result: ClassificationResult = classify_document(ctx.ocr_text)
            ctx.doc_type = result.doc_type
            ctx.doc_type_confidence = result.confidence
            ctx.status = "classified"
        except Exception as e:
            ctx.validation_errors.append(f"Classification failed: {e}")
            ctx.doc_type = "other"
            ctx.doc_type_confidence = 0.0
        return ctx

    def _run_extraction(self, ctx: DocumentContext) -> DocumentContext:
        """Extract structured fields based on document type."""
        ctx.status = "extracting"
        if self.extractor:
            try:
                result: ExtractionResult = self.extractor.extract(
                    doc_type=ctx.doc_type,
                    text=ctx.ocr_text,
                    ctx=ctx,
                )
                ctx.extracted_fields = result.fields
                ctx.confidence_scores = result.confidence
            except Exception as e:
                ctx.validation_errors.append(f"Extraction failed: {e}")
        ctx.status = "extracted"
        return ctx

    def _run_validation(self, ctx: DocumentContext) -> DocumentContext:
        """Validate extracted data against business rules."""
        ctx.status = "validating"
        if self.validator:
            try:
                result: ValidationResult = self.validator.validate(
                    doc_type=ctx.doc_type,
                    fields=ctx.extracted_fields,
                )
                ctx.validation_errors = []
                for field, errors in result.field_errors.items():
                    ctx.validation_errors.extend(errors)
                for field, warnings in result.field_warnings.items():
                    ctx.validation_warnings.extend(warnings)
            except Exception as e:
                ctx.validation_errors.append(f"Validation failed: {e}")
        ctx.status = "validated"
        return ctx
