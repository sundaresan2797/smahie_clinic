from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UTCDateTime, utcnow

APPOINTMENT_STATUSES = ("pending", "confirmed", "cancelled", "completed")
APPOINTMENT_SESSIONS = ("morning", "evening")

# Allowed status changes in the admin workflow.
STATUS_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "pending": ("confirmed", "cancelled"),
    "confirmed": ("completed", "cancelled", "pending"),
    "cancelled": ("pending",),
    "completed": (),
}


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint(f"status IN {APPOINTMENT_STATUSES}", name="status"),
        CheckConstraint(f"preferred_session IN {APPOINTMENT_SESSIONS}", name="session"),
        Index("ix_appointments_phone_date", "phone", "preferred_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(80))
    phone: Mapped[str] = mapped_column(String(16))  # E.164, e.g. +919876543210
    email: Mapped[str | None] = mapped_column(String(254))
    preferred_date: Mapped[date] = mapped_column(Date, index=True)
    preferred_session: Mapped[str] = mapped_column(String(10))
    preferred_time: Mapped[str | None] = mapped_column(String(5))  # "HH:MM"
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)
    admin_notes: Mapped[str | None] = mapped_column(Text)
    consent_at: Mapped[datetime] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    @property
    def allowed_transitions(self) -> tuple[str, ...]:
        return STATUS_TRANSITIONS.get(self.status, ())
