"""Alembic migrations create exactly the schema defined by the models."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect

import app.models  # noqa: F401
from app.core.database import Base, make_engine

ROOT = Path(__file__).resolve().parent.parent


def test_upgrade_head_matches_models(tmp_path):
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"db_url={url}"]})()
    command.upgrade(cfg, "head")

    engine = make_engine(url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert {
            "appointments",
            "contact_messages",
            "admin_users",
            "admin_sessions",
            "audit_log",
            "rate_limit_hits",
            "alembic_version",
        } <= tables
        with engine.connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
        assert diff == [], f"models and migrations differ: {diff}"
    finally:
        engine.dispose()

    command.downgrade(cfg, "base")
