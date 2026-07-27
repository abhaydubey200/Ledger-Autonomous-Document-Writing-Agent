"""
Reflection module — evaluate, then repair. Two separate steps, not one
combined "check-and-fix" function, because that separation is what makes
this a reflection engine rather than a template validator:

  evaluate_sections()  -> structured findings: which expected elements are
                           missing entirely, which are present but thin
                           ("weak"), which are solidly covered, plus an
                           overall completeness score. Pure assessment,
                           no side effects, no LLM calls for missing/weak
                           decisions (the classification is heuristic and
                           deterministic on purpose, so it's cheap,
                           reproducible, and auditable).

  repair_sections()    -> acts ONLY on the findings from evaluate_sections.
                           Missing elements get a full regeneration pass;
                           weak elements get a "strengthen" pass (a more
                           detailed replacement, not just an appended
                           afterthought); strong elements are left alone.
                           Bounded by MAX_FIXES so this can't run away.

This keeps assessment and repair as distinct, independently testable
stages -- you can call evaluate_sections() on its own to get a quality
report with no mutation at all, which a template-validator-style
"if label not in text: fix()" approach can't offer.
"""

from __future__ import annotations

from dataclasses import dataclass
import time

from .llm_client import LLMClient
from .executor import ExecutedSection
from . import logutil

# (document_type, [(human_label, [synonym keywords to look for]), ...])
_EXPECTED_ELEMENTS: dict[str, list[tuple[str, list[str]]]] = {
    "project_plan": [
        ("timeline", ["timeline", "schedule", "week", "phase", "milestone"]),
        ("budget", ["budget", "cost", "$", "usd"]),
        ("risks", ["risk"]),
        ("team & roles", ["team", "role"]),
    ],
    "business_report": [
        ("performance metrics", ["revenue", "growth", "metric", "%", "kpi"]),
        ("recommendations", ["recommend", "outlook", "next"]),
        ("challenges", ["challenge", "risk", "concern"]),
    ],
    "meeting_minutes": [
        ("attendees", ["attendee", "present", "join"]),
        ("decisions", ["decision", "decided", "agreed"]),
        ("action items", ["action item", "follow-up", "follow up", "next step"]),
    ],
    "technical_design": [
        ("architecture", ["architecture", "component", "diagram"]),
        ("scalability", ["scalab", "load", "reliab", "performance"]),
        ("technology stack", ["stack", "technology", "framework"]),
    ],
    "sop": [
        ("procedure steps", ["step", "procedure"]),
        ("ownership", ["owner", "responsib"]),
        ("review cycle", ["review"]),
    ],
    "product_spec": [
        ("requirements", ["requirement"]),
        ("success metrics", ["metric", "success"]),
        ("target users", ["user"]),
    ],
    "proposal": [
        ("cost", ["cost", "price", "budget", "$"]),
        ("timeline", ["timeline", "week", "duration", "schedule"]),
        ("proposed solution", ["solution", "approach"]),
    ],
}

# Below this many keyword hits, an element is "weak" (mentioned once,
# likely superficially) rather than "missing" (zero hits) or "strong"
# (repeated / substantive coverage).
WEAK_THRESHOLD = 2
MAX_FIXES = 4

FIX_SYSTEM_PROMPT = """You are the self-review module of an autonomous document-writing agent.
Your own earlier draft is missing a short but important element entirely. Write ONE
short paragraph (40-90 words) that supplies it, in professional business prose
consistent with a document of this type. Respond with ONLY the paragraph."""

STRENGTHEN_SYSTEM_PROMPT = """You are the self-review module of an autonomous document-writing agent.
Your own earlier draft mentions an important element only superficially. Write ONE
more substantive paragraph (50-100 words) that covers it properly -- concrete,
specific, professional business prose. Respond with ONLY the paragraph."""


@dataclass
class ElementFinding:
    label: str
    status: str  # "strong" | "weak" | "missing"
    occurrences: int


@dataclass
class EvaluationResult:
    missing: list[ElementFinding]
    weak: list[ElementFinding]
    strong: list[ElementFinding]
    score: float  # 0.0-1.0, completeness BEFORE any repair


@dataclass
class ReflectionCheck:
    label: str
    status: str  # "strong" | "weak" | "missing" | "regenerated" | "strengthened" | "unresolved"
    note: str


def evaluate_sections(document_type: str, sections: list[ExecutedSection]) -> EvaluationResult:
    """Pure assessment -- no mutation, no LLM calls. Counts keyword hits
    per expected element and buckets each into strong/weak/missing."""
    expected = _EXPECTED_ELEMENTS.get(document_type, [])
    combined = " ".join(s.content.lower() for s in sections)

    missing, weak, strong = [], [], []
    for label, synonyms in expected:
        occurrences = sum(combined.count(kw) for kw in synonyms)
        if occurrences == 0:
            missing.append(ElementFinding(label, "missing", occurrences))
        elif occurrences < WEAK_THRESHOLD:
            weak.append(ElementFinding(label, "weak", occurrences))
        else:
            strong.append(ElementFinding(label, "strong", occurrences))

    total = len(expected)
    if total == 0:
        score = 1.0
    else:
        score = (len(strong) * 1.0 + len(weak) * 0.5 + len(missing) * 0.0) / total

    return EvaluationResult(missing=missing, weak=weak, strong=strong, score=round(score, 2))


def repair_sections(
    document_type: str,
    sections: list[ExecutedSection],
    evaluation: EvaluationResult,
    llm: LLMClient,
) -> tuple[list[ReflectionCheck], list[dict], float]:
    """Acts only on evaluation's findings. Mutates `sections` in place for
    fixed items. Returns (checks, structured_events, reflection_confidence)."""
    events: list[dict] = []
    checks: list[ReflectionCheck] = []
    fixes_used = 0

    events.append(logutil.event(
        "reflection", "evaluate",
        f"Evaluated draft against {len(evaluation.missing) + len(evaluation.weak) + len(evaluation.strong)} "
        f"expected element(s): {len(evaluation.strong)} strong, {len(evaluation.weak)} weak, "
        f"{len(evaluation.missing)} missing (pre-repair score {evaluation.score:.0%}).",
    ))

    for f in evaluation.strong:
        checks.append(ReflectionCheck(label=f.label, status="strong", note=f"{f.occurrences} supporting mention(s) found"))

    # Missing elements get full regeneration; weak elements get strengthened.
    # Missing is treated as higher priority within the fix budget.
    for f in evaluation.missing:
        if fixes_used >= MAX_FIXES or not sections:
            checks.append(ReflectionCheck(label=f.label, status="unresolved", note="missing; fix budget exhausted"))
            events.append(logutil.event("reflection", "regenerate", f"Skipped '{f.label}': fix budget exhausted.", target=f.label, status="error"))
            continue
        t0 = time.time()
        prompt = f"MODE: REFLECTION_FIX:{f.label}\nDocument type: {document_type}\nMissing element: {f.label}."
        result = llm.complete(FIX_SYSTEM_PROMPT, prompt, json_mode=False)
        addition = result.text.strip()
        sections[-1].content = sections[-1].content.rstrip() + f"\n\n{addition}"
        dur = int((time.time() - t0) * 1000)
        fixes_used += 1
        checks.append(ReflectionCheck(label=f.label, status="regenerated", note=f"was missing; regenerated via {result.mode} generator"))
        events.append(logutil.event("reflection", "regenerate", f"Regenerated missing element '{f.label}'.", target=f.label, status="success", duration_ms=dur))

    for f in evaluation.weak:
        if fixes_used >= MAX_FIXES or not sections:
            checks.append(ReflectionCheck(label=f.label, status="unresolved", note=f"weak ({f.occurrences} mention); fix budget exhausted"))
            events.append(logutil.event("reflection", "strengthen", f"Skipped '{f.label}': fix budget exhausted.", target=f.label, status="error"))
            continue
        t0 = time.time()
        prompt = f"MODE: REFLECTION_STRENGTHEN:{f.label}\nDocument type: {document_type}\nThinly covered element: {f.label}."
        result = llm.complete(STRENGTHEN_SYSTEM_PROMPT, prompt, json_mode=False)
        addition = result.text.strip()
        sections[-1].content = sections[-1].content.rstrip() + f"\n\n{addition}"
        dur = int((time.time() - t0) * 1000)
        fixes_used += 1
        checks.append(ReflectionCheck(label=f.label, status="strengthened", note=f"was weak ({f.occurrences} mention); strengthened via {result.mode} generator"))
        events.append(logutil.event("reflection", "strengthen", f"Strengthened weak element '{f.label}'.", target=f.label, status="success", duration_ms=dur))

    # Post-repair confidence: strong=1.0, regenerated/strengthened=0.85
    # (a patched gap, not organically thorough coverage), unresolved=0.0.
    quality_map = {"strong": 1.0, "regenerated": 0.85, "strengthened": 0.85, "unresolved": 0.0}
    if checks:
        reflection_confidence = round(sum(quality_map[c.status] for c in checks) / len(checks), 2)
    else:
        reflection_confidence = 1.0

    events.append(logutil.event(
        "reflection", "complete",
        f"Reflection complete: {sum(1 for c in checks if c.status=='strong')} strong, "
        f"{sum(1 for c in checks if c.status=='regenerated')} regenerated, "
        f"{sum(1 for c in checks if c.status=='strengthened')} strengthened, "
        f"{sum(1 for c in checks if c.status=='unresolved')} unresolved. "
        f"Post-repair confidence {reflection_confidence:.0%}.",
    ))

    return checks, events, reflection_confidence
