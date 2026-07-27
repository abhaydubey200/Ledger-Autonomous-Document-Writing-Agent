"""
Planner module.

Given a raw natural-language request, ask the LLM (or the offline fallback)
to:
  1. Decide what kind of business document best satisfies the request
     (proposal / meeting minutes / project plan / report / SOP / spec...),
     with a calibrated confidence score and stated reasoning.
  2. State any assumptions it had to make to resolve ambiguity or fill
     missing information.
  3. Propose the section structure of the document.
  4. Emit a step-by-step execution plan (the agent's own TODO list) that
     the executor will carry out and report progress against.

Precise framing: the planner derives an execution plan from the user's
intent and the detected document type. The sequence is generated
dynamically per request (no hardcoded per-type template), but execution
is constrained to a known set of supported actions (classify, draft
section, evaluate, repair, assemble) to keep the pipeline reliable. This
is autonomy within a bounded action space, not open-ended reasoning.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .llm_client import LLMClient, LLMResult

PLANNER_SYSTEM_PROMPT = """You are the planning module of an autonomous business-document-writing agent.
Given a user's natural language request, you must:
1. Decide the single best document type to produce. Choose from:
   proposal, meeting_minutes, project_plan, business_report, technical_design,
   sop, product_spec, general_business_document.
2. Give a confidence score from 0.0 to 1.0 for that classification, and a one-sentence
   reasoning that names the specific words/phrases in the request that drove the decision.
   If the request is genuinely ambiguous between two types, say so and give a lower
   confidence (e.g. 0.5-0.7) rather than overstating certainty.
3. If the request is ambiguous, incomplete, or has conflicting requirements,
   make the most reasonable professional assumption and record it explicitly
   -- do not ask a clarifying question, since this agent must run end-to-end
   without human intervention.
4. Propose 4 to 7 section titles that this document should contain, each with
   a one-line purpose explaining why that section belongs in this document type.
5. Propose a numbered execution plan (your own TODO list) of 5 to 8 steps
   describing how you will produce the final document.

Respond with ONLY a JSON object, no prose, no markdown fences, matching exactly:
{
  "document_type": "...",
  "title": "...",
  "confidence": 0.0,
  "classification_reasoning": "...",
  "assumptions": ["...", "..."],
  "sections": [{"title": "...", "purpose": "..."}, ...],
  "plan": [{"step_id": 1, "name": "short_name", "description": "..."}, ...]
}
"""


@dataclass
class PlanResult:
    document_type: str
    title: str
    classification_confidence: float
    classification_reasoning: str
    assumptions: list[str]
    sections: list[dict]
    plan: list[dict]
    llm_mode: str
    raw_error: str | None = None


def _extract_json(text: str) -> dict:
    """LLMs (and our fallback) should return pure JSON, but strip code
    fences defensively in case a model wraps it anyway."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    return json.loads(cleaned)


def create_plan(user_request: str, llm: LLMClient) -> PlanResult:
    user_prompt = f"MODE: PLAN\nUser request:\n\"\"\"\n{user_request}\n\"\"\""
    result: LLMResult = llm.complete(PLANNER_SYSTEM_PROMPT, user_prompt, json_mode=True)

    try:
        data = _extract_json(result.text)
    except Exception:
        # Even the JSON parse itself gets a safety net: if the model
        # returned malformed JSON, degrade to the deterministic fallback
        # rather than raising 500 to the caller.
        from . import fallback_content

        data = json.loads(fallback_content.generate(PLANNER_SYSTEM_PROMPT, user_prompt, True))
        result.mode = "fallback"

    return PlanResult(
        document_type=data.get("document_type", "general_business_document"),
        title=data.get("title", "Generated Document"),
        classification_confidence=float(data.get("confidence", 0.6)),
        classification_reasoning=data.get("classification_reasoning", "No reasoning provided."),
        assumptions=data.get("assumptions", []),
        sections=data.get("sections", []),
        plan=data.get("plan", []),
        llm_mode=result.mode,
        raw_error=result.error,
    )
