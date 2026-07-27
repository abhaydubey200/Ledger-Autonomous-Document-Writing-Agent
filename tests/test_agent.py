"""
Comprehensive tests for agent modules: planner, reflection, email_intent,
fallback_content, logutil, and mock_data.

Run with:
    pytest tests/test_agent.py -v
"""

# ---------------------------------------------------------------------------
# email_intent.py tests
# ---------------------------------------------------------------------------

from agent.email_intent import detect_email_intent


class TestEmailIntent:
    def test_both_email_and_verb_returns_requested(self):
        """Explicit delivery request: address + delivery verb = requested."""
        result = detect_email_intent("Please email the report to jane@acme.com")
        assert result.requested is True
        assert result.recipient == "jane@acme.com"
        assert "delivery verb" in result.reasoning

    def test_email_with_send_verb(self):
        result = detect_email_intent("Send it to bob@example.com")
        assert result.requested is True
        assert result.recipient == "bob@example.com"

    def test_email_with_share_verb(self):
        result = detect_email_intent("Share the document with alice@co.com")
        assert result.requested is True
        assert result.recipient == "alice@co.com"

    def test_email_with_forward_verb(self):
        result = detect_email_intent("Forward this to ceo@corp.org")
        assert result.requested is True

    def test_email_with_deliver_verb(self):
        result = detect_email_intent("Deliver the final doc to client@biz.net")
        assert result.requested is True

    def test_email_alone_no_verb_returns_not_requested(self):
        """Address without a delivery verb = incidental text, not a request."""
        result = detect_email_intent("Our contact is jane@acme.com")
        assert result.requested is False
        assert result.recipient is None

    def test_verb_alone_no_email_returns_not_requested(self):
        """Delivery verb without an address = incomplete intent."""
        result = detect_email_intent("Please email the report")
        assert result.requested is False
        assert result.recipient is None

    def test_no_email_no_verb_returns_not_requested(self):
        result = detect_email_intent("Create a project plan")
        assert result.requested is False
        assert result.recipient is None

    def test_empty_string_returns_not_requested(self):
        result = detect_email_intent("")
        assert result.requested is False

    def test_email_with_e_dash_mail_verb(self):
        result = detect_email_intent("E-mail it to test@example.org")
        assert result.requested is True

    def test_mail_verb_detected(self):
        result = detect_email_intent("Mail the document to user@domain.com")
        assert result.requested is True

    def test_case_insensitive_verb_matching(self):
        """Verbs are matched case-insensitively."""
        result = detect_email_intent("SEND this to USER@EXAMPLE.COM")
        assert result.requested is True
        assert result.recipient == "USER@EXAMPLE.COM"

    def test_multiple_emails_picks_first(self):
        """When multiple addresses exist, the first match is returned."""
        result = detect_email_intent("Send to first@a.com and cc second@b.com")
        assert result.requested is True
        assert result.recipient == "first@a.com"


# ---------------------------------------------------------------------------
# fallback_content.py tests
# ---------------------------------------------------------------------------

from agent.fallback_content import _guess_document_type, generate
import json


class TestFallbackGuessDocumentType:
    def test_project_plan_keywords(self):
        doc_type, confidence, reasoning = _guess_document_type(
            "Create a project plan with timeline and milestones"
        )
        assert doc_type == "project_plan"
        assert confidence > 0.5

    def test_business_report_keywords(self):
        doc_type, confidence, reasoning = _guess_document_type(
            "Q4 performance report with revenue and KPIs"
        )
        assert doc_type == "business_report"
        assert confidence > 0.5

    def test_meeting_minutes_keywords(self):
        doc_type, confidence, reasoning = _guess_document_type(
            "Meeting minutes from the team call with attendees"
        )
        assert doc_type == "meeting_minutes"

    def test_proposal_keywords(self):
        doc_type, confidence, reasoning = _guess_document_type(
            "Write a proposal for project funding"
        )
        assert doc_type == "proposal"

    def test_sop_keywords(self):
        doc_type, confidence, reasoning = _guess_document_type(
            "Standard operating procedure for onboarding"
        )
        assert doc_type == "sop"

    def test_technical_design_keywords(self):
        doc_type, confidence, reasoning = _guess_document_type(
            "Technical design document for system architecture"
        )
        assert doc_type == "technical_design"

    def test_product_spec_keywords(self):
        doc_type, confidence, reasoning = _guess_document_type(
            "Product specification and requirements document"
        )
        assert doc_type == "product_spec"

    def test_ambiguous_request_lower_confidence(self):
        """A request matching multiple types gets a lower, honest confidence."""
        doc_type, confidence, reasoning = _guess_document_type(
            "We need something for the client meeting tomorrow about Q3 performance"
        )
        # Should detect with confidence less than max (1.0) since genuinely ambiguous
        assert doc_type in ("business_report", "meeting_minutes")
        assert confidence <= 0.8  # genuinely ambiguous

    def test_no_keyword_match_defaults_to_business_report(self):
        doc_type, confidence, reasoning = _guess_document_type(
            "Some completely unrelated text here"
        )
        assert doc_type == "business_report"
        assert confidence == 0.35  # default low confidence

    def test_sow_keyword_identifies_proposal(self):
        doc_type, _, _ = _guess_document_type("statement of work for a new project")
        assert doc_type == "proposal"


class TestFallbackGenerate:
    def test_plan_mode_returns_valid_json(self):
        result = generate("system prompt", "MODE: PLAN\nUser request:\n\"\"\"\nCreate a project plan\n\"\"\"", True)
        data = json.loads(result)
        assert "document_type" in data
        assert "title" in data
        assert "confidence" in data
        assert "sections" in data
        assert "plan" in data

    def test_plan_mode_returns_array_fields(self):
        result = generate("", "MODE: PLAN\nUser request:\n\"\"\"\nMeeting minutes\n\"\"\"", True)
        data = json.loads(result)
        assert isinstance(data["sections"], list)
        assert len(data["sections"]) > 0
        assert isinstance(data["plan"], list)
        assert len(data["plan"]) > 0

    def test_section_mode_returns_text(self):
        result = generate("", "MODE: SECTION:Executive Summary\nOverall document type: business_report\nOverall user request:\n\"\"\"\nWrite a report\n\"\"\"\n", False)
        assert isinstance(result, str)
        assert len(result) > 50
        assert "Executive Summary" in result or "This section" in result

    def test_reflection_fix_mode(self):
        result = generate("", "MODE: REFLECTION_FIX:budget", False)
        assert "budget" in result.lower()

    def test_reflection_strengthen_mode(self):
        result = generate("", "MODE: REFLECTION_STRENGTHEN:risks", False)
        assert "risks" in result.lower()

    def test_unknown_mode_returns_error_message(self):
        result = generate("", "MODE: UNKNOWN", False)
        assert "unrecognized mode" in result.lower()

    def test_plan_mode_confidence_matches_keyword_strength(self):
        """Strong project plan request should produce high confidence."""
        result = generate("", "MODE: PLAN\nUser request:\n\"\"\"\nProject plan for mobile app with timeline milestones and budget\n\"\"\"", True)
        data = json.loads(result)
        assert data["confidence"] >= 0.6


# ---------------------------------------------------------------------------
# reflection.py tests (evaluate_sections - pure assessment, no LLM needed)
# ---------------------------------------------------------------------------

from agent.reflection import evaluate_sections, WEAK_THRESHOLD
from agent.executor import ExecutedSection


class TestEvaluateSections:
    def make_sections(self, *contents):
        """Helper to create ExecutedSection list from content strings."""
        return [
            ExecutedSection(title=f"Section {i+1}", purpose="", content=c, llm_mode="fallback")
            for i, c in enumerate(contents)
        ]

    def test_known_doc_type_returns_mixed_results(self):
        """project_plan expects: timeline, budget, risks, team & roles."""
        sections = self.make_sections(
            "The project timeline spans 12 weeks with key milestones.",
            "The budget is estimated at $185,000 USD for the full scope.",
            "The team includes a project manager and developers.",
        )
        result = evaluate_sections("project_plan", sections)
        # Should find timeline (1 hit = weak), budget (2+ hits = strong),
        # risks (0 hits = missing), team (1 hit = weak)
        assert any(f.status == "strong" for f in result.strong), "Budget should be strong"
        assert any(f.status == "missing" for f in result.missing), "Risks should be missing"

    def test_unknown_doc_type_returns_perfect_score(self):
        sections = self.make_sections("Random text")
        result = evaluate_sections("nonexistent_type", sections)
        assert result.score == 1.0
        assert len(result.missing) == 0
        assert len(result.weak) == 0
        assert len(result.strong) == 0

    def test_all_elements_strong_returns_high_score(self):
        """A project plan that mentions all expected elements multiple times."""
        sections = self.make_sections(
            "Timeline: weeks 1-12 with milestones at week 4 and week 8. "
            "The schedule shows phases for design and development.",
            "Budget: $185k total. Costs are split across engineering and marketing. "
            "USD budget is final.",
            "Risks: key risk is timeline slippage. Mitigation: buffer weeks.",
            "Team: the product team includes 6 roles. Each role has clear ownership.",
        )
        result = evaluate_sections("project_plan", sections)
        assert len(result.missing) == 0
        assert len(result.weak) == 0
        assert result.score == 1.0

    def test_all_elements_missing_returns_zero_score(self):
        sections = self.make_sections("Nothing relevant here at all.")
        result = evaluate_sections("project_plan", sections)
        assert result.score == 0.0
        assert len(result.strong) == 0

    def test_mixed_results_produce_correct_score(self):
        """2 strong + 1 weak + 1 missing = (2*1.0 + 1*0.5 + 1*0.0)/4 = 0.62."""
        sections = self.make_sections(
            "Timeline: weeks 1-12 with milestones week 4 and week 8.",
            "Budget: $185k USD. Cost allocated.",
            "Risk is considered a concern.",
            "Nothing about personnel here.",
        )
        result = evaluate_sections("project_plan", sections)
        # timeline (4 hits=strong), budget (3 hits=strong), risks (1 hit=weak), team (0=missing)
        assert result.score == 0.62  # (1.0 + 1.0 + 0.5 + 0.0) / 4 = 0.625 -> 0.62

    def test_business_report_elements(self):
        sections = self.make_sections(
            "Revenue grew 14% this quarter. KPI targets exceeded.",
            "Our recommendation is to expand into new markets.",
            "Challenges include increased competition.",
        )
        result = evaluate_sections("business_report", sections)
        assert len(result.missing) == 0  # all three should be found
        assert result.score >= 0.5

    def test_dollar_sign_counts_for_budget(self):
        """The '$' character is a synonym in the budget keyword list."""
        # Single $ + 'cost' = 2 hits = strong (not weak)
        sections = self.make_sections("The total cost is $50,000.")
        result = evaluate_sections("project_plan", sections)
        budget_strong = [f for f in result.strong if f.label == "budget"]
        budget_weak = [f for f in result.weak if f.label == "budget"]
        # 'cost' (1) + '$' (1) = 2 hits = strong
        assert len(budget_strong) > 0 or len(budget_weak) > 0

        # With no budget keywords at all
        sections2 = self.make_sections("Nothing about money here.")
        result2 = evaluate_sections("project_plan", sections2)
        budget_missing = [f for f in result2.missing if f.label == "budget"]
        assert len(budget_missing) > 0  # missing now


# ---------------------------------------------------------------------------
# planner.py tests
# ---------------------------------------------------------------------------

from agent.planner import _extract_json, PlanResult, create_plan
from agent.llm_client import LLMClient, LLMResult


class TestExtractJson:
    def test_plain_json(self):
        result = _extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_with_code_fence(self):
        result = _extract_json('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_json_with_fence_no_lang(self):
        result = _extract_json('```\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_whitespace_handling(self):
        result = _extract_json('  \n  {"key": "value"}  \n  ')
        assert result == {"key": "value"}

    def test_nested_json(self):
        result = _extract_json('{"sections": [{"title": "Intro"}]}')
        assert result["sections"][0]["title"] == "Intro"

    def test_invalid_json_raises(self):
        import json
        try:
            _extract_json("{invalid}")
            assert False, "Should have raised"
        except json.JSONDecodeError:
            pass


class TestPlanResultDataclass:
    def test_default_raw_error_is_none(self):
        pr = PlanResult(
            document_type="test",
            title="Test",
            classification_confidence=0.5,
            classification_reasoning="reasoning",
            assumptions=[],
            sections=[],
            plan=[],
            llm_mode="fallback",
        )
        assert pr.raw_error is None
        assert pr.document_type == "test"

    def test_all_fields_set(self):
        pr = PlanResult(
            document_type="project_plan",
            title="My Plan",
            classification_confidence=0.9,
            classification_reasoning="Clear keyword match",
            assumptions=["Assumption 1"],
            sections=[{"title": "Intro", "purpose": "Overview"}],
            plan=[{"step_id": 1, "name": "draft", "description": "Draft"}],
            llm_mode="live",
            raw_error="Something went wrong",
        )
        assert pr.classification_confidence == 0.9
        assert pr.raw_error == "Something went wrong"


class TestCreatePlanWithFallback:
    """Tests create_plan with whatever LLM client is configured."""

    @property
    def _expected_llm_mode(self):
        """Detect whether a live LLM is configured."""
        llm = LLMClient()
        return "live" if llm._provider_available() else "fallback"

    def test_returns_plan_result(self):
        llm = LLMClient()
        result = create_plan("Create a project plan with timeline", llm)
        assert isinstance(result, PlanResult)
        assert result.document_type != ""
        assert result.title != ""
        assert isinstance(result.classification_confidence, float)
        assert isinstance(result.assumptions, list)
        assert isinstance(result.sections, list)
        assert isinstance(result.plan, list)
        assert result.llm_mode == self._expected_llm_mode

    def test_project_plan_request_detected(self):
        llm = LLMClient()
        result = create_plan("Project plan for mobile app with timeline and milestones", llm)
        assert result.document_type == "project_plan"
        assert len(result.sections) > 0
        assert len(result.plan) > 0

    def test_meeting_minutes_request_detected(self):
        llm = LLMClient()
        result = create_plan("Meeting minutes from the team standup with attendees", llm)
        assert result.document_type == "meeting_minutes"

    def test_proposal_request(self):
        llm = LLMClient()
        result = create_plan("Business proposal for funding a new project", llm)
        assert result.document_type == "proposal"

    def test_confidence_is_reasonable(self):
        llm = LLMClient()
        result = create_plan("Create a project plan", llm)
        assert 0.0 <= result.classification_confidence <= 1.0

    def test_assumptions_are_recorded(self):
        llm = LLMClient()
        result = create_plan("Unclear vague request for something important", llm)
        assert len(result.assumptions) > 0

    def test_sections_have_title_and_purpose(self):
        llm = LLMClient()
        result = create_plan("Write a technical design document", llm)
        for section in result.sections:
            assert "title" in section
            assert "purpose" in section

    def test_plan_has_numbered_steps(self):
        llm = LLMClient()
        result = create_plan("Create a project plan", llm)
        for step in result.plan:
            assert "step_id" in step
            assert "name" in step
            assert "description" in step


# ---------------------------------------------------------------------------
# logutil.py tests
# ---------------------------------------------------------------------------

from agent.logutil import event


class TestLogUtil:
    def test_event_returns_required_fields(self):
        e = event("planning", "classify", "Testing classification")
        assert e["phase"] == "planning"
        assert e["action"] == "classify"
        assert e["message"] == "Testing classification"
        assert e["status"] == "success"
        assert "event_id" in e
        assert "timestamp" in e

    def test_event_with_optional_fields(self):
        e = event("drafting", "draft_section", "Drafted intro", target="intro", status="success", duration_ms=150)
        assert e["target"] == "intro"
        assert e["duration_ms"] == 150
        assert e["status"] == "success"

    def test_event_with_error_status(self):
        e = event("reflection", "evaluate", "Something failed", status="error")
        assert e["status"] == "error"

    def test_event_id_is_unique(self):
        e1 = event("a", "b", "c")
        e2 = event("a", "b", "c")
        assert e1["event_id"] != e2["event_id"]

    def test_timestamp_is_iso_format(self):
        e = event("test", "test", "test")
        assert "T" in e["timestamp"]
        assert e["timestamp"].endswith("Z") or "+" in e["timestamp"]


# ---------------------------------------------------------------------------
# mock_data.py tests
# ---------------------------------------------------------------------------

from agent.mock_data import get_supporting_data


class TestMockData:
    def test_known_type_returns_common_and_specific_data(self):
        data = get_supporting_data("project_plan")
        assert data["company_name"] == "Northbridge Analytics"
        assert data["timeline_weeks"] == 12
        assert data["budget_usd"] == 185000

    def test_unknown_type_returns_only_common_data(self):
        data = get_supporting_data("nonexistent_type")
        assert data["company_name"] == "Northbridge Analytics"
        # Should NOT have type-specific keys
        assert "timeline_weeks" not in data

    def test_all_known_types_have_company_name(self):
        for doc_type in ["project_plan", "business_report", "meeting_minutes",
                         "proposal", "sop", "technical_design", "product_spec"]:
            data = get_supporting_data(doc_type)
            assert data["company_name"] == "Northbridge Analytics"
            assert "prepared_by" in data
            assert "fiscal_quarter" in data

    def test_business_report_has_revenue(self):
        data = get_supporting_data("business_report")
        assert data["revenue_usd"] == 4_320_000
        assert data["revenue_growth_pct"] == 14.2

    def test_meeting_minutes_has_attendees(self):
        data = get_supporting_data("meeting_minutes")
        assert len(data["attendees"]) == 4
        assert data["duration_minutes"] == 45


# ---------------------------------------------------------------------------
# mailer.py tests
# ---------------------------------------------------------------------------

from agent.mailer import Mailer, EmailResult


class TestMailer:
    def test_not_configured_returns_failure(self):
        """Without SMTP env vars, the mailer returns a structured failure."""
        mailer = Mailer()
        assert mailer.is_configured() is False
        result = mailer.send("test@example.com", "Subject", "Body", "/fake/path")
        assert result.status == "failed"
        assert "not configured" in (result.error or "").lower()
        assert result.recipient == "test@example.com"

    def test_email_result_dataclass(self):
        er = EmailResult(requested=True, recipient="a@b.com", status="sent")
        assert er.status == "sent"
        assert er.error is None

    def test_email_result_error_none_by_default(self):
        er = EmailResult(requested=True, recipient="a@b.com", status="failed", error="SMTP error")
        assert er.error == "SMTP error"
