"""Security headers (with a per-request CSP nonce) and privacy-aware request logging."""

from __future__ import annotations

import logging
import secrets
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

log = logging.getLogger("smahie.http")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = request.app.state.settings
        nonce = secrets.token_urlsafe(16)
        request.state.csp_nonce = nonce
        started = time.perf_counter()

        response = await call_next(request)

        csp = [
            "default-src 'self'",
            f"script-src 'self' 'nonce-{nonce}'",
            "style-src 'self'",
            "img-src 'self' data:",
            "font-src 'self'",
            "connect-src 'self'",
            "media-src 'self'",
            "object-src 'none'",
            "frame-src 'none'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "manifest-src 'self'",
        ]
        if settings.is_production:
            csp.append("upgrade-insecure-requests")

        h = response.headers
        h.setdefault("Content-Security-Policy", "; ".join(csp))
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        h.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()",
        )
        if settings.is_production:
            h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

        path = request.url.path
        if path.startswith("/admin") or path.startswith("/api"):
            h["Cache-Control"] = "no-store"
            h["X-Robots-Tag"] = "noindex, nofollow"
        elif not settings.site_indexing:
            h["X-Robots-Tag"] = "noindex, nofollow"

        # Log method, path and status only: never query strings (admin searches
        # can contain patient names) or request bodies.
        if not path.startswith("/static"):
            log.info(
                "%s %s %s %.0fms", request.method, path, response.status_code, (time.perf_counter() - started) * 1000
            )
        return response
