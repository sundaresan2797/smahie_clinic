"""sitemap.xml, robots.txt, favicon, web manifest and health check."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.content.services import SERVICES
from app.core.config import STATIC_DIR
from app.core.database import get_db

router = APIRouter()

PUBLIC_PATHS = (
    "/",
    "/about",
    "/doctor",
    "/services",
    "/appointment",
    "/gallery",
    "/faq",
    "/contact",
    "/privacy",
    "/terms",
)


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap(request: Request) -> Response:
    base = request.app.state.settings.site_url
    paths = [*PUBLIC_PATHS, *(s.path for s in SERVICES)]
    urls = "".join(f"<url><loc>{base}{p}</loc></url>" for p in paths)
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
    )
    return Response(body, media_type="application/xml")


@router.get("/robots.txt", include_in_schema=False)
def robots(request: Request) -> PlainTextResponse:
    s = request.app.state.settings
    if not s.site_indexing:
        return PlainTextResponse("# Preview mode: indexing disabled until launch.\nUser-agent: *\nDisallow: /\n")
    return PlainTextResponse(
        "User-agent: *\nDisallow: /admin\nDisallow: /api/\nDisallow: /appointment/received\n\n"
        f"Sitemap: {s.site_url}/sitemap.xml\n"
    )


@router.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "images" / "icons" / "favicon.ico", headers={"Cache-Control": "public, max-age=604800"}
    )


@router.get("/site.webmanifest", include_in_schema=False)
def manifest() -> FileResponse:
    return FileResponse(STATIC_DIR / "site.webmanifest", media_type="application/manifest+json")


@router.get("/health", include_in_schema=False)
def health(db: Session = Depends(get_db)) -> JSONResponse:
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # report unhealthy without leaking details
        return JSONResponse({"status": "error", "database": "unavailable"}, status_code=503)
    return JSONResponse({"status": "ok", "database": "ok"})
