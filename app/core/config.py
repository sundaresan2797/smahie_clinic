"""Application settings, loaded from environment variables or a local .env file."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
APP_DIR = BASE_DIR / "app"
STATIC_DIR = APP_DIR / "static"
TEMPLATES_DIR = APP_DIR / "templates"

INSECURE_DEV_KEY = "dev-only-insecure-secret-key-do-not-use-in-production"


# ---- Vercel-aware defaults (explicit environment variables always win) ----
def _on_vercel() -> bool:
    return bool(os.environ.get("VERCEL"))


def _default_environment() -> str:
    return "production" if os.environ.get("VERCEL_ENV") in ("production", "preview") else "development"


def normalize_database_url(value: str) -> str:
    """Hosted providers hand out postgres:// URLs; SQLAlchemy needs the driver name."""
    for prefix in ("postgres://", "postgresql://"):
        if value.startswith(prefix):
            return "postgresql+psycopg://" + value[len(prefix) :]
    return value


def _default_site_url() -> str:
    host = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL")  # bare hostname, no scheme
    return f"https://{host}" if host else "http://localhost:8000"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Literal["development", "production", "test"] = Field(default_factory=_default_environment)
    secret_key: str = INSECURE_DEV_KEY
    # DATABASE_URL, or POSTGRES_URL as set by Vercel's Postgres (Neon) integration.
    database_url: str = Field(
        default=f"sqlite:///{BASE_DIR / 'data' / 'smahie.db'}",
        validation_alias=AliasChoices("DATABASE_URL", "POSTGRES_URL", "database_url"),
    )
    site_url: str = Field(default_factory=_default_site_url)
    log_level: str = "INFO"

    # Hosting. On Vercel both default to on: the real client IP comes from the
    # X-Forwarded-For header that Vercel overwrites, and database connections
    # are not pooled in-process (use the provider's pooled connection string).
    trust_forwarded_for: bool = Field(default_factory=_on_vercel)
    serverless: bool = Field(default_factory=_on_vercel)

    # Publishing controls. Keep indexing off and review markers on until the
    # clinic has approved the content (see docs/LAUNCH_CHECKLIST.md).
    site_indexing: bool = False
    show_review_markers: bool = True

    # Optional SMTP notifications to the clinic inbox.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_starttls: bool = True
    clinic_notification_email: str | None = None

    # Public form protection and booking rules.
    form_min_age_seconds: int = 3
    form_max_age_seconds: int = 7200
    appointment_max_days_ahead: int = 90
    admin_session_hours: int = 8

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_from and self.clinic_notification_email)

    @field_validator("database_url")
    @classmethod
    def _postgres_driver(cls, value: str) -> str:
        return normalize_database_url(value)

    @model_validator(mode="after")
    def _validate(self) -> Settings:
        self.site_url = self.site_url.rstrip("/")
        if self.environment == "production":
            if self.secret_key == INSECURE_DEV_KEY or len(self.secret_key) < 32:
                raise ValueError("SECRET_KEY must be a random value of at least 32 characters in production.")
            if not self.site_url.startswith("https://"):
                raise ValueError("SITE_URL must start with https:// in production.")
            if self.database_url.startswith("sqlite"):
                raise ValueError("Use PostgreSQL (DATABASE_URL=postgresql+psycopg://...) in production.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
