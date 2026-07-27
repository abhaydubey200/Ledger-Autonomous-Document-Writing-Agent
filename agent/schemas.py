"""
Pydantic schemas for the autonomous agent API.

These models double as the API's *request validation & input guardrail*
layer: FastAPI will automatically reject malformed input (wrong types,
missing fields) with a 422 before any agent logic runs, and the custom
validators below add business-rule checks (empty strings, absurd length)
on top of that.
"""

from pydantic import BaseModel, Field, field_validator


class AgentRequest(BaseModel):
    request: str = Field(
        ...,
        min_length=3,
        max_length=4000,
        description="Natural language description of the document the user needs.",
    )

    @field_validator("request")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("request must not be blank or whitespace-only")
        return v.strip()


class PlanStep(BaseModel):
    step_id: int
    name: str
    description: str
    status: str = "pending"  # pending -> running -> done / failed / fallback
    detail: str | None = None


class DocumentSection(BaseModel):
    title: str
    content: str


class TimingBreakdown(BaseModel):
    planning_ms: int
    drafting_ms: int
    reflection_ms: int
    docx_ms: int
    total_ms: int


class ReflectionCheckModel(BaseModel):
    label: str
    status: str  # strong | weak | missing | regenerated | strengthened | unresolved
    note: str


class LogEntry(BaseModel):
    """One structured event, not a flat sentence -- see agent/logutil.py."""
    event_id: str
    timestamp: str
    phase: str
    action: str
    target: str | None = None
    status: str
    duration_ms: int | None = None
    message: str


class EmailResultModel(BaseModel):
    requested: bool
    recipient: str | None = None
    status: str  # not_requested | sent | failed
    error: str | None = None


class AgentSummary(BaseModel):
    """Compact, demo-friendly synthesis of the whole run -- everything
    else in the response is the detail; this is the one-glance version."""
    intent: str
    detected_type: str
    classification_confidence: float
    reflection_confidence: float
    assumptions_count: int
    reflection_issues: int
    sections_generated: int
    sections_regenerated: int
    execution_time_ms: int
    email_requested: bool = False
    email_recipient: str | None = None
    email_status: str = "not_requested"
    email_duration_ms: int | None = None


class AgentResponse(BaseModel):
    id: int
    status: str
    document_type: str
    title: str
    classification_confidence: float
    classification_reasoning: str
    reflection_confidence: float
    assumptions: list[str]
    plan: list[PlanStep]
    sections: list[DocumentSection]
    reflection: list[ReflectionCheckModel]
    timing: TimingBreakdown
    execution_log: list[LogEntry]
    summary: AgentSummary
    email: EmailResultModel
    llm_mode: str  # "live" or "fallback"
    file_name: str
    download_url: str
    message: str


class HistoryItem(BaseModel):
    id: int
    request_text: str
    document_type: str
    title: str
    llm_mode: str
    file_name: str
    download_url: str
    created_at: str


class HistoryDetail(AgentResponse):
    created_at: str
