"""Contact form submissions."""

from __future__ import annotations

from sqlalchemy import select

from app.models import ContactMessage


def payload(token, **overrides):
    data = {
        "name": "Karthik",
        "phone": "9840012345",
        "email": "",
        "message": "Do you have parking near the clinic?",
        "consent": True,
        "form_token": token,
        "website": "",
    }
    data.update(overrides)
    return data


def test_contact_message_stored(client, db, token):
    r = client.post("/api/contact", json=payload(token))
    assert r.status_code == 200 and r.json()["ok"] is True
    msg = db.scalar(select(ContactMessage))
    assert msg.phone == "+919840012345" and msg.is_handled is False


def test_contact_requires_phone_or_email(client, token):
    r = client.post("/api/contact", json=payload(token, phone="", email=""))
    assert r.status_code == 422
    assert "mobile number or an email" in r.json()["errors"]["phone"]


def test_contact_accepts_email_only(client, db, token):
    r = client.post("/api/contact", json=payload(token, phone="", email="karthik@example.com"))
    assert r.status_code == 200
    assert db.scalar(select(ContactMessage.email)) == "karthik@example.com"


def test_contact_message_length(client, token):
    r = client.post("/api/contact", json=payload(token, message="hi"))
    assert r.status_code == 422
    assert "10 and 1000" in r.json()["errors"]["message"]


def test_contact_html_fallback_redirects(client, db, token):
    r = client.post("/contact", data={**payload(token), "consent": "on"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/contact?sent=1")
    assert "Message sent" in client.get("/contact?sent=1").text
