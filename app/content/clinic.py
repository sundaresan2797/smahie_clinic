"""Single source of truth for clinic and doctor facts.

Only information confirmed by the clinic belongs here. Anything still awaiting
confirmation is `None` / empty and marked `TODO(clinic)`; templates hide empty
values and (while SHOW_REVIEW_MARKERS is on) list them as "to be confirmed".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time


@dataclass(frozen=True)
class ConsultationSession:
    key: str
    label: str
    start: time
    end: time
    display: str

    def slots(self, step_minutes: int = 30) -> list[str]:
        """Preferred-time options, ending 30 minutes before the session closes."""
        out: list[str] = []
        minutes = self.start.hour * 60 + self.start.minute
        last = self.end.hour * 60 + self.end.minute - 30
        while minutes <= last:
            out.append(f"{minutes // 60:02d}:{minutes % 60:02d}")
            minutes += step_minutes
        return out


@dataclass(frozen=True)
class Clinic:
    name: str
    tagline: str
    pillars: tuple[str, ...]
    locality: str
    area: str
    city: str
    state: str
    country: str
    country_code: str
    phone_e164: str
    phone_display: str
    sessions: tuple[ConsultationSession, ...]
    # ---- awaiting confirmation -------------------------------------------
    street_address: str | None = None
    postal_code: str | None = None
    maps_url: str | None = None
    email: str | None = None
    whatsapp_e164: str | None = None
    consultation_days: str | None = None
    consultation_fee: str | None = None
    hospital_affiliations: tuple[str, ...] = field(default_factory=tuple)

    @property
    def short_location(self) -> str:
        return f"{self.locality}, {self.area}, {self.city}"

    @property
    def tel_href(self) -> str:
        return f"tel:{self.phone_e164}"

    def session(self, key: str) -> ConsultationSession | None:
        return next((s for s in self.sessions if s.key == key), None)

    @property
    def pending_items(self) -> list[str]:
        items = []
        if not self.street_address:
            items.append("Full street address and PIN code")
        if not self.maps_url:
            items.append("Google Maps location / directions link")
        if not self.consultation_days:
            items.append("Consultation days (and holiday closures)")
        if not self.email:
            items.append("Clinic email address")
        if not self.consultation_fee:
            items.append("Consultation fees")
        if not self.hospital_affiliations:
            items.append("Current hospital affiliations")
        if not self.whatsapp_e164:
            items.append("WhatsApp number (if the clinic uses one)")
        return items


@dataclass(frozen=True)
class Doctor:
    name: str
    qualifications: str
    title: str
    photo_alt: str
    # ---- awaiting confirmation -------------------------------------------
    registration_number: str | None = None
    languages: tuple[str, ...] = field(default_factory=tuple)
    experience_summary: str | None = None
    areas_of_interest: tuple[str, ...] = field(default_factory=tuple)

    @property
    def pending_items(self) -> list[str]:
        items = []
        if not self.registration_number:
            items.append("Medical council registration number")
        if not self.languages:
            items.append("Languages spoken")
        if not self.experience_summary:
            items.append("Professional experience and training history")
        if not self.areas_of_interest:
            items.append("Clinical areas of interest")
        return items


CLINIC = Clinic(
    name="SMAHIE ORTHO CARE",
    tagline="Care That Keeps You Moving.",
    pillars=("Bone", "Spine", "Joint", "Movement"),
    locality="Thirumalai Nagar",
    area="Perungudi",
    city="Chennai",
    state="Tamil Nadu",
    country="India",
    country_code="IN",
    phone_e164="+919445489809",
    phone_display="+91 94454 89809",
    sessions=(
        ConsultationSession("morning", "Morning", time(10, 0), time(13, 0), "10:00 AM – 1:00 PM"),
        ConsultationSession("evening", "Evening", time(17, 0), time(20, 30), "5:00 PM – 8:30 PM"),
    ),
    # TODO(clinic): street_address, postal_code, maps_url, email, whatsapp_e164,
    # consultation_days, consultation_fee, hospital_affiliations
)

DOCTOR = Doctor(
    name="Dr. Arun Selvan R",
    qualifications="MBBS, MS (Ortho)",
    title="Consultant Orthopaedic Surgeon",
    photo_alt="Dr. Arun Selvan R, Consultant Orthopaedic Surgeon, in a white coat with arms folded",
    # TODO(clinic): registration_number, languages, experience_summary, areas_of_interest
)
