"""
Validation Engine.

Validates extracted data against business rules and computes
confidence scores. Flags low-confidence fields for human review.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from agents.schemas import ValidationResult
from extraction.fields import get_fields_for_type


class Validator:
    """
    Validates extracted document fields against business rules.

    Checks include:
    - Required fields are present
    - Date formats are valid
    - Currency values are numeric
    - Field-specific business rules
    """

    HUMAN_REVIEW_THRESHOLD = 0.6  # Below this, flag for human review

    def validate(self, doc_type: str, fields: dict[str, Any]) -> ValidationResult:
        """
        Validate extracted fields for a given document type.

        Args:
            doc_type: The classified document type
            fields: The extracted fields dict

        Returns:
            ValidationResult with errors, warnings, and overall confidence
        """
        field_defs = get_fields_for_type(doc_type)
        field_errors: dict[str, list[str]] = {}
        field_warnings: dict[str, list[str]] = {}
        total_confidence = 0.0
        field_count = 0

        # If no fields defined for this type, it passes trivially
        if not field_defs:
            return ValidationResult(
                passed=True,
                field_errors={},
                field_warnings={},
                overall_confidence=1.0,
                requires_human_review=False,
            )

        for field_def in field_defs:
            value = fields.get(field_def.name)
            conf = self._validate_field(field_def, value)
            field_count += 1
            total_confidence += conf.get("confidence", 0.0)

            if conf.get("errors"):
                field_errors[field_def.name] = conf["errors"]
            if conf.get("warnings"):
                field_warnings[field_def.name] = conf["warnings"]

        overall = round(total_confidence / field_count, 2) if field_count > 0 else 1.0
        requires_review = overall < self.HUMAN_REVIEW_THRESHOLD or bool(field_errors)

        return ValidationResult(
            passed=not bool(field_errors),
            field_errors=field_errors,
            field_warnings=field_warnings,
            overall_confidence=overall,
            requires_human_review=requires_review,
        )

    def _validate_field(self, field_def, value: Any) -> dict:
        """Validate a single field. Returns {confidence, errors, warnings}."""
        result: dict = {"confidence": 0.0, "errors": [], "warnings": []}

        if value is None or value == "":
            if field_def.required:
                result["errors"].append(f"{field_def.label} is required but missing")
                result["confidence"] = 0.0
            else:
                result["warnings"].append(f"{field_def.label} is missing (optional)")
                result["confidence"] = 0.3
            return result

        # Confidence based on value quality
        if isinstance(value, str):
            # Check for placeholder text
            if "(present but unstructured)" in value:
                result["warnings"].append(f"{field_def.label} found but not fully structured")
                result["confidence"] = 0.4
                return result

            # Check for "(OCR not configured)" 
            if "OCR not configured" in value:
                result["warnings"].append(f"{field_def.label}: OCR not available for this format")
                result["confidence"] = 0.2
                return result

            # Type-specific validation
            if field_def.field_type == "date":
                valid, msg = self._validate_date(value)
                if not valid:
                    result["warnings"].append(f"{field_def.label}: {msg}")
                    result["confidence"] = 0.5
                else:
                    result["confidence"] = 0.9

            elif field_def.field_type == "currency":
                valid, msg = self._validate_currency(value)
                if not valid:
                    result["warnings"].append(f"{field_def.label}: {msg}")
                    result["confidence"] = 0.5
                else:
                    result["confidence"] = 0.9

            elif field_def.field_type == "enum":
                if field_def.enum_values and value.upper() in [v.upper() for v in field_def.enum_values]:
                    result["confidence"] = 0.95
                else:
                    result["warnings"].append(f"{field_def.label}: '{value}' not in expected values")
                    result["confidence"] = 0.5
            else:
                # String field - basic confidence based on length
                if len(value) > 5:
                    result["confidence"] = 0.85
                else:
                    result["confidence"] = 0.6
        else:
            # Numeric or other type
            result["confidence"] = 0.8

        return result

    def _validate_date(self, value: str) -> tuple[bool, str]:
        """Validate a date string."""
        patterns = [
            (r"\d{4}[-/]\d{2}[-/]\d{2}", "%Y-%m-%d"),
            (r"\d{2}[-/]\d{2}[-/]\d{4}", "%d-%m-%Y"),
            (r"\d{2}\s+[A-Z][a-z]+\s+\d{4}", "%d %B %Y"),
        ]
        for pattern, fmt in patterns:
            if re.search(pattern, value):
                try:
                    datetime.strptime(value, fmt)
                    return True, ""
                except ValueError:
                    continue
        return False, "could not parse as a valid date"

    def _validate_currency(self, value: str) -> tuple[bool, str]:
        """Validate a currency value."""
        cleaned = re.sub(r"[₹$€£,\s]", "", value)
        try:
            float(cleaned)
            return True, ""
        except ValueError:
            return False, f"'{value}' is not a valid currency amount"
