"""Behaviour specific to running on Vercel (serverless)."""

from __future__ import annotations

import pytest
from sqlalchemy.pool import NullPool, QueuePool
from starlette.requests import Request

from app.core.config import Settings
from app.core.database import make_engine
from app.core.security import client_ip, issue_form_token
from tests.conftest import make_settings
from tests.test_appointments import FakeSMTP

VERCEL_VARS = (
    "VERCEL",
    "VERCEL_ENV",
    "VERCEL_PROJECT_PRODUCTION_URL",
    "DATABASE_URL",
    "POSTGRES_URL",
    "SITE_URL",
    "ENVIRONMENT",
    "SECRET_KEY",
)


@pytest.fixture
def clean_env(monkeypatch):
    for name in VERCEL_VARS:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


@pytest.mark.parametrize("scheme", ["postgres://", "postgresql://"])
def test_hosted_postgres_urls_get_the_psycopg_driver(clean_env, scheme):
    s = Settings(_env_file=None, environment="test", database_url=f"{scheme}u:p@db.example/neondb?sslmode=require")
    assert s.database_url == "postgresql+psycopg://u:p@db.example/neondb?sslmode=require"


def test_postgres_url_alias_is_accepted(clean_env):
    clean_env.setenv("POSTGRES_URL", "postgres://u:p@db.example/neondb")
    assert Settings(_env_file=None, environment="test").database_url.startswith("postgresql+psycopg://")


def test_vercel_defaults(clean_env):
    clean_env.setenv("VERCEL", "1")
    clean_env.setenv("VERCEL_ENV", "production")
    clean_env.setenv("VERCEL_PROJECT_PRODUCTION_URL", "smahie-ortho-care.vercel.app")
    clean_env.setenv("SECRET_KEY", "s" * 48)
    clean_env.setenv("DATABASE_URL", "postgres://u:p@db.example/neondb")
    s = Settings(_env_file=None)
    assert s.environment == "production"
    assert s.site_url == "https://smahie-ortho-care.vercel.app"
    assert s.serverless is True and s.trust_forwarded_for is True


def test_vercel_production_without_database_fails_clearly(clean_env):
    clean_env.setenv("VERCEL", "1")
    clean_env.setenv("VERCEL_ENV", "production")
    clean_env.setenv("VERCEL_PROJECT_PRODUCTION_URL", "smahie-ortho-care.vercel.app")
    clean_env.setenv("SECRET_KEY", "s" * 48)
    with pytest.raises(ValueError, match="PostgreSQL"):
        Settings(_env_file=None)


def test_local_defaults_unchanged(clean_env):
    s = Settings(_env_file=None)
    assert s.environment == "development" and s.site_url == "http://localhost:8000"
    assert s.serverless is False and s.trust_forwarded_for is False


def _request(forwarded: str | None) -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    return Request({"type": "http", "headers": headers, "client": ("10.0.0.7", 5555)})


def test_client_ip_trusts_forwarded_for_only_when_configured(tmp_path):
    trusted = make_settings(tmp_path, trust_forwarded_for=True)
    untrusted = make_settings(tmp_path, trust_forwarded_for=False)
    assert client_ip(_request("203.0.113.9, 10.0.0.1"), trusted) == "203.0.113.9"
    assert client_ip(_request("203.0.113.9"), untrusted) == "10.0.0.7"
    assert client_ip(_request(None), trusted) == "10.0.0.7"


def test_serverless_engine_does_not_pool():
    url = "postgresql+psycopg://u:p@localhost/smahie"
    assert isinstance(make_engine(url, serverless=True).pool, NullPool)
    assert isinstance(make_engine(url).pool, QueuePool)


def test_notification_sent_before_response_when_serverless(tmp_path, monkeypatch, appointment_payload):
    from fastapi.testclient import TestClient

    from app.core.database import Base
    from app.main import create_app
    from app.services import email_service

    FakeSMTP.sent = []
    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)
    settings = make_settings(
        tmp_path,
        serverless=True,
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


def test_build_script_skips_migrations_outside_production(clean_env, capsys):
    from app.core.config import get_settings
    from scripts import vercel_build

    clean_env.setenv("VERCEL_ENV", "preview")
    clean_env.setenv("ENVIRONMENT", "test")
    get_settings.cache_clear()
    try:
        assert vercel_build.main() == 0
    finally:
        get_settings.cache_clear()
    assert "skipping database migrations" in capsys.readouterr().out


def test_build_script_reports_missing_configuration(clean_env, capsys):
    from app.core.config import get_settings
    from scripts import vercel_build

    clean_env.setenv("VERCEL", "1")
    clean_env.setenv("VERCEL_ENV", "production")
    clean_env.setenv("VERCEL_PROJECT_PRODUCTION_URL", "smahie-ortho-care.vercel.app")
    get_settings.cache_clear()
    try:
        assert vercel_build.main() == 1
    finally:
        get_settings.cache_clear()
    out = capsys.readouterr().out
    assert "SECRET_KEY" in out and "DATABASE_URL" in out


def test_build_script_migrates_in_production(clean_env, tmp_path, capsys):
    from sqlalchemy import inspect

    from app.core.config import get_settings
    from scripts import vercel_build

    db = tmp_path / "prod.db"
    clean_env.setenv("VERCEL_ENV", "production")
    clean_env.setenv("ENVIRONMENT", "test")  # allow SQLite for this test
    clean_env.setenv("DATABASE_URL", f"sqlite:///{db}")
    get_settings.cache_clear()
    try:
        assert vercel_build.main() == 0
    finally:
        get_settings.cache_clear()
    assert "appointments" in inspect(make_engine(f"sqlite:///{db}")).get_table_names()
