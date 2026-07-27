"""
Comprehensive tests for the Ledger Document Intelligence Platform.

Covers: classifier, extractor, validator, orchestrator, OCR engine, workflows.

Run with:
    pytest tests/test_platform.py -v
"""

import os
import tempfile
import json

# ---------------------------------------------------------------------------
# agents/classifier.py tests
# ---------------------------------------------------------------------------

from agents.classifier import classify


class TestClassifier:
    def test_classify_invoice(self):
        result = classify("INVOICE NUMBER: INV-001\nTotal Amount: $5,000.00\nGST: 123456")
        assert result.doc_type == "invoice"
        assert result.confidence > 0.5

    def test_classify_purchase_order(self):
        result = classify("PURCHASE ORDER PO-2024-001\nVendor: ABC Corp\nDelivery Date: 2024-03-01")
        assert result.doc_type == "purchase_order"
        assert result.confidence > 0.5

    def test_classify_contract(self):
        result = classify("CONTRACT AGREEMENT between Party A and Party B\nEffective Date: 2024-01-01\nSignature: ________")
        assert result.doc_type == "contract"

    def test_classify_bank_statement(self):
        result = classify("BANK STATEMENT\nAccount Number: 1234567890\nOpening Balance: $10,000")
        assert result.doc_type == "bank_statement"

    def test_classify_receipt(self):
        result = classify("RECEIPT\nTotal: $25.00\nThank you for your purchase!")
        assert result.doc_type == "receipt"

    def test_classify_identity_passport(self):
        result = classify("PASSPORT\nDate of Birth: 01/01/1990\nNationality: Indian")
        assert result.doc_type == "identity_document"

    def test_classify_shipping(self):
        result = classify("SHIPPING BILL\nConsignment Note\nTransport: ABC Logistics")
        assert result.doc_type == "shipping_document"

    def test_classify_utility_bill(self):
        result = classify("ELECTRICITY BILL\nConsumer Number: 12345\nMeter Reading: 1000")
        assert result.doc_type == "utility_bill"

    def test_classify_tax_document(self):
        result = classify("INCOME TAX RETURN\nPAN: ABCDE1234F\nAssessment Year: 2024-25")
        assert result.doc_type in ("tax_document", "identity_document")

    def test_classify_empty_text(self):
        result = classify("")
        assert result.doc_type == "other"
        assert result.confidence == 0.0

    def test_classify_gibberish(self):
        result = classify("zxcvbnm asdfghjkl qwertyuiop")
        assert result.doc_type == "other"
        assert result.confidence <= 0.2

    def test_classify_mixed_document(self):
        """A document with mixed signals should still pick the best match."""
        result = classify("INVOICE: INV-001\nThis is also an AGREEMENT between parties")
        assert result.doc_type == "invoice"  # invoice keywords stronger


# ---------------------------------------------------------------------------
# extraction/fields.py tests
# ---------------------------------------------------------------------------

from extraction.fields import get_fields_for_type, FieldDef, FIELD_MAP


class TestExtractionFields:
    def test_invoice_has_required_fields(self):
        fields = get_fields_for_type("invoice")
        names = [f.name for f in fields]
        assert "invoice_number" in names
        assert "total_amount" in names
        assert "vendor_name" in names

    def test_po_has_required_fields(self):
        fields = get_fields_for_type("purchase_order")
        names = [f.name for f in fields]
        assert "po_number" in names
        assert "total_amount" in names
        assert "vendor_name" in names

    def test_contract_has_required_fields(self):
        fields = get_fields_for_type("contract")
        names = [f.name for f in fields]
        assert "party_a" in names
        assert "party_b" in names
        assert "effective_date" in names

    def test_unknown_type_returns_empty(self):
        fields = get_fields_for_type("nonexistent")
        assert fields == []

    def test_field_def_attributes(self):
        fields = get_fields_for_type("invoice")
        field = [f for f in fields if f.name == "invoice_number"][0]
        assert field.required is True
        assert len(field.patterns) > 0
        assert field.label == "Invoice Number"

    def test_currency_field_has_enum(self):
        fields = get_fields_for_type("invoice")
        currency = [f for f in fields if f.name == "currency"][0]
        assert currency.field_type == "enum"
        assert "INR" in (currency.enum_values or [])

    def test_all_field_types_covered(self):
        """Every document type in FIELD_MAP should have at least some fields."""
        for doc_type in ["invoice", "purchase_order", "contract", "bank_statement", "receipt"]:
            fields = get_fields_for_type(doc_type)
            assert len(fields) > 0, f"{doc_type} has no fields defined"


# ---------------------------------------------------------------------------
# extraction/extractor.py tests
# ---------------------------------------------------------------------------

from extraction.extractor import Extractor


class TestExtractor:
    def make_extractor(self):
        return Extractor()

    def test_extract_invoice_number(self):
        ext = self.make_extractor()
        result = ext.extract("invoice", "INVOICE NUMBER: INV-001\nTotal: $1,500")
        assert "invoice_number" in result.fields
        assert result.fields["invoice_number"] is not None

    def test_extract_total_amount(self):
        ext = self.make_extractor()
        result = ext.extract("invoice", "Total Amount: $5,000.00")
        assert "total_amount" in result.fields

    def test_extract_invoice_date(self):
        ext = self.make_extractor()
        result = ext.extract("invoice", "Invoice Date: 2024-03-15")
        assert "invoice_date" in result.fields

    def test_extract_no_text(self):
        ext = self.make_extractor()
        result = ext.extract("invoice", "")
        assert result.fields == {}
        assert result.raw_text == ""

    def test_extract_confidence_scores_present(self):
        ext = self.make_extractor()
        result = ext.extract("invoice", "INVOICE: INV-001\nDate: 2024-01-01\nTotal: $100")
        for field_name in result.fields:
            assert field_name in result.confidence
            assert 0.0 <= result.confidence[field_name] <= 1.0

    def test_extract_unknown_doc_type(self):
        ext = self.make_extractor()
        result = ext.extract("unknown_type", "Some random text")
        assert result.fields == {}
        assert result.agent_used == "rule"

    def test_extract_po_number(self):
        ext = self.make_extractor()
        result = ext.extract("purchase_order", "PO Number: PO-2024-001")
        assert "po_number" in result.fields


# ---------------------------------------------------------------------------
# validation/validator.py tests
# ---------------------------------------------------------------------------

from validation.validator import Validator


class TestValidator:
    def make_validator(self):
        return Validator()

    def test_valid_invoice_passes(self):
        v = self.make_validator()
        fields = {
            "invoice_number": "INV-001",
            "invoice_date": "2024-03-15",
            "vendor_name": "ABC Corp",
            "total_amount": "$5,000.00",
        }
        result = v.validate("invoice", fields)
        assert result.passed or result.overall_confidence > 0.5

    def test_missing_required_field_fails(self):
        v = self.make_validator()
        result = v.validate("invoice", {})
        assert result.overall_confidence < 0.5
        assert len(result.field_errors) > 0

    def test_unknown_doc_type_passes_trivially(self):
        v = self.make_validator()
        result = v.validate("nonexistent_type", {})
        assert result.passed is True
        assert result.overall_confidence == 1.0

    def test_placeholder_text_lowers_confidence(self):
        v = self.make_validator()
        fields = {"invoice_number": "(present but unstructured)", "total_amount": "$100"}
        result = v.validate("invoice", fields)
        assert result.overall_confidence < 0.8

    def test_currency_validation_valid(self):
        v = self.make_validator()
        fields = {
            "invoice_number": "INV-001",
            "invoice_date": "2024-03-15",
            "vendor_name": "ABC Corp",
            "total_amount": "$1,500.00",
        }
        result = v.validate("invoice", fields)
        assert result.overall_confidence > 0.5

    def test_date_validation_invalid(self):
        v = self.make_validator()
        fields = {"invoice_date": "not-a-date"}
        result = v.validate("invoice", fields)
        assert result.overall_confidence <= 0.5

    def test_human_review_triggered_on_low_confidence(self):
        v = Validator()
        # Override threshold to test
        v.HUMAN_REVIEW_THRESHOLD = 0.8
        result = v.validate("invoice", {"invoice_number": "(present but unstructured)"})
        if result.overall_confidence < 0.8:
            assert result.requires_human_review is True


# ---------------------------------------------------------------------------
# ocr/engine.py tests
# ---------------------------------------------------------------------------

from ocr.engine import OCREngine


class TestOCREngine:
    def test_text_file_passthrough(self):
        ocr = OCREngine()
        # Use a temporary file that we fully control (close + reopen)
        import uuid
        tmpname = os.path.join(tempfile.gettempdir(), f"ledger_test_{uuid.uuid4().hex[:8]}.txt")
        with open(tmpname, "w") as f:
            f.write("Hello, this is a test document.")
        try:
            result = ocr.process(tmpname)
            assert "test document" in result.text
            assert result.engine_used == "passthrough"
            assert result.pages == 1
        finally:
            if os.path.exists(tmpname):
                os.unlink(tmpname)

    def test_ocr_empty_file(self):
        ocr = OCREngine()
        import uuid
        tmpname = os.path.join(tempfile.gettempdir(), f"ledger_test_{uuid.uuid4().hex[:8]}.txt")
        with open(tmpname, "w") as f:
            f.write("")
        try:
            result = ocr.process(tmpname)
            assert result.text == ""
            assert isinstance(result.processing_time_ms, int)
        finally:
            if os.path.exists(tmpname):
                os.unlink(tmpname)

    def test_ocr_unknown_extension(self):
        ocr = OCREngine()
        import uuid
        tmpname = os.path.join(tempfile.gettempdir(), f"ledger_test_{uuid.uuid4().hex[:8]}.xyz")
        with open(tmpname, "w") as f:
            f.write("test")
        try:
            result = ocr.process(tmpname)
            assert result.engine_used in ("passthrough", "none")
        finally:
            if os.path.exists(tmpname):
                os.unlink(tmpname)

    def test_ocr_processing_time_recorded(self):
        ocr = OCREngine()
        import uuid
        tmpname = os.path.join(tempfile.gettempdir(), f"ledger_test_{uuid.uuid4().hex[:8]}.txt")
        with open(tmpname, "w") as f:
            f.write("test content here")
        try:
            result = ocr.process(tmpname)
            assert result.processing_time_ms >= 0
        finally:
            if os.path.exists(tmpname):
                os.unlink(tmpname)

    def test_ocr_bytes_input(self):
        """Test that OCR works with bytes input."""
        ocr = OCREngine()
        tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
        tmp.write(b"bytes test content")
        tmp.close()
        with open(tmp.name, "rb") as f:
            content = f.read()
        result = ocr.process(tmp.name, file_bytes=content)
        os.unlink(tmp.name)
        assert result.engine_used == "passthrough"
        assert "bytes test" in result.text.lower()


# ---------------------------------------------------------------------------
# agents/orchestrator.py tests
# ---------------------------------------------------------------------------

from agents.orchestrator import Orchestrator
from agents.schemas import DocumentContext


class TestOrchestrator:
    def test_orchestrator_initializes(self):
        orch = Orchestrator()
        assert orch is not None
        assert orch.ocr_engine is None

    def test_orchestrator_full_pipeline_plain_text(self):
        """Run pipeline on a text file (no OCR needed)."""
        from ocr.engine import OCREngine

        ctx = DocumentContext(
            id=1,
            filename="test.txt",
            file_path="/tmp/test.txt",
            mime_type="text/plain",
            raw_bytes=b"INVOICE NUMBER: INV-001\nTotal Amount: $5,000.00\nVendor: ABC Corp",
        )
        orch = Orchestrator(ocr_engine=OCREngine())
        result = orch.run_full_pipeline(ctx)
        assert result.status in ("completed", "extracted", "classified")
        assert result.doc_type is not None

    def test_orchestrator_classification_only(self):
        """Test that orchestrator runs classification correctly."""
        ctx = DocumentContext(
            id=2,
            filename="doc.txt",
            file_path="/tmp/doc.txt",
            mime_type="text/plain",
            raw_bytes=b"PURCHASE ORDER PO-101",
        )
        orch = Orchestrator(ocr_engine=OCREngine())
        result = orch.run_full_pipeline(ctx)
        assert result.doc_type is not None
        assert result.doc_type_confidence > 0

    def test_orchestrator_empty_text(self):
        """Pipeline should handle empty text gracefully."""
        ctx = DocumentContext(
            id=3,
            filename="empty.txt",
            file_path="/tmp/empty.txt",
            mime_type="text/plain",
            raw_bytes=b"",
        )
        orch = Orchestrator(ocr_engine=OCREngine())
        result = orch.run_full_pipeline(ctx)
        assert result.doc_type == "other"
        assert result.processing_time_ms >= 0


# ---------------------------------------------------------------------------
# workflows/engine.py tests
# ---------------------------------------------------------------------------

from workflows.engine import WorkflowEngine, WorkflowStatus


class TestWorkflowEngine:
    def test_auto_archive_workflow(self):
        wf = WorkflowEngine()
        result = wf.run_workflow("auto_archive", 1)
        assert result.status == WorkflowStatus.COMPLETED
        assert len(result.steps) == 3
        assert result.document_id == 1

    def test_invoice_approval_workflow(self):
        wf = WorkflowEngine()
        result = wf.run_workflow("invoice_approval", 42)
        assert result.status == WorkflowStatus.IN_PROGRESS
        assert result.workflow_name == "invoice_approval"

    def test_document_review_workflow(self):
        wf = WorkflowEngine()
        result = wf.run_workflow("document_review", 7)
        assert result.status == WorkflowStatus.IN_PROGRESS
        assert result.document_id == 7

    def test_unknown_workflow_returns_error(self):
        wf = WorkflowEngine()
        result = wf.run_workflow("nonexistent_workflow", 1)
        assert result.status == WorkflowStatus.REJECTED
        assert result.error is not None

    def test_custom_workflow_registration(self):
        from workflows.engine import WorkflowResult
        wf = WorkflowEngine()
        def handler(doc_id, ctx):
            return WorkflowResult(
                workflow_name="custom",
                document_id=doc_id,
                status=WorkflowStatus.COMPLETED,
                steps=[],
            )
        wf.register_workflow("custom", handler)
        result = wf.run_workflow("custom", 1)
        assert result.status == WorkflowStatus.COMPLETED


# ---------------------------------------------------------------------------
# backend/routes.py / API integration tests
# ---------------------------------------------------------------------------

from fastapi.testclient import TestClient
import main


class TestAPIEndpoints:
    """Test the new API endpoints using FastAPI TestClient."""

    @classmethod
    def setup_class(cls):
        cls.client = TestClient(main.app)

    def test_health_endpoint_still_works(self):
        resp = self.client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_agent_endpoint_still_works(self):
        """The original document generation endpoint should still work."""
        resp = self.client.post(
            "/agent",
            json={"request": "Create a project plan for a mobile app"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["document_type"] is not None

    def test_system_endpoint(self):
        resp = self.client.get("/api/v1/system")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "documents" in data

    def test_upload_text_document(self):
        """Upload a text file for processing."""
        resp = self.client.post(
            "/api/v1/documents/upload",
            files={"file": ("test_invoice.txt", b"INVOICE: INV-001\nTotal: $500", "text/plain")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "uploaded"
        assert "id" in data
        assert data["filename"] == "test_invoice.txt"

    def test_upload_and_list_documents(self):
        resp = self.client.get("/api/v1/documents")
        assert resp.status_code == 200
        docs = resp.json()
        assert isinstance(docs, list)

    def test_upload_and_process_document(self):
        # Upload
        resp = self.client.post(
            "/api/v1/documents/upload",
            files={"file": ("invoice.txt", b"INVOICE NUMBER: INV-001\nTotal Amount: $5,000.00", "text/plain")},
        )
        doc_id = resp.json()["id"]

        # Process
        resp = self.client.post(f"/api/v1/process/{doc_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["doc_type"] == "invoice"
        assert data["status"] in ("completed", "classified", "extracted")

    def test_upload_and_get_detail(self):
        # Upload
        resp = self.client.post(
            "/api/v1/documents/upload",
            files={"file": ("doc.txt", b"Test document content", "text/plain")},
        )
        doc_id = resp.json()["id"]

        # Get detail
        resp = self.client.get(f"/api/v1/documents/{doc_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == doc_id
        assert "filename" in data
        assert "status" in data

    def test_upload_and_delete(self):
        resp = self.client.post(
            "/api/v1/documents/upload",
            files={"file": ("temp.txt", b"Temporary file", "text/plain")},
        )
        doc_id = resp.json()["id"]

        resp = self.client.delete(f"/api/v1/documents/{doc_id}")
        assert resp.status_code == 200

        # Verify deleted
        resp = self.client.get(f"/api/v1/documents/{doc_id}")
        assert resp.status_code == 404

    def test_upload_nonexistent_document_returns_404(self):
        resp = self.client.get("/api/v1/documents/99999")
        assert resp.status_code == 404

    def test_workflow_run(self):
        # Upload + process first
        resp = self.client.post(
            "/api/v1/documents/upload",
            files={"file": ("wf.txt", b"Test document for workflow", "text/plain")},
        )
        doc_id = resp.json()["id"]

        # Run workflow
        resp = self.client.post(f"/api/v1/workflows/run?doc_id={doc_id}&workflow=auto_archive")
        assert resp.status_code == 200
        data = resp.json()
        assert data["workflow"] == "auto_archive"
        assert data["document_id"] == doc_id

    def test_workflow_history(self):
        resp = self.client.get("/api/v1/workflows/history")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
