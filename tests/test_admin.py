"""Admin authentication, authorisation, CSRF and appointment management."""

from __future__ import annotations

import csv
import io

from sqlalchemy import select

from app.core.database import utcnow
from app.models import AdminSession, Appointment, AuditLog, ContactMessage
from tests.conftest import ADMIN_PASSWORD, STAFF_PASSWORD, csrf_from


def make_appointment(db, **overrides) -> Appointment:
    from datetime import timedelta

    from app.core.timeutil import today_ist

    values = dict(
        reference="SOC-TEST01",
        full_name="Meena Kumar",
        phone="+919812345678",
        email=None,
        preferred_date=today_ist() + timedelta(days=2),
        preferred_session="morning",
        preferred_time=None,
        message="Back pain",
        status="pending",
        consent_at=utcnow(),
    )
    values.update(overrides)
    appt = Appointment(**values)
    db.add(appt)
    db.commit()
    return appt


def test_admin_requires_login(client):
    r = client.get("/admin/appointments", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/login?next=/admin/appointments"


def test_wrong_password_gives_generic_error(client, admin_user, login):
    r = login("doctor@example.com", "wrong password here")
    assert r.status_code == 400
    assert "email or password is incorrect" in r.text
    r = login("nobody@example.com", "wrong password here")
    assert "email or password is incorrect" in r.text


def test_login_sets_secure_session_cookie(client, admin_user, login):
    r = login("doctor@example.com", ADMIN_PASSWORD)
    assert r.status_code == 303 and r.headers["location"] == "/admin/appointments"
    cookie = r.headers["set-cookie"]
    assert "soc_admin=" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/admin" in cookie


def test_session_token_is_hashed_in_database(client, db, admin_user, login):
    r = login("doctor@example.com", ADMIN_PASSWORD)
    raw = r.cookies.get("soc_admin") or client.cookies.get("soc_admin")
    stored = db.scalar(select(AdminSession.token_hash))
    assert raw and stored and raw != stored and len(stored) == 64


def test_login_is_case_insensitive_for_email(client, admin_user, login):
    assert login("Doctor@Example.com", ADMIN_PASSWORD).status_code == 303


def test_login_rate_limited_per_account(client, admin_user, login):
    for _ in range(5):
        assert login("doctor@example.com", "nope nope nope").status_code == 400
    r = login("doctor@example.com", ADMIN_PASSWORD)
    assert r.status_code == 429


def test_open_redirect_blocked(client, admin_user, login):
    r = login("doctor@example.com", ADMIN_PASSWORD, next_path="//evil.example/path")
    assert r.headers["location"] == "/admin/appointments"


def test_inactive_user_cannot_login(client, db, admin_user, login):
    admin_user.is_active = False
    db.commit()
    assert login("doctor@example.com", ADMIN_PASSWORD).status_code == 400


def test_list_and_search(client, db, admin_user, login):
    make_appointment(db)
    make_appointment(db, reference="SOC-TEST02", full_name="Arjun Das", phone="+919900011122")
    login("doctor@example.com", ADMIN_PASSWORD)
    page = client.get("/admin/appointments")
    assert page.status_code == 200 and "Meena Kumar" in page.text and "Arjun Das" in page.text
    assert page.headers["cache-control"] == "no-store"
    filtered = client.get("/admin/appointments", params={"q": "99000"})
    assert "Arjun Das" in filtered.text and "Meena Kumar" not in filtered.text
    by_ref = client.get("/admin/appointments", params={"q": "soc-test01"})
    assert "Meena Kumar" in by_ref.text and "Arjun Das" not in by_ref.text


def test_status_change_requires_csrf(client, db, admin_user, login):
    appt = make_appointment(db)
    login("doctor@example.com", ADMIN_PASSWORD)
    r = client.post(f"/admin/appointments/{appt.id}/status", data={"status": "confirmed", "csrf_token": "forged"})
    assert r.status_code == 403
    db.refresh(appt)
    assert appt.status == "pending"


def test_status_change_and_audit(client, db, staff_user, login):
    appt = make_appointment(db)
    login("reception@example.com", STAFF_PASSWORD)
    csrf = csrf_from(client.get(f"/admin/appointments/{appt.id}").text)
    r = client.post(
        f"/admin/appointments/{appt.id}/status",
        data={"status": "confirmed", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert r.status_code == 303
    db.refresh(appt)
    assert appt.status == "confirmed"
    entry = db.scalar(select(AuditLog).where(AuditLog.action == "status"))
    assert entry.detail == "pending → confirmed" and entry.user_id == staff_user.id
    assert "Meena" not in (entry.detail or "")


def test_invalid_status_transition_rejected(client, db, admin_user, login):
    appt = make_appointment(db)
    login("doctor@example.com", ADMIN_PASSWORD)
    csrf = csrf_from(client.get(f"/admin/appointments/{appt.id}").text)
    r = client.post(f"/admin/appointments/{appt.id}/status", data={"status": "completed", "csrf_token": csrf})
    assert r.status_code == 400
    db.refresh(appt)
    assert appt.status == "pending"


def test_full_status_lifecycle(client, db, admin_user, login):
    appt = make_appointment(db)
    login("doctor@example.com", ADMIN_PASSWORD)
    for status in ("confirmed", "completed"):
        csrf = csrf_from(client.get(f"/admin/appointments/{appt.id}").text)
        client.post(f"/admin/appointments/{appt.id}/status", data={"status": status, "csrf_token": csrf})
    db.refresh(appt)
    assert appt.status == "completed"
    assert "No further changes" in client.get(f"/admin/appointments/{appt.id}").text


def test_notes_saved(client, db, admin_user, login):
    appt = make_appointment(db)
    login("doctor@example.com", ADMIN_PASSWORD)
    csrf = csrf_from(client.get(f"/admin/appointments/{appt.id}").text)
    client.post(f"/admin/appointments/{appt.id}/notes", data={"notes": "Called, prefers 11am", "csrf_token": csrf})
    db.refresh(appt)
    assert appt.admin_notes == "Called, prefers 11am"


def test_staff_cannot_export(client, db, staff_user, login):
    make_appointment(db)
    login("reception@example.com", STAFF_PASSWORD)
    assert client.get("/admin/export.csv").status_code == 403
    assert "Export CSV" not in client.get("/admin/appointments").text


def test_admin_export_csv_is_injection_safe(client, db, admin_user, login):
    make_appointment(db, message='=HYPERLINK("http://evil")')
    login("doctor@example.com", ADMIN_PASSWORD)
    r = client.get("/admin/export.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(r.text)))
    assert rows[0][0] == "Reference" and rows[1][2] == "Meena Kumar"
    assert rows[1][9].startswith("'=")
    assert db.scalar(select(AuditLog).where(AuditLog.action == "export")) is not None


def test_logout_revokes_session(client, db, admin_user, login):
    login("doctor@example.com", ADMIN_PASSWORD)
    csrf = csrf_from(client.get("/admin/appointments").text)
    r = client.post("/admin/logout", data={"csrf_token": csrf}, follow_redirects=False)
    assert r.status_code == 303
    assert db.scalar(select(AdminSession)) is None
    assert client.get("/admin/appointments", follow_redirects=False).status_code == 303


def test_expired_session_rejected(client, db, admin_user, login):
    from datetime import timedelta

    login("doctor@example.com", ADMIN_PASSWORD)
    sess = db.scalar(select(AdminSession))
    sess.expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    assert client.get("/admin/appointments", follow_redirects=False).status_code == 303


def test_messages_page_and_toggle(client, db, admin_user, login):
    msg = ContactMessage(name="Karthik", phone="+919840012345", message="Is there parking?", consent_at=utcnow())
    db.add(msg)
    db.commit()
    login("doctor@example.com", ADMIN_PASSWORD)
    page = client.get("/admin/messages")
    assert "Is there parking?" in page.text
    client.post(f"/admin/messages/{msg.id}/handled", data={"csrf_token": csrf_from(page.text)})
    db.refresh(msg)
    assert msg.is_handled is True and msg.handled_at is not None
