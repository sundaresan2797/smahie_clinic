"""Staff authentication: Argon2 passwords and hashed server-side sessions."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import utcnow
from app.core.security import (
    hash_password,
    hash_token,
    new_token,
    password_needs_rehash,
    verify_password,
)
from app.models import AdminSession, AdminUser, AuditLog

SESSION_COOKIE = "soc_admin"


def authenticate(db: Session, email: str, password: str) -> AdminUser | None:
    user = db.scalar(select(AdminUser).where(func.lower(AdminUser.email) == email.strip().lower()))
    valid = verify_password(user.password_hash if user else None, password)
    if not (valid and user and user.is_active):
        return None
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    return user


def create_session(db: Session, user: AdminUser, settings: Settings) -> str:
    token = new_token()
    now = utcnow()
    db.add(
        AdminSession(
            token_hash=hash_token(token),
            user_id=user.id,
            csrf_token=new_token(),
            created_at=now,
            expires_at=now + timedelta(hours=settings.admin_session_hours),
        )
    )
    user.last_login_at = now
    db.execute(delete(AdminSession).where(AdminSession.expires_at < now))
    db.commit()
    return token


def load_session(db: Session, token: str | None) -> AdminSession | None:
    if not token:
        return None
    sess = db.scalar(select(AdminSession).where(AdminSession.token_hash == hash_token(token)))
    if sess is None:
        return None
    if sess.expires_at <= utcnow() or not sess.user.is_active:
        db.delete(sess)
        db.commit()
        return None
    return sess


def revoke_session(db: Session, sess: AdminSession) -> None:
    db.delete(sess)
    db.commit()


def revoke_all_sessions(db: Session, user: AdminUser) -> None:
    db.execute(delete(AdminSession).where(AdminSession.user_id == user.id))
    db.commit()


def audit(
    db: Session,
    user_id: int | None,
    action: str,
    target_type: str | None = None,
    target_id: int | None = None,
    detail: str | None = None,
) -> None:
    """Add an audit entry (caller commits). Never pass patient details in `detail`."""
    db.add(AuditLog(user_id=user_id, action=action, target_type=target_type, target_id=target_id, detail=detail))
