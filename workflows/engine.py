"""
Workflow Engine.

Routes processed documents through configurable business workflows
(e.g., invoice approval, vendor verification, PO matching).
"""

from __future__ import annotations

import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    COMPLETED = "completed"


@dataclass
class WorkflowStep:
    name: str
    action: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    assigned_to: str | None = None
    notes: str | None = None


@dataclass
class WorkflowResult:
    workflow_name: str
    document_id: int
    status: WorkflowStatus
    steps: list[WorkflowStep] = field(default_factory=list)
    error: str | None = None


class WorkflowEngine:
    """
    Manages document processing workflows.

    Built-in workflows:
    - invoice_approval: Route invoices through finance approval
    - document_review: Route low-confidence docs for human review
    - auto_archive: Automatically archive completed documents
    """

    def __init__(self):
        self._handlers: dict[str, Callable] = {}

    def register_workflow(self, name: str, handler: Callable):
        """Register a custom workflow handler."""
        self._handlers[name] = handler

    def run_workflow(self, name: str, document_id: int, context: dict = None) -> WorkflowResult:
        """
        Execute a named workflow for a document.

        Args:
            name: Workflow name (e.g., 'invoice_approval', 'auto_archive')
            document_id: The document to process
            context: Additional context data

        Returns:
            WorkflowResult with status and step details
        """
        context = context or {}

        # Check for custom registered handler
        if name in self._handlers:
            return self._handlers[name](document_id, context)

        # Built-in workflows
        workflow_map = {
            "invoice_approval": self._invoice_approval,
            "document_review": self._document_review,
            "auto_archive": self._auto_archive,
        }

        handler = workflow_map.get(name)
        if not handler:
            return WorkflowResult(
                workflow_name=name,
                document_id=document_id,
                status=WorkflowStatus.REJECTED,
                error=f"Unknown workflow: {name}",
            )

        return handler(document_id, context)

    def _invoice_approval(self, document_id: int, context: dict) -> WorkflowResult:
        """Standard invoice approval workflow."""
        steps = [
            WorkflowStep("Validate invoice", "validation", WorkflowStatus.COMPLETED),
            WorkflowStep("Check PO matching", "po_match", WorkflowStatus.IN_PROGRESS),
            WorkflowStep("Finance review", "finance_review", WorkflowStatus.PENDING),
            WorkflowStep("Approval", "approval", WorkflowStatus.PENDING),
        ]
        return WorkflowResult(
            workflow_name="invoice_approval",
            document_id=document_id,
            status=WorkflowStatus.IN_PROGRESS,
            steps=steps,
        )

    def _document_review(self, document_id: int, context: dict) -> WorkflowResult:
        """Route document for human review when confidence is low."""
        steps = [
            WorkflowStep("AI extraction complete", "extraction", WorkflowStatus.COMPLETED),
            WorkflowStep("Flagged for human review", "human_review", WorkflowStatus.IN_PROGRESS),
            WorkflowStep("Manual verification", "verification", WorkflowStatus.PENDING),
        ]
        return WorkflowResult(
            workflow_name="document_review",
            document_id=document_id,
            status=WorkflowStatus.IN_PROGRESS,
            steps=steps,
        )

    def _auto_archive(self, document_id: int, context: dict) -> WorkflowResult:
        """Automatically archive a completed document."""
        steps = [
            WorkflowStep("Finalize extraction", "finalize", WorkflowStatus.COMPLETED),
            WorkflowStep("Generate audit trail", "audit", WorkflowStatus.COMPLETED),
            WorkflowStep("Archive document", "archive", WorkflowStatus.COMPLETED),
        ]
        return WorkflowResult(
            workflow_name="auto_archive",
            document_id=document_id,
            status=WorkflowStatus.COMPLETED,
            steps=steps,
        )
