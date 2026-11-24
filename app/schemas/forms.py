"""Pydantic schemas for the public forms, with patient-friendly error messages."""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)

from app.content.clinic import CLINIC

_NAME_FORBIDDEN = re.compile(r"[0-9<>{}\[\]@#$%^*=+_~`|\\/:;\"]")
_PHONE_STRIP = re.compile(r"[\s\-().]")
_MOBILE = re.compile(r"[6-9]\d{9}")


def normalize_indian_mobile(raw: object) -> str:
    """Accept common Indian mobile formats and return E.164 (+91XXXXXXXXXX)."""
    digits = _PHONE_STRIP.sub("", str(raw or ""))
    if digits.startswith("+91"):
        digits = digits[3:]
    elif digits.startswith("0091"):
        digits = digits[4:]
    elif digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if not _MOBILE.fullmatch(digits):
        raise ValueError("Please enter a valid 10-digit Indian mobile number.")
    return "+91" + digits


def _blank_to_none(value: object) -> object:
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _clean_name(value: str) -> str:
    value = " ".join(value.split())
    if _NAME_FORBIDDEN.search(value):
        raise ValueError("Please enter your name using letters only.")
    return value


def _consent(value: object) -> bool:
    if value in (True, "on", "true", "1", "yes", 1):
        return True
    raise ValueError("Please agree to the privacy notice to continue.")


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]


class AppointmentRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    full_name: Name
    phone: str
    email: EmailStr | None = None
    preferred_date: date
    preferred_session: Literal["morning", "evening"]
    preferred_time: str | None = None
    message: Annotated[str | None, StringConstraints(max_length=500)] = None
    consent: bool

    @field_validator("email", "preferred_time", "message", mode="before")
    @classmethod
    def _blank(cls, v: object) -> object:
        return _blank_to_none(v)

    @field_validator("full_name")
    @classmethod
    def _name(cls, v: str) -> str:
        return _clean_name(v)

    @field_validator("phone", mode="before")
    @classmethod
    def _phone(cls, v: object) -> str:
        return normalize_indian_mobile(v)

    @field_validator("consent", mode="before")
    @classmethod
    def _consent(cls, v: object) -> bool:
        return _consent(v)

    @model_validator(mode="after")
    def _time_in_session(self) -> AppointmentRequest:
        if self.preferred_time:
            session = CLINIC.session(self.preferred_session)
            if session is None or self.preferred_time not in session.slots():
                raise ValueError("preferred_time|Please choose a time within the selected session.")
        return self


class ContactRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    name: Name
    phone: str | None = None
    email: EmailStr | None = None
    message: Annotated[str, StringConstraints(min_length=10, max_length=1000)]
    consent: bool

    @field_validator("email", mode="before")
    @classmethod
    def _blank(cls, v: object) -> object:
        return _blank_to_none(v)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return _clean_name(v)

    @field_validator("phone", mode="before")
    @classmethod
    def _phone(cls, v: object) -> str | None:
        v = _blank_to_none(v)
        return None if v is None else normalize_indian_mobile(v)

    @field_validator("consent", mode="before")
    @classmethod
    def _consent(cls, v: object) -> bool:
        return _consent(v)

    @model_validator(mode="after")
    def _reachable(self) -> ContactRequest:
        if not self.phone and not self.email:
            raise ValueError("phone|Please give a mobile number or an email address so we can reply.")
        return self


# --------------------------------------------------------------------------- errors
FIELD_MESSAGES = {
    "full_name": "Please enter your full name (2–80 characters).",
    "name": "Please enter your name (2–80 characters).",
    "phone": "Please enter a valid 10-digit Indian mobile number.",
    "email": "Please enter a valid email address, or leave this blank.",
    "preferred_date": "Please choose a preferred date.",
    "preferred_session": "Please choose a morning or evening session.",
    "preferred_time": "Please choose a time within the selected session.",
    "message": "Please check the length of your message.",
    "consent": "Please agree to the privacy notice to continue.",
}

CONTACT_MESSAGE_HINT = "Please write a message between 10 and 1000 characters."


def friendly_errors(exc: ValidationError, *, contact: bool = False) -> dict[str, str]:
    """Map a ValidationError to {field: message} suitable for display."""
    errors: dict[str, str] = {}
    for err in exc.errors():
        loc = err.get("loc") or ()
        field = str(loc[0]) if loc else ""
        message = None
        if err.get("type") == "value_error":
            raw = str(err.get("ctx", {}).get("error", ""))
            if "|" in raw:  # model-level error that targets a specific field
                field, message = raw.split("|", 1)
            else:
                message = raw or None
        if contact and field == "message" and message is None:
            message = CONTACT_MESSAGE_HINT
        if not field:
            field = "form"
        errors.setdefault(field, message or FIELD_MESSAGES.get(field, "Please check this field."))
    return errors
