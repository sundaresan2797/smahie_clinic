"""Optional SMTP notifications to the clinic inbox.

Emails deliberately contain no patient names, phone numbers or messages — only
a reference and a link to the protected admin area.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import Settings

log = logging.getLogger("smahie.email")


def _send(settings: Settings, subject: str, body: str) -> None:
    if not settings.smtp_configured:
        log.info("SMTP not configured; notification skipped (%s)", subject.split(" ")[0])
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = settings.clinic_notification_email
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_username and settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)
        log.info("notification sent (%s)", subject.split(" ")[0])
    except (OSError, smtplib.SMTPException) as exc:
        # Requests are always visible in the admin dashboard, so a failed email
        # is logged (without patient data) rather than surfaced to the patient.
        log.warning("notification failed: %s", exc.__class__.__name__)


def notify_new_appointment(settings: Settings, reference: str, date_text: str, session_label: str) -> None:
    _send(
        settings,
        f"New appointment request {reference}",
        "A new appointment request was submitted on the website.\n\n"
        f"Reference: {reference}\n"
        f"Preferred date: {date_text}\n"
        f"Session: {session_label}\n\n"
        "Sign in to view the details and contact the patient:\n"
        f"{settings.site_url}/admin/appointments\n\n"
        "For privacy, patient details are not included in this email.\n",
    )


def notify_new_contact(settings: Settings, message_id: int) -> None:
    _send(
        settings,
        f"New website message #{message_id}",
        "A new message was sent using the website contact form.\n\n"
        f"Sign in to read it:\n{settings.site_url}/admin/messages\n\n"
        "For privacy, the message is not included in this email.\n",
    )
