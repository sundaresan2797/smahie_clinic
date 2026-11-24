"""Password hashing, opaque tokens, public form tokens and request checks."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from enum import StrEnum
from urllib.parse import urlsplit

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Request
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner

from app.core.config import Settings

_hasher = PasswordHasher()
# Used to keep login timing similar when the account does not exist.
_DUMMY_HASH = _hasher.hash("timing-equaliser-not-a-real-password")

MIN_PASSWORD_LENGTH = 12


# --------------------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


# --------------------------------------------------------------------------- opaque tokens
def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def tokens_match(a: str | None, b: str | None) -> bool:
    return bool(a and b) and hmac.compare_digest(a, b)


# --------------------------------------------------------------------------- public form tokens
class FormTokenStatus(StrEnum):
    OK = "ok"
    INVALID = "invalid"
    EXPIRED = "expired"
    TOO_FAST = "too_fast"


def _form_signer(settings: Settings) -> TimestampSigner:
    return TimestampSigner(settings.secret_key, salt="soc-public-form")


def issue_form_token(settings: Settings) -> str:
    """A signed, timestamped token embedded in public forms.

    Public visitors get no cookies; the token proves the form was rendered by
    this site recently and enforces a minimum fill time against bots.
    """
    return _form_signer(settings).sign(secrets.token_hex(8)).decode()


def check_form_token(token: str | None, settings: Settings) -> FormTokenStatus:
    if not token:
        return FormTokenStatus.INVALID
    try:
        _value, issued = _form_signer(settings).unsign(
            token, max_age=settings.form_max_age_seconds, return_timestamp=True
        )
    except SignatureExpired:
        return FormTokenStatus.EXPIRED
    except BadSignature:
        return FormTokenStatus.INVALID
    age = time.time() - issued.timestamp()
    if age < settings.form_min_age_seconds:
        return FormTokenStatus.TOO_FAST
    return FormTokenStatus.OK


# --------------------------------------------------------------------------- request helpers
def client_ip(request: Request, settings: Settings | None = None) -> str:
    # Behind Nginx, Uvicorn's --proxy-headers / --forwarded-allow-ips sets
    # request.client from X-Forwarded-For for trusted proxies only. On Vercel the
    # platform overwrites X-Forwarded-For with the real client address.
    if settings is not None and settings.trust_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if forwarded:
            return forwarded
    return request.client.host if request.client else "unknown"


def client_fingerprint(request: Request, settings: Settings) -> str:
    """A keyed hash of the client IP so raw IP addresses are never stored."""
    digest = hmac.new(settings.secret_key.encode(), client_ip(request, settings).encode(), hashlib.sha256)
    return digest.hexdigest()[:32]


def same_origin(request: Request, settings: Settings) -> bool:
    """Reject cross-site form posts. Missing headers are tolerated (privacy tools strip them)."""
    source = request.headers.get("origin") or request.headers.get("referer")
    if not source or source == "null":
        return source is None
    host = urlsplit(source).netloc.lower()
    allowed = {urlsplit(settings.site_url).netloc.lower(), request.headers.get("host", "").lower()}
    return host in allowed
