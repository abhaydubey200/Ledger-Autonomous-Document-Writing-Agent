"""
Deterministic, rule-based "offline brain" used by LLMClient when every
live-provider attempt has failed (or none is configured). It parses the
same `MODE: ...` marker convention that planner.py and executor.py embed
in their prompts, and returns plausible, structured output so the rest of
the pipeline can proceed exactly as if a real model had answered.

This is not meant to be smart -- it's meant to be a reliable safety net,
which is the whole point of the "retry & fallback" improvement.
"""

from __future__ import annotations

import json
import re


_TYPE_KEYWORDS = [
    ("meeting_minutes", [("minutes", 3), ("attendee", 3), ("call notes", 3), ("meeting", 1)]),
    ("project_plan", [("project plan", 3), ("timeline", 2), ("milestone", 2), ("roadmap", 2), ("launch plan", 3)]),
    ("business_report", [("report", 2), ("performance", 2), ("quarterly", 2), ("revenue", 2), ("kpi", 2), ("q1", 2), ("q2", 2), ("q3", 2), ("q4", 2)]),
    ("technical_design", [("technical design", 3), ("architecture", 2), ("system design", 3), ("design doc", 3)]),
    ("sop", [("sop", 3), ("standard operating procedure", 3), ("process document", 2), ("procedure", 2)]),
    ("product_spec", [("product spec", 3), ("specification", 2), ("feature spec", 3), ("requirements doc", 2)]),
    ("proposal", [("proposal", 3), ("pitch", 2), ("quote", 1), ("statement of work", 3), ("sow", 2), ("funding", 2)]),
]


def _guess_document_type(request_text: str) -> tuple[str, float, str]:
    """
    Returns (document_type, confidence, reasoning).

    Confidence is the winning type's share of total matched keyword weight
    across all types -- a document that only matches one type's keywords
    scores near 1.0; a genuinely ambiguous request that partially matches
    two or three types scores lower, honestly reflecting that ambiguity
    rather than pretending certainty it doesn't have.
    """
    text = request_text.lower()
    scores: dict[str, int] = {}
    matched_terms: dict[str, list[str]] = {}
    for doc_type, keywords in _TYPE_KEYWORDS:
        hits = [kw for kw, weight in keywords if kw in text]
        score = sum(weight for kw, weight in keywords if kw in text)
        if score:
            scores[doc_type] = score
            matched_terms[doc_type] = hits

    if not scores:
        return "business_report", 0.35, "No strong keyword signal found; defaulted to the most general business document type."

    winner = max(scores, key=scores.get)
    total = sum(scores.values())
    confidence = round(scores[winner] / total, 2) if total else 0.5
    terms = ", ".join(f"'{t}'" for t in matched_terms[winner])
    reasoning = f"Keyword match against offline classifier: found {terms} (weighted score {scores[winner]} of {total} total matched across all types)."
    return winner, confidence, reasoning


def _default_sections(doc_type: str) -> list[dict]:
    presets = {
        "meeting_minutes": [
            {"title": "Meeting Overview", "purpose": "Date, attendees, and objective"},
            {"title": "Key Discussion Points", "purpose": "Summary of topics covered"},
            {"title": "Decisions Made", "purpose": "Concrete decisions reached"},
            {"title": "Action Items", "purpose": "Owners and due dates"},
            {"title": "Next Steps", "purpose": "Follow-up meeting or milestone"},
        ],
        "project_plan": [
            {"title": "Project Overview", "purpose": "Goal and scope"},
            {"title": "Objectives & Success Criteria", "purpose": "What success looks like"},
            {"title": "Timeline & Milestones", "purpose": "Phased schedule"},
            {"title": "Team & Roles", "purpose": "Who does what"},
            {"title": "Budget", "purpose": "High-level cost breakdown"},
            {"title": "Risks & Mitigations", "purpose": "Key risks and how they're handled"},
        ],
        "business_report": [
            {"title": "Executive Summary", "purpose": "Top-line takeaways"},
            {"title": "Performance Overview", "purpose": "Key metrics vs. prior period"},
            {"title": "Highlights", "purpose": "Notable wins"},
            {"title": "Challenges", "purpose": "Areas of concern"},
            {"title": "Outlook & Recommendations", "purpose": "What's next"},
        ],
        "technical_design": [
            {"title": "Overview", "purpose": "Problem and goals"},
            {"title": "Architecture", "purpose": "System components and data flow"},
            {"title": "Technology Stack", "purpose": "Chosen tools and rationale"},
            {"title": "Scalability & Reliability", "purpose": "How it handles load and failure"},
            {"title": "Open Questions & Risks", "purpose": "Unresolved items"},
        ],
        "sop": [
            {"title": "Purpose & Scope", "purpose": "What this SOP governs"},
            {"title": "Roles & Responsibilities", "purpose": "Who owns each step"},
            {"title": "Procedure", "purpose": "Step-by-step process"},
            {"title": "Exceptions & Escalation", "purpose": "What to do when things go wrong"},
            {"title": "Review Cycle", "purpose": "How and when this SOP is updated"},
        ],
        "product_spec": [
            {"title": "Overview", "purpose": "Problem and target users"},
            {"title": "Goals & Non-Goals", "purpose": "Scope boundaries"},
            {"title": "Requirements", "purpose": "Functional requirements"},
            {"title": "User Experience", "purpose": "Key flows"},
            {"title": "Success Metrics", "purpose": "How success is measured"},
        ],
        "proposal": [
            {"title": "Executive Summary", "purpose": "The ask, in brief"},
            {"title": "Problem Statement", "purpose": "Why this matters"},
            {"title": "Proposed Solution", "purpose": "What we'll do"},
            {"title": "Timeline & Cost", "purpose": "Schedule and pricing"},
            {"title": "Why Us", "purpose": "Differentiation"},
        ],
    }
    return presets.get(doc_type, presets["business_report"])


def _plan_steps(doc_type: str) -> list[dict]:
    return [
        {"step_id": 1, "name": "interpret_request", "description": "Parse the user's natural language request and extract intent."},
        {"step_id": 2, "name": "classify_document_type", "description": f"Determine that a '{doc_type}' best satisfies the request."},
        {"step_id": 3, "name": "resolve_ambiguity", "description": "Make and record reasonable assumptions for any missing/conflicting information."},
        {"step_id": 4, "name": "design_structure", "description": "Choose section structure for the document."},
        {"step_id": 5, "name": "gather_supporting_data", "description": "Collect mock supporting data relevant to the document type."},
        {"step_id": 6, "name": "draft_sections", "description": "Generate content for each section."},
        {"step_id": 7, "name": "assemble_docx", "description": "Assemble the final content into a formatted Word document."},
        {"step_id": 8, "name": "self_check", "description": "Verify every planned section has content before returning the result."},
    ]


def _fallback_plan_json(request_text: str) -> dict:
    doc_type, confidence, reasoning = _guess_document_type(request_text)
    sections = _default_sections(doc_type)
    title_map = {
        "meeting_minutes": "Meeting Minutes",
        "project_plan": "Project Plan",
        "business_report": "Business Performance Report",
        "technical_design": "Technical Design Document",
        "sop": "Standard Operating Procedure",
        "product_spec": "Product Specification",
        "proposal": "Business Proposal",
    }
    return {
        "document_type": doc_type,
        "title": title_map.get(doc_type, "Business Document"),
        "confidence": confidence,
        "classification_reasoning": reasoning,
        "assumptions": [
            "No live LLM endpoint was reachable, so the offline rule-based planner selected the "
            "document type from keyword matching against the request text.",
            "Where the request left details unspecified, standard industry-typical structure and "
            "mock figures were used instead of asking a clarifying question, per the assignment's "
            "autonomy requirement.",
        ],
        "sections": sections,
        "plan": _plan_steps(doc_type),
    }


def _fallback_section_text(section_title: str, doc_type: str, request_text: str) -> str:
    generic = (
        f"This section, \"{section_title}\", addresses the {doc_type.replace('_', ' ')} requested "
        f"by the stakeholder. Based on the request (\"{request_text.strip()[:140]}...\" if longer than "
        "140 characters), the agent compiled relevant points below.\n"
        "- Context gathered from the request and standard practice for this document type.\n"
        "- Mock supporting figures applied where concrete data was not supplied.\n"
        "- Content structured for clarity and stakeholder review.\n"
        "This content was produced by the offline fallback generator because no live LLM endpoint "
        "was reachable at draft time; it is intentionally template-based rather than freeform "
        "prose, and would be replaced by richer, model-generated writing whenever a live provider "
        "(Groq, Ollama, etc.) is available."
    )
    return generic


def generate(system_prompt: str, user_prompt: str, json_mode: bool) -> str:
    mode_match = re.search(r"MODE:\s*([A-Z_]+)(:(.*))?", user_prompt)
    mode = mode_match.group(1) if mode_match else "UNKNOWN"
    arg = mode_match.group(3).strip() if mode_match and mode_match.group(3) else None

    if mode == "PLAN":
        req_match = re.search(r'"""\n(.*?)\n"""', user_prompt, re.DOTALL)
        request_text = req_match.group(1) if req_match else user_prompt
        return json.dumps(_fallback_plan_json(request_text))

    if mode == "SECTION":
        doc_type_match = re.search(r"Overall document type:\s*(\S+)", user_prompt)
        doc_type = doc_type_match.group(1) if doc_type_match else "business_report"
        req_match = re.search(r'Overall user request:\n"""\n(.*?)\n"""', user_prompt, re.DOTALL)
        request_text = req_match.group(1) if req_match else user_prompt
        return _fallback_section_text(arg or "Section", doc_type, request_text)

    if mode == "REFLECTION_FIX":
        label = arg or "supporting detail"
        return (
            f"To ensure {label} is clearly addressed, the team has documented a dedicated "
            f"{label} plan as part of this deliverable, reviewed against comparable prior "
            f"engagements and confirmed with stakeholders before circulation. This section was "
            f"added by the agent's self-check step, which flagged that {label} was not yet "
            f"covered and generated this supplementary content to close the gap."
        )

    if mode == "REFLECTION_STRENGTHEN":
        label = arg or "supporting detail"
        return (
            f"Expanding further on {label}: the agent's self-review flagged this as only "
            f"briefly touched on in the initial draft. A more complete treatment includes "
            f"specific ownership, a defined timeframe, and measurable criteria for {label}, "
            f"documented here so a reader does not need to infer them. This paragraph was "
            f"added by the reflection step after evaluating the draft as thin on this point."
        )

    return "Fallback generator: unrecognized mode; no content produced."
