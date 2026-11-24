"""Appointment request validation, anti-spam, storage and notifications."""

from __future__ import annotations

from datetime import timedelta
from typing import ClassVar

import pytest
from sqlalchemy import func, select

from app.core.security import issue_form_token
from app.core.timeutil import today_ist
from app.models import Appointment
from app.services.submissions import APPOINTMENT_SUCCESS


def count(db) -> int:
    return db.scalar(select(func.count()).select_from(Appointment))


def test_valid_request_is_stored_as_pending(client, db, appointment_payload):
    r = client.post("/api/appointments", json=appointment_payload)
    assert r.status_code == 200
    assert r.json() == {"ok": True, "message": APPOINTMENT_SUCCESS}
    appt = db.scalar(select(Appointment))
    assert appt.status == "pending"
    assert appt.phone == "+919876543210"
    assert appt.preferred_session == "evening" and appt.preferred_time == "18:00"
    assert appt.reference.startswith("SOC-") and len(appt.reference) == 10
    assert appt.consent_at is not None


def test_success_message_matches_brief(client, appointment_payload):
    message = client.post("/api/appointments", json=appointment_payload).json()["message"]
    assert message == (
        "Your appointment request has been received. Our clinic team will contact you to confirm the availability."
    )


@pytest.mark.parametrize(
    "raw", ["9876543210", "+91 98765 43210", "09876543210", "98765-43210", "+919876543210", "0091 98765 43210"]
)
def test_indian_mobile_formats_are_normalised(client, db, appointment_payload, raw):
    appointment_payload["phone"] = raw
    assert client.post("/api/appointments", json=appointment_payload).status_code == 200
    assert db.scalar(select(Appointment.phone)) == "+919876543210"


@pytest.mark.parametrize("raw", ["12345", "5876543210", "98765432101", "+1 202 555 0100", "abcdefghij"])
def test_invalid_mobile_numbers_rejected(client, appointment_payload, raw):
    appointment_payload["phone"] = raw
    r = client.post("/api/appointments", json=appointment_payload)
    assert r.status_code == 422
    assert "Indian mobile" in r.json()["errors"]["phone"]


def test_past_date_rejected(client, appointment_payload):
    appointment_payload["preferred_date"] = (today_ist() - timedelta(days=1)).isoformat()
    r = client.post("/api/appointments", json=appointment_payload)
    assert r.status_code == 422
    assert "future date" in r.json()["errors"]["preferred_date"]


def test_date_too_far_ahead_rejected(client, appointment_payload):
    appointment_payload["preferred_date"] = (today_ist() + timedelta(days=200)).isoformat()
    r = client.post("/api/appointments", json=appointment_payload)
    assert r.status_code == 422
    assert "next 90 days" in r.json()["errors"]["preferred_date"]


def test_time_must_belong_to_session(client, appointment_payload):
    appointment_payload["preferred_session"] = "morning"
    appointment_payload["preferred_time"] = "18:00"
    r = client.post("/api/appointments", json=appointment_payload)
    assert r.status_code == 422
    assert "preferred_time" in r.json()["errors"]


def test_consent_required(client, appointment_payload):
    appointment_payload["consent"] = False
    r = client.post("/api/appointments", json=appointment_payload)
    assert r.status_code == 422
    assert "privacy notice" in r.json()["errors"]["consent"]


def test_missing_fields_reported_together(client, token):
    r = client.post("/api/appointments", json={"form_token": token})
    assert r.status_code == 422
    errors = r.json()["errors"]
    assert {"full_name", "phone", "preferred_date", "preferred_session", "consent"} <= set(errors)


def test_name_with_digits_or_markup_rejected(client, appointment_payload):
    appointment_payload["full_name"] = "<script>alert(1)</script>"
    r = client.post("/api/appointments", json=appointment_payload)
    assert r.status_code == 422 and "full_name" in r.json()["errors"]


def test_optional_fields_may_be_blank(client, db, appointment_payload):
    appointment_payload.update(email="", preferred_time="", message="")
    assert client.post("/api/appointments", json=appointment_payload).status_code == 200
    appt = db.scalar(select(Appointment))
    assert appt.email is None and appt.preferred_time is None and appt.message is None


def test_honeypot_pretends_success_but_stores_nothing(client, db, appointment_payload):
    appointment_payload["website"] = "http://spam.example"
    r = client.post("/api/appointments", json=appointment_payload)
    assert r.status_code == 200 and r.json()["ok"] is True
    assert count(db) == 0


@pytest.mark.parametrize("bad_token", ["", "not-a-token", "abc.def.ghi"])
def test_invalid_form_token_rejected(client, db, appointment_payload, bad_token):
    appointment_payload["form_token"] = bad_token
    r = client.post("/api/appointments", json=appointment_payload)
    assert r.status_code == 400
    assert "expired" in r.json()["message"]
    assert count(db) == 0


def test_too_fast_submission_rejected(tmp_path, appointment_payload):
    from fastapi.testclient import TestClient

    from app.core.database import Base
    from app.main import create_app
    from tests.conftest import make_settings

    settings = make_settings(tmp_path, form_min_age_seconds=30)
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    appointment_payload["form_token"] = issue_form_token(settings)
    with TestClient(app) as c:
        r = c.post("/api/appointments", json=appointment_payload)
    assert r.status_code == 400 and "very quick" in r.json()["message"]


def test_duplicate_request_not_stored_twice(client, db, appointment_payload):
    assert client.post("/api/appointments", json=appointment_payload).status_code == 200
    r = client.post("/api/appointments", json=appointment_payload)
    assert r.status_code == 200 and r.json()["ok"] is True
    assert count(db) == 1


def test_rate_limit_on_valid_submissions(client, db, appointment_payload):
    for day in range(1, 6):
        appointment_payload["preferred_date"] = (today_ist() + timedelta(days=day)).isoformat()
        assert client.post("/api/appointments", json=appointment_payload).status_code == 200
    appointment_payload["preferred_date"] = (today_ist() + timedelta(days=10)).isoformat()
    r = client.post("/api/appointments", json=appointment_payload)
    assert r.status_code == 429
    assert "+91 94454 89809" in r.json()["message"]
    assert count(db) == 5


def test_cross_origin_post_rejected(client, db, appointment_payload):
    r = client.post("/api/appointments", json=appointment_payload, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert count(db) == 0


def test_same_origin_header_accepted(client, appointment_payload):
    r = client.post("/api/appointments", json=appointment_payload, headers={"Origin": "http://testserver"})
    assert r.status_code == 200


def test_non_json_body_rejected(client, appointment_payload):
    r = client.post("/api/appointments", data={"full_name": "x"})
    assert r.status_code == 415


def test_no_public_listing_of_appointments(client, appointment_payload):
    client.post("/api/appointments", json=appointment_payload)
    r = client.get("/api/appointments")
    assert r.status_code == 405
    assert "Priya" not in r.text


def test_html_form_fallback_success(client, db, appointment_payload):
    form = {**appointment_payload, "consent": "on"}
    r = client.post("/appointment", data=form, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/appointment/received"
    assert count(db) == 1
    page = client.get("/appointment/received")
    assert "contact you to confirm the availability" in page.text
    assert "noindex" in page.text


def test_html_form_fallback_shows_errors_and_keeps_values(client, db, appointment_payload):
    form = {**appointment_payload, "phone": "123", "consent": "on"}
    r = client.post("/appointment", data=form)
    assert r.status_code == 422
    assert "valid 10-digit Indian mobile number" in r.text
    assert 'value="Priya Raman"' in r.text
    assert 'aria-invalid="true"' in r.text
    assert count(db) == 0


def test_output_is_escaped_in_form_fallback(client, appointment_payload):
    form = {**appointment_payload, "message": '<img src=x onerror="alert(1)">', "phone": "1"}
    r = client.post("/appointment", data=form)
    assert '<img src=x onerror="alert(1)">' not in r.text
    assert "&lt;img src=x" in r.text


class FakeSMTP:
    sent: ClassVar[list] = []

    def __init__(self, host, port, timeout=None):
        self.host = host

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        pass

    def login(self, user, password):
        pass

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


def test_email_notification_has_no_patient_details(tmp_path, monkeypatch, appointment_payload):
    from fastapi.testclient import TestClient

    from app.core.database import Base
    from app.main import create_app
    from app.services import email_service
    from tests.conftest import make_settings

    FakeSMTP.sent = []
    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)
    settings = make_settings(
        tmp_path,
        smtp_host="smtp.example.com",
        smtp_from="site@example.com",
        clinic_notification_email="clinic@example.com",
    )
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    appointment_payload["form_token"] = issue_form_token(settings)
    with TestClient(app) as c:
        assert c.post("/api/appointments", json=appointment_payload).status_code == 200
    assert len(FakeSMTP.sent) == 1
    body = FakeSMTP.sent[0].get_content()
    assert "SOC-" in FakeSMTP.sent[0]["Subject"]
    assert "Priya" not in body and "98765" not in body and "Knee pain" not in body
    assert "/admin/appointments" in body
