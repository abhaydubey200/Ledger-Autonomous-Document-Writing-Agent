"""
Email intent detection.

Deliberately its own module, separate from planner.py's document-type
classification. This is a distinct "tool selection" decision -- does the
request ask for an additional action (email delivery) beyond producing
the document? -- and keeping it separate makes both the code and the
demo clearer: one function answers "what document," a different function
answers "does anything else need to happen after."

Detection is intentionally conservative and explicit-intent-only. It
requires BOTH an email address AND a delivery verb in the request text;
either alone is not enough. This is a deliberate design choice per the
"don't make it fully automatic" requirement -- a request that merely
mentions an email address (e.g. "our contact is jane@acme.com") should
NOT trigger sending, only a request that clearly asks for delivery
("...and email it to jane@acme.com" / "send it to jane@acme.com").
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# A delivery verb must appear in the request for email intent to count --
# an address alone is not a request to send anything.
_DELIVERY_VERBS = [
    r"\bemail\b", r"\be-mail\b", r"\bmail\b", r"\bsend\b",
    r"\bshare\b", r"\bdeliver\b", r"\bforward\b",
]
_DELIVERY_PATTERN = re.compile("|".join(_DELIVERY_VERBS), re.IGNORECASE)


@dataclass
class EmailIntent:
    requested: bool
    recipient: str | None
    reasoning: str


def detect_email_intent(request_text: str) -> EmailIntent:
    email_match = _EMAIL_PATTERN.search(request_text)
    has_delivery_verb = bool(_DELIVERY_PATTERN.search(request_text))

    if email_match and has_delivery_verb:
        return EmailIntent(
            requested=True,
            recipient=email_match.group(0),
            reasoning=(
                f"Found an email address ({email_match.group(0)}) alongside a delivery verb "
                f"in the request, so email delivery was treated as an explicit part of the task."
            ),
        )

    if email_match and not has_delivery_verb:
        return EmailIntent(
            requested=False,
            recipient=None,
            reasoning=(
                "An email address was present in the request but no delivery verb "
                "(e.g. 'email', 'send') accompanied it, so it was treated as incidental "
                "text, not a delivery instruction."
            ),
        )

    return EmailIntent(requested=False, recipient=None, reasoning="No email delivery intent detected.")
