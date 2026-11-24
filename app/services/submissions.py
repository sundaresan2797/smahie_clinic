"""Shared handling for the public appointment and contact forms.

Both the no-JavaScript HTML form routes and the JSON API routes call these
functions, so validation, anti-spam and storage behave identically.
"""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.content.clinic import CLINIC
from app.core import rate_limit
from app.core.config import Settings
from app.core.database import utcnow
from app.core.security import FormTokenStatus, check_form_token
from app.core.timeutil import now_ist, today_ist
from app.models import Appointment, ContactMessage
from app.schemas.forms import AppointmentRequest, ContactRequest, friendly_errors

APPOINTMENT_SUCCESS = (
    "Your appointment request has been received. Our clinic team will contact you to confirm the availability."
)
CONTACT_SUCCESS = "Thank you — your message has been sent. The clinic team will reply as soon as possible."

_REFERENCE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


@dataclass
class Outcome:
    ok: bool
    status_code: int = 200
    kind: str = "created"  # created | duplicate | ignored | invalid | rejected | rate_limited
    message: str = ""
    errors: dict[str, str] = field(default_factory=dict)
    record: Any = None

    def as_json(self) -> dict[str, Any]:
        body: dict[str, Any] = {"ok": self.ok, "message": self.message}
        if self.errors:
            body["errors"] = self.errors
        return body


def _rejected(status: int, message: str, kind: str = "rejected") -> Outcome:
    return Outcome(ok=False, status_code=status, kind=kind, message=message, errors={"form": message})


def _precheck(
    db: Session,
    settings: Settings,
    data: Mapping[str, Any],
    fingerprint: str,
    origin_ok: bool,
    scope: str,
    success: str,
) -> Outcome | None:
    """Origin, honeypot, form token and coarse rate limit. Returns an Outcome to stop early."""
    if not origin_ok:
        return _rejected(403, "This request could not be verified. Please refresh the page and try again.")
    if str(data.get("website") or "").strip():
        # Honeypot filled: almost certainly a bot. Pretend success, store nothing.
        return Outcome(ok=True, kind="ignored", message=success)
    status = check_form_token(str(data.get("form_token") or ""), settings)
    if status is FormTokenStatus.TOO_FAST:
        return _rejected(400, "That was very quick. Please check your details and submit the form again.")
    if status is not FormTokenStatus.OK:
        return _rejected(400, "This form has expired. Please refresh the page and try again.")
    if not rate_limit.allow(db, f"{scope}-attempt:{fingerprint}", limit=30, window_seconds=3600):
        return _too_many()
    return None


def _too_many() -> Outcome:
    return _rejected(
        429,
        "Too many requests have been sent from this connection. Please try again later or call "
        f"the clinic on {CLINIC.phone_display}.",
        kind="rate_limited",
    )


# --------------------------------------------------------------------------- appointments
def _new_reference(db: Session) -> str:
    while True:
        ref = "SOC-" + "".join(secrets.choice(_REFERENCE_ALPHABET) for _ in range(6))
        if not db.scalar(select(Appointment.id).where(Appointment.reference == ref)):
            return ref


def _date_errors(req: AppointmentRequest, settings: Settings) -> dict[str, str]:
    today = today_ist()
    max_days = settings.appointment_max_days_ahead
    if req.preferred_date < today:
        return {"preferred_date": "Please choose today or a future date."}
    if req.preferred_date > today + timedelta(days=max_days):
        return {"preferred_date": f"Please choose a date within the next {max_days} days."}
    if req.preferred_date == today:
        now = now_ist().time()
        session = CLINIC.session(req.preferred_session)
        if session and now >= session.end:
            return {
                "preferred_session": f"Today's {session.label.lower()} session has ended. "
                "Please choose another session or date."
            }
        if req.preferred_time and now.strftime("%H:%M") >= req.preferred_time:
            return {"preferred_time": "This time has already passed today. Please choose a later time."}
    return {}


def submit_appointment(
    db: Session, settings: Settings, data: Mapping[str, Any], *, fingerprint: str, origin_ok: bool
) -> Outcome:
    stop = _precheck(db, settings, data, fingerprint, origin_ok, "appt", APPOINTMENT_SUCCESS)
    if stop:
        return stop

    try:
        req = AppointmentRequest.model_validate(dict(data))
    except ValidationError as exc:
        return Outcome(
            ok=False,
            status_code=422,
            kind="invalid",
            message="Please correct the highlighted fields.",
            errors=friendly_errors(exc),
        )
    errors = _date_errors(req, settings)
    if errors:
        return Outcome(
            ok=False, status_code=422, kind="invalid", message="Please correct the highlighted fields.", errors=errors
        )

    duplicate = db.scalar(
        select(Appointment).where(
            Appointment.phone == req.phone,
            Appointment.preferred_date == req.preferred_date,
            Appointment.preferred_session == req.preferred_session,
            Appointment.status.in_(("pending", "confirmed")),
        )
    )
    if duplicate:
        # Same response as a new request: no new row, no duplicate notification,
        # and nothing revealed about existing bookings.
        return Outcome(ok=True, kind="duplicate", message=APPOINTMENT_SUCCESS, record=duplicate)

    if not rate_limit.allow(db, f"appt-valid:{fingerprint}", limit=5, window_seconds=3600):
        return _too_many()

    appt = Appointment(
        reference=_new_reference(db),
        full_name=req.full_name,
        phone=req.phone,
        email=str(req.email) if req.email else None,
        preferred_date=req.preferred_date,
        preferred_session=req.preferred_session,
        preferred_time=req.preferred_time,
        message=req.message,
        status="pending",
        consent_at=utcnow(),
    )
    db.add(appt)
    db.commit()
    return Outcome(ok=True, kind="created", message=APPOINTMENT_SUCCESS, record=appt)


# --------------------------------------------------------------------------- contact
def submit_contact(
    db: Session, settings: Settings, data: Mapping[str, Any], *, fingerprint: str, origin_ok: bool
) -> Outcome:
    stop = _precheck(db, settings, data, fingerprint, origin_ok, "contact", CONTACT_SUCCESS)
    if stop:
        return stop
    try:
        req = ContactRequest.model_validate(dict(data))
    except ValidationError as exc:
        return Outcome(
            ok=False,
            status_code=422,
            kind="invalid",
            message="Please correct the highlighted fields.",
            errors=friendly_errors(exc, contact=True),
        )
    if not rate_limit.allow(db, f"contact-valid:{fingerprint}", limit=5, window_seconds=3600):
        return _too_many()
    msg = ContactMessage(
        name=req.name,
        phone=req.phone,
        email=str(req.email) if req.email else None,
        message=req.message,
        consent_at=utcnow(),
    )
    db.add(msg)
    db.commit()
    return Outcome(ok=True, kind="created", message=CONTACT_SUCCESS, record=msg)
