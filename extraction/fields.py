"""
Field definitions for entity extraction per document type.

Each doc type has a list of FieldDef objects describing what to extract,
the extraction strategy, and validation rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FieldDef:
    """Definition of an extractable field."""
    name: str
    label: str
    field_type: str = "string"  # string, number, date, currency, enum
    required: bool = False
    patterns: list[str] = field(default_factory=list)  # regex or keyword hints
    enum_values: list[str] | None = None  # for enum type
    description: str = ""


# Invoice fields
INVOICE_FIELDS = [
    FieldDef("invoice_number", "Invoice Number", required=True,
             patterns=[r"INV[-\s]?\d+", r"Invoice\s*#?\s*:?\s*\S+"]),
    FieldDef("invoice_date", "Invoice Date", field_type="date", required=True,
             patterns=[r"\d{2}[-/]\d{2}[-/]\d{4}", r"\d{4}[-/]\d{2}[-/]\d{2}"]),
    FieldDef("vendor_name", "Vendor Name", required=True),
    FieldDef("vendor_gst", "GST Number",
             patterns=[r"\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}"]),
    FieldDef("total_amount", "Total Amount", field_type="currency", required=True,
             patterns=[r"Total\s*:?\s*[₹$€]?\s*[\d,]+\.?\d*"]),
    FieldDef("tax_amount", "Tax Amount", field_type="currency",
             patterns=[r"Tax\s*:?\s*[₹$€]?\s*[\d,]+\.?\d*", r"GST\s*:?\s*[₹$€]?\s*[\d,]+\.?\d*"]),
    FieldDef("currency", "Currency", field_type="enum",
             enum_values=["INR", "USD", "EUR", "GBP", "AUD", "CAD", "SGD"]),
    FieldDef("po_number", "Purchase Order Number"),
    FieldDef("due_date", "Due Date", field_type="date"),
    FieldDef("line_items", "Line Items", field_type="string"),  # raw line items text
]

# Purchase Order fields
PO_FIELDS = [
    FieldDef("po_number", "PO Number", required=True,
             patterns=[r"PO[-\s]?\d+", r"Purchase\s*Order\s*#?\s*:?\s*\S+"]),
    FieldDef("po_date", "PO Date", field_type="date", required=True),
    FieldDef("vendor_name", "Vendor Name", required=True),
    FieldDef("total_amount", "Total Amount", field_type="currency", required=True),
    FieldDef("delivery_date", "Delivery Date", field_type="date"),
    FieldDef("currency", "Currency", field_type="enum",
             enum_values=["INR", "USD", "EUR", "GBP"]),
    FieldDef("payment_terms", "Payment Terms"),
]

# Contract fields
CONTRACT_FIELDS = [
    FieldDef("contract_title", "Contract Title", required=True),
    FieldDef("party_a", "Party A (First Party)", required=True),
    FieldDef("party_b", "Party B (Second Party)", required=True),
    FieldDef("effective_date", "Effective Date", field_type="date", required=True),
    FieldDef("expiry_date", "Expiry Date", field_type="date"),
    FieldDef("governing_law", "Governing Law"),
    FieldDef("contract_value", "Contract Value", field_type="currency"),
]

# Bank statement fields
BANK_STATEMENT_FIELDS = [
    FieldDef("account_number", "Account Number", required=True,
             patterns=[r"A/c\s*No\.?\s*:?\s*\d+", r"Account\s*Number\s*:?\s*\d+"]),
    FieldDef("account_holder", "Account Holder Name"),
    FieldDef("bank_name", "Bank Name"),
    FieldDef("opening_balance", "Opening Balance", field_type="currency"),
    FieldDef("closing_balance", "Closing Balance", field_type="currency"),
    FieldDef("statement_period", "Statement Period"),
    FieldDef("transactions", "Transactions", field_type="string"),
]

# Receipt fields
RECEIPT_FIELDS = [
    FieldDef("receipt_number", "Receipt Number"),
    FieldDef("date", "Date", field_type="date", required=True),
    FieldDef("amount", "Amount", field_type="currency", required=True),
    FieldDef("merchant_name", "Merchant Name"),
    FieldDef("payment_method", "Payment Method"),
]

# Document type to field mapping
FIELD_MAP: dict[str, list[FieldDef]] = {
    "invoice": INVOICE_FIELDS,
    "purchase_order": PO_FIELDS,
    "contract": CONTRACT_FIELDS,
    "bank_statement": BANK_STATEMENT_FIELDS,
    "receipt": RECEIPT_FIELDS,
    "tax_document": [],
    "identity_document": [],
    "shipping_document": [],
    "utility_bill": [],
    "other": [],
}


def get_fields_for_type(doc_type: str) -> list[FieldDef]:
    """Get the field definitions for a given document type."""
    return FIELD_MAP.get(doc_type, [])
