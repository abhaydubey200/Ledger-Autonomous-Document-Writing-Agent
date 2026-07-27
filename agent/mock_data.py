"""
Small mock-data bank the agent can draw on when drafting sections,
as explicitly permitted by the assignment ("Use of mock data is allowed
where appropriate."). Keyed loosely by document type so the drafting
prompts get plausible, on-topic numbers instead of generic filler.
"""

from __future__ import annotations

_COMMON = {
    "company_name": "Northbridge Analytics",
    "prepared_by": "Autonomous Agent (AI Engineer Assignment Build)",
    "fiscal_quarter": "Q3 2026",
}

_BY_TYPE = {
    "project_plan": {
        "timeline_weeks": 12,
        "team_size": 6,
        "budget_usd": 185000,
        "milestones": ["Kickoff", "Design freeze", "Beta release", "UAT", "GA launch"],
    },
    "business_report": {
        "revenue_usd": 4_320_000,
        "revenue_growth_pct": 14.2,
        "churn_pct": 3.1,
        "headcount": 142,
    },
    "meeting_minutes": {
        "attendees": ["A. Sharma (Product)", "R. Verma (Engineering)", "M. Iyer (Finance)", "S. Kapoor (Client)"],
        "duration_minutes": 45,
    },
    "proposal": {
        "estimated_cost_usd": 92000,
        "estimated_duration_weeks": 8,
        "roi_estimate_pct": 22,
    },
    "sop": {
        "review_cycle_months": 6,
        "owner_role": "Operations Lead",
    },
    "technical_design": {
        "stack": ["FastAPI", "PostgreSQL", "Redis", "React"],
        "expected_load_rps": 250,
    },
    "product_spec": {
        "target_release": "v1.0",
        "target_users": "SMB finance teams",
    },
}


def get_supporting_data(document_type: str) -> dict:
    data = dict(_COMMON)
    data.update(_BY_TYPE.get(document_type, {}))
    return data
