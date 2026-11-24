"""Database-backed sliding-window rate limiting (works across worker processes)."""

from __future__ import annotations

import secrets
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.models import RateLimitHit


def allow(db: Session, key: str, limit: int, window_seconds: int) -> bool:
    """Record a hit for `key` and return False if the limit is already reached."""
    now = utcnow()
    since = now - timedelta(seconds=window_seconds)
    count = db.scalar(
        select(func.count()).select_from(RateLimitHit).where(RateLimitHit.key == key, RateLimitHit.created_at >= since)
    )
    if (count or 0) >= limit:
        return False
    db.add(RateLimitHit(key=key, created_at=now))
    if secrets.randbelow(50) == 0:  # occasional cleanup of old rows
        db.execute(delete(RateLimitHit).where(RateLimitHit.created_at < now - timedelta(days=2)))
    db.commit()
    return True
