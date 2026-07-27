"""
Document Type Classifier Agent.

Identifies document types from OCR text using keyword-weighted
classification (fallback) or LLM-based classification (live).

Supports: invoice, purchase_order, receipt, contract, bank_statement,
tax_document, identity_document, shipping_document, utility_bill
"""

from __future__ import annotations

from agents.schemas import ClassificationResult

# Keyword scoring for each document type
# Format: (doc_type, [(keyword, weight), ...])
_TYPE_KEYWORDS: list[tuple[str, list[tuple[str, int]]]] = [
    ("invoice", [
        ("invoice", 5), ("inv no", 4), ("invoice number", 4), ("tax invoice", 5),
        ("gst", 3), ("total amount", 3), ("due date", 2), ("bill to", 2),
        ("vendor", 2), ("po number", 2), ("payment terms", 2),
    ]),
    ("purchase_order", [
        ("purchase order", 5), ("po number", 4), ("po date", 3),
        ("order date", 3), ("ship to", 2), ("vendor", 2),
        ("delivery date", 2), ("payment terms", 2),
    ]),
    ("receipt", [
        ("receipt", 5), ("total", 2), ("cash", 2), ("payment", 2),
        ("change", 1), ("thank you", 1),
    ]),
    ("contract", [
        ("contract", 5), ("agreement", 4), ("party", 3), ("hereby", 3),
        ("effective date", 3), ("termination", 2), ("indemnification", 2),
        ("confidentiality", 2), ("governing law", 2), ("signature", 2),
    ]),
    ("bank_statement", [
        ("bank statement", 5), ("account number", 4), ("opening balance", 3),
        ("closing balance", 3), ("transaction", 2), ("deposit", 2),
        ("withdrawal", 2), ("interest", 1),
    ]),
    ("tax_document", [
        ("tax", 3), ("return", 2), ("form", 2), ("pan", 3),
        ("assessment", 2), ("income tax", 4), ("filing", 2),
    ]),
    ("identity_document", [
        ("passport", 5), ("aadhaar", 5), ("pan card", 4), ("driving license", 4),
        ("date of birth", 3), ("father's name", 2), ("address", 1),
    ]),
    ("shipping_document", [
        ("shipping bill", 5), ("delivery challan", 4), ("consignment", 3),
        ("dispatch", 2), ("transport", 2), ("lr number", 3),
        ("waybill", 3), ("shipment", 2),
    ]),
    ("utility_bill", [
        ("bill", 3), ("electricity", 4), ("water", 3), ("gas", 3),
        ("utility", 3), ("meter reading", 3), ("connection", 2),
        ("consumer number", 3),
    ]),
]


def classify(text: str) -> ClassificationResult:
    """
    Deterministic document type classification using weighted keyword scoring.
    """
    if not text or not text.strip():
        return ClassificationResult(
            doc_type="other", confidence=0.0,
            reasoning="No text provided for classification."
        )

    lower_text = text.lower()
    scores: dict[str, int] = {}
    matched_terms: dict[str, list[str]] = {}

    for doc_type, keywords in _TYPE_KEYWORDS:
        hits = [kw for kw, _weight in keywords if kw in lower_text]
        score = sum(weight for kw, weight in keywords if kw in lower_text)
        if score > 0:
            scores[doc_type] = score
            matched_terms[doc_type] = hits

    if not scores:
        return ClassificationResult(
            doc_type="other", confidence=0.2,
            reasoning="No strong keyword signal found for known document types."
        )

    winner = max(scores, key=scores.get)
    total = sum(scores.values())
    confidence = round(scores[winner] / total, 2) if total else 0.0
    terms = ", ".join(f"'{t}'" for t in matched_terms[winner][:5])
    reasoning = (
        f"Matched keywords: {terms} (score {scores[winner]}/{total})"
    )

    return ClassificationResult(
        doc_type=winner,
        confidence=confidence,
        reasoning=reasoning,
    )
