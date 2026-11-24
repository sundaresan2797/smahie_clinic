"""Jinja2 environment: shared context, filters and cache-busted static URLs."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.content.clinic import CLINIC, DOCTOR
from app.content.services import SERVICES
from app.core.config import STATIC_DIR, TEMPLATES_DIR
from app.core.timeutil import format_date, format_datetime, format_time, today_ist

NAV_ITEMS: tuple[tuple[str, str], ...] = (
    ("About", "/about"),
    ("Doctor", "/doctor"),
    ("Services", "/services"),
    ("Gallery", "/gallery"),
    ("FAQ", "/faq"),
    ("Contact", "/contact"),
)


@lru_cache(maxsize=1024)
def _file_hash(path: str, mtime_ns: int) -> str:  # mtime in the key invalidates on change
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:10]


def static_url(path: str) -> str:
    """`/static/<path>?v=<content hash>` so assets can be cached for a year."""
    file = STATIC_DIR / path
    try:
        version = _file_hash(str(file), file.stat().st_mtime_ns)
    except FileNotFoundError:
        return f"/static/{path}"
    return f"/static/{path}?v={version}"


def phone_display(e164: str | None) -> str:
    if not e164:
        return ""
    if e164.startswith("+91") and len(e164) == 13:
        return f"+91 {e164[3:8]} {e164[8:]}"
    return e164


def _nav_active(current: str, href: str) -> bool:
    return current == href or current.startswith(href + "/")


def site_context(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    return {
        "clinic": CLINIC,
        "doctor": DOCTOR,
        "all_services": SERVICES,
        "nav_items": NAV_ITEMS,
        "current_path": request.url.path,
        "current_year": today_ist().year,
        "csp_nonce": getattr(request.state, "csp_nonce", ""),
        "show_review": settings.show_review_markers,
        "site_indexing": settings.site_indexing,
        "site_url": settings.site_url,
        "is_active": lambda href: _nav_active(request.url.path, href),
    }


JS_MODULES = (
    "main.js",
    "animations.js",
    "scroll.js",
    "navigation.js",
    "forms.js",
    "gallery.js",
    "home.js",
    "anatomy.js",
    "utils.js",
)


def import_map() -> str:
    """Import map that pins every ES module to its content-hashed URL, so
    relative `import './x.js'` statements are cache-busted too."""
    return json.dumps({"imports": {f"/static/js/{m}": static_url(f"js/{m}") for m in JS_MODULES}})


templates = Jinja2Templates(directory=str(TEMPLATES_DIR), context_processors=[site_context])
templates.env.globals["static_url"] = static_url
templates.env.globals["import_map"] = import_map
templates.env.filters["ist_datetime"] = format_datetime
templates.env.filters["nice_date"] = format_date
templates.env.filters["nice_time"] = format_time
templates.env.filters["phone"] = phone_display
templates.env.trim_blocks = True
templates.env.lstrip_blocks = True
