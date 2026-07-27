"""
Entity Extraction Engine.

Extracts structured fields from OCR text based on document type.
Uses keyword/regex matching as a fallback when no LLM is available.
"""

from __future__ import annotations

import re
import logging
from typing import Any

from agents.schemas import ExtractionResult
from extraction.fields import get_fields_for_type, FieldDef

logger = logging.getLogger(__name__)


class Extractor:
    """
    Extracts structured fields from document text.

    Uses rule-based extraction with keyword/regex patterns.
    Can be extended with LLM-based extraction for higher accuracy.
    """

    def extract(self, doc_type: str, text: str, ctx=None) -> ExtractionResult:
        """
        Extract fields from OCR text for a given document type.

        Args:
            doc_type: The classified document type
            text: The OCR text content
            ctx: Optional document context for enrichment

        Returns:
            ExtractionResult with extracted fields and confidence scores
        """
        if not text or not text.strip():
            return ExtractionResult(
                fields={},
                confidence={},
                raw_text="",
                agent_used="rule",
            )

        fields = get_fields_for_type(doc_type)
        extracted: dict[str, Any] = {}
        confidences: dict[str, float] = {}

        for field_def in fields:
            value, confidence = self._extract_field(field_def, text)
            if value is not None:
                extracted[field_def.name] = value
                confidences[field_def.name] = confidence

        return ExtractionResult(
            fields=extracted,
            confidence=confidences,
            raw_text=text[:500],
            agent_used="rule",
        )

    def _extract_field(self, field_def: FieldDef, text: str) -> tuple[Any, float]:
        """
        Extract a single field using patterns and heuristics.

        Returns (value, confidence).
        """
        lower_text = text.lower()

        # Try pattern-based extraction first
        for pattern in field_def.patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0), 0.85

        # For required fields, try keyword proximity
        if field_def.required:
            # Look for the field label near a value
            label_parts = field_def.label.lower().split()
            for part in label_parts:
                if len(part) > 3 and part in lower_text:
                    # Found the label keyword, try to extract nearby value
                    idx = lower_text.index(part)
                    context = text[idx:idx + 100]
                    # Try to find a value after a colon or separator
                    value_match = re.search(
                        r":\s*([^\n]{2,60})", context
                    )
                    if value_match:
                        return value_match.group(1).strip(), 0.6

        # Fallback: check if the field name or its patterns appear anywhere
        all_keywords = [field_def.label.lower()] + [p.lower() for p in field_def.patterns]
        total_hits = sum(1 for kw in all_keywords if kw[:4] in lower_text)

        if total_hits > 0:
            # Present but unstructured - low confidence
            return f"(present but unstructured)", 0.3

        return None, 0.0
