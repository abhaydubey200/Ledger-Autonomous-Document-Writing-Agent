"""
Executor module.

Walks the plan produced by planner.py and actually does the work:
drafts content for each proposed section (one LLM call per section, each
independently protected by the retry+fallback logic in llm_client.py),
mixes in mock supporting data where useful, and logs a structured event
per action (not just a sentence) so the "agent-generated task list"
requirement is visibly satisfied and auditable, not just implied.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .llm_client import LLMClient
from .planner import PlanResult
from . import mock_data
from . import logutil

SECTION_SYSTEM_PROMPT = """You are the drafting module of an autonomous business-document-writing agent.
Write clear, professional, well-structured business prose for ONE section of a
larger document. Use concrete, specific-sounding details (you may invent
plausible mock data such as dates, numbers, names, or metrics where useful --
label nothing as fake, just write it naturally as a real business document would).
Do not repeat the section title in your answer. Do not use markdown headers.
Plain paragraphs and, where natural, short bullet lists (using "- ") are fine.
Keep it to roughly 120-220 words unless the section is a table-like list
(e.g. timeline, roles), in which case short bullet lines are preferred.
Respond with ONLY the section content, no preamble.
"""


@dataclass
class ExecutedSection:
    title: str
    purpose: str
    content: str
    llm_mode: str


@dataclass
class ExecutionResult:
    sections: list[ExecutedSection]
    log: list[dict]
    overall_mode: str  # "live" if every call was live, "fallback" if any call fell back


def execute_plan(user_request: str, plan_result: PlanResult, llm: LLMClient) -> ExecutionResult:
    log: list[dict] = []
    log.append(logutil.event(
        "drafting", "interpret",
        f"Interpreted request and selected document_type='{plan_result.document_type}' "
        f"(classification confidence {plan_result.classification_confidence:.0%}, planner mode={plan_result.llm_mode}).",
        status="success",
    ))

    if plan_result.assumptions:
        for a in plan_result.assumptions:
            log.append(logutil.event("drafting", "record_assumption", a, status="info"))

    supporting_data = mock_data.get_supporting_data(plan_result.document_type)
    log.append(logutil.event(
        "drafting", "gather_data",
        f"Gathered mock supporting data for '{plan_result.document_type}' ({len(supporting_data)} data points).",
        status="success",
    ))

    executed_sections: list[ExecutedSection] = []
    any_fallback = plan_result.llm_mode == "fallback"
    any_live = plan_result.llm_mode == "live"

    for idx, section in enumerate(plan_result.sections, start=1):
        title = section.get("title", f"Section {idx}")
        purpose = section.get("purpose", "")
        user_prompt = (
            f"MODE: SECTION:{title}\n"
            f"Overall document type: {plan_result.document_type}\n"
            f"Overall user request:\n\"\"\"\n{user_request}\n\"\"\"\n"
            f"This section's title: {title}\n"
            f"This section's purpose: {purpose}\n"
            f"Relevant mock supporting data you may draw on: {supporting_data}\n"
        )
        t0 = time.time()
        result = llm.complete(SECTION_SYSTEM_PROMPT, user_prompt, json_mode=False)
        duration_ms = int((time.time() - t0) * 1000)
        any_fallback = any_fallback or (result.mode == "fallback")
        any_live = any_live or (result.mode == "live")

        status_label = "drafted (live LLM)" if result.mode == "live" else "drafted (offline fallback generator)"
        log.append(logutil.event(
            "drafting", "draft_section",
            f"[{idx}/{len(plan_result.sections)}] '{title}' -> {status_label}, attempts={result.attempts}.",
            target=title, status="success", duration_ms=duration_ms,
        ))
        if result.error:
            log.append(logutil.event(
                "drafting", "recover_error",
                f"Recovered from error on '{title}': {result.error[:160]}",
                target=title, status="error",
            ))

        executed_sections.append(
            ExecutedSection(title=title, purpose=purpose, content=result.text.strip(), llm_mode=result.mode)
        )

    overall_mode = "live" if (any_live and not any_fallback) else ("mixed" if (any_live and any_fallback) else "fallback")
    log.append(logutil.event("drafting", "complete", f"All sections drafted. Overall LLM mode: {overall_mode}.", status="success"))

    return ExecutionResult(sections=executed_sections, log=log, overall_mode=overall_mode)
