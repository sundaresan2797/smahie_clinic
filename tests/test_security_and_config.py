"""Security helpers, production settings guards and schema helpers."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security import (
    FormTokenStatus,
    check_form_token,
    hash_password,
    issue_form_token,
    verify_password,
)
from app.schemas.forms import normalize_indian_mobile
from tests.conftest import make_settings


def test_password_hashing_roundtrip():
    h = hash_password("a very long password")
    assert h.startswith("$argon2")
    assert verify_password(h, "a very long password")
    assert not verify_password(h, "wrong")
    assert not verify_password(None, "anything")


def test_form_token_states(tmp_path):
    s = make_settings(tmp_path)
    assert check_form_token(issue_form_token(s), s) is FormTokenStatus.OK
    assert check_form_token("garbage", s) is FormTokenStatus.INVALID
    other = make_settings(tmp_path, secret_key="a-different-secret-key-0123456789-abcdef")
    assert check_form_token(issue_form_token(other), s) is FormTokenStatus.INVALID
    slow = make_settings(tmp_path, form_min_age_seconds=60)
    assert check_form_token(issue_form_token(slow), slow) is FormTokenStatus.TOO_FAST


@pytest.mark.parametrize(
    "overrides,message",
    [
        ({"secret_key": "short"}, "SECRET_KEY"),
        ({"site_url": "http://example.com"}, "https"),
        ({"database_url": "sqlite:///x.db"}, "PostgreSQL"),
    ],
)
def test_production_settings_are_guarded(overrides, message):
    values = {
        "environment": "production",
        "secret_key": "p" * 48,
        "site_url": "https://smahieorthocare.example",
        "database_url": "postgresql+psycopg://user:pass@localhost/smahie",
    }
    values.update(overrides)
    with pytest.raises(ValidationError, match=message):
        Settings(_env_file=None, **values)


def test_hsts_only_in_production():
    from fastapi.testclient import TestClient

    from app.main import create_app

    settings = Settings(
        _env_file=None,
        environment="production",
        secret_key="p" * 48,
        site_url="https://smahieorthocare.example",
        database_url="postgresql+psycopg://user:pass@localhost/smahie",
    )
    app = create_app(settings)  # engine is lazy; robots.txt never touches the database
    with TestClient(app) as c:
        r = c.get("/robots.txt")
    assert "max-age=31536000" in r.headers["strict-transport-security"]
    assert "upgrade-insecure-requests" in r.headers["content-security-policy"]


@pytest.mark.parametrize(
    "raw,expected",
    [("9445489809", "+919445489809"), ("+91-94454-89809", "+919445489809"), ("(0) 94454 89809", "+919445489809")],
)
def test_normalize_mobile(raw, expected):
    assert normalize_indian_mobile(raw) == expected


def test_normalize_mobile_rejects_landline():
    with pytest.raises(ValueError):
        normalize_indian_mobile("044 2496 1234")
