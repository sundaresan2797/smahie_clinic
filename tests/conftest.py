"""Shared fixtures: an isolated app + SQLite database per test."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.database import Base
from app.core.security import hash_password, issue_form_token
from app.core.timeutil import today_ist
from app.main import create_app
from app.models import AdminUser

ADMIN_PASSWORD = "correct horse battery staple"
STAFF_PASSWORD = "another long staff password"


def make_settings(tmp_path, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": "test",
        "secret_key": "test-secret-key-for-the-suite-0123456789abcdef",
        "database_url": f"sqlite:///{tmp_path / 'test.db'}",
        "site_url": "http://testserver",
        "form_min_age_seconds": 0,
        "smtp_host": None,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.fixture
def settings(tmp_path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def app(settings):
    application = create_app(settings)
    Base.metadata.create_all(application.state.engine)
    yield application
    application.state.engine.dispose()


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db(app):
    session = app.state.session_factory()
    yield session
    session.close()


@pytest.fixture
def token(settings) -> str:
    return issue_form_token(settings)


@pytest.fixture
def appointment_payload(token) -> dict[str, Any]:
    return {
        "full_name": "Priya Raman",
        "phone": "+91 98765 43210",
        "email": "priya@example.com",
        "preferred_date": (today_ist() + timedelta(days=3)).isoformat(),
        "preferred_session": "evening",
        "preferred_time": "18:00",
        "message": "Knee pain while climbing stairs.",
        "consent": True,
        "form_token": token,
        "website": "",
    }


def _make_user(db, email: str, password: str, role: str) -> AdminUser:
    user = AdminUser(email=email, password_hash=hash_password(password), role=role, is_active=True)
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def admin_user(db) -> AdminUser:
    return _make_user(db, "doctor@example.com", ADMIN_PASSWORD, "admin")


@pytest.fixture
def staff_user(db) -> AdminUser:
    return _make_user(db, "reception@example.com", STAFF_PASSWORD, "staff")


@pytest.fixture
def login(client, settings) -> Callable[..., Any]:
    def _login(email: str, password: str, next_path: str = "/admin/appointments"):
        return client.post(
            "/admin/login",
            data={"email": email, "password": password, "form_token": issue_form_token(settings), "next": next_path},
            follow_redirects=False,
        )

    return _login


def csrf_from(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, "csrf token not found in page"
    return match.group(1)
