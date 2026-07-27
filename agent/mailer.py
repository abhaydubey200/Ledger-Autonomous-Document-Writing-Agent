"""
Mailer module -- sends the generated document as an email attachment.

Uses only Python's standard library (smtplib + email.message.EmailMessage)
per the "no third-party dependency" preference: no API key to manage for
a third-party email service, and it demonstrates standard-library email
handling directly.

Configuration is via environment variables (see .env.example):
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_USE_TLS

Follows the same graceful-degradation philosophy as agent/llm_client.py:
if SMTP isn't configured, or the send fails for any reason (auth, network,
invalid recipient), this returns a structured failure -- it never raises,
and it never blocks the document itself from being generated and returned.
Email is an optional side effect, not a dependency of the core pipeline.
"""

from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage


@dataclass
class EmailResult:
    requested: bool
    recipient: str | None
    status: str  # "not_requested" | "sent" | "failed"
    error: str | None = None


class Mailer:
    def __init__(self):
        self.host = os.getenv("SMTP_HOST")
        self.port = int(os.getenv("SMTP_PORT", "587"))
        self.user = os.getenv("SMTP_USER")
        self.password = os.getenv("SMTP_PASSWORD")
        self.sender = os.getenv("SMTP_FROM", self.user or "agent@example.com")
        self.use_tls = os.getenv("SMTP_USE_TLS", "true").lower() != "false"

    def is_configured(self) -> bool:
        return bool(self.host and self.user and self.password)

    def send(
        self,
        recipient: str,
        subject: str,
        body: str,
        attachment_path: str,
    ) -> EmailResult:
        if not self.is_configured():
            return EmailResult(
                requested=True,
                recipient=recipient,
                status="failed",
                error=(
                    "SMTP is not configured (set SMTP_HOST, SMTP_USER, SMTP_PASSWORD in .env). "
                    "The document was generated successfully regardless; email delivery is an "
                    "optional side effect, not a dependency of document generation."
                ),
            )

        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = self.sender
            msg["To"] = recipient
            msg.set_content(body)

            with open(attachment_path, "rb") as f:
                file_data = f.read()
            file_name = os.path.basename(attachment_path)
            msg.add_attachment(
                file_data,
                maintype="application",
                subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
                filename=file_name,
            )

            with smtplib.SMTP(self.host, self.port, timeout=15) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.user, self.password)
                server.send_message(msg)

            return EmailResult(requested=True, recipient=recipient, status="sent")

        except Exception as exc:  # noqa: BLE001 - deliberately broad: any failure here
            # must degrade to a structured result, never crash the request.
            return EmailResult(requested=True, recipient=recipient, status="failed", error=str(exc))
