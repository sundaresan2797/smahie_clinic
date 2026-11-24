"""Vercel build step (configured in pyproject.toml under [tool.vercel.scripts]).

Runs after dependencies are installed:
- checks that the required environment variables are present, with a clear
  message instead of a confusing runtime failure;
- applies database migrations on **production** deployments only, so preview
  deployments can never change the live database.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

from pydantic import ValidationError

from app.core.config import BASE_DIR, get_settings, normalize_database_url

HELP = """
Set these in Vercel -> Project -> Settings -> Environment Variables (Production and Preview):
  SECRET_KEY    random value, e.g. python -c "import secrets; print(secrets.token_urlsafe(48))"
  DATABASE_URL  added automatically when you connect a Postgres database
                (Vercel -> Storage -> Create Database -> Neon -> connect to this project)
See docs/DEPLOY_VERCEL.md.
"""


def main() -> int:
    vercel_env = os.environ.get("VERCEL_ENV", "development")
    try:
        settings = get_settings()
    except ValidationError as exc:
        print("Configuration error:")
        for err in exc.errors():
            print(f"  - {err.get('msg')}")
        print(HELP)
        return 1

    if vercel_env != "production":
        print(f"VERCEL_ENV={vercel_env}: skipping database migrations (production deployments only).")
        return 0

    from alembic import command
    from alembic.config import Config

    # Prefer the direct (non-pooled) connection for schema changes when the provider offers one.
    url = normalize_database_url(os.environ.get("DATABASE_URL_UNPOOLED") or settings.database_url)
    cfg = Config(str(BASE_DIR / "alembic.ini"))
    cfg.cmd_opts = SimpleNamespace(x=[f"db_url={url}"])
    command.upgrade(cfg, "head")
    print("Database migrations applied (alembic upgrade head).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
