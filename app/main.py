"""FastAPI application factory for the SMAHIE ORTHO CARE website."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import STATIC_DIR, Settings, get_settings
from app.core.database import make_engine, make_session_factory
from app.core.middleware import SecurityHeadersMiddleware
from app.core.templating import templates
from app.routers import admin, forms, pages, system
from app.services import seo

log = logging.getLogger("smahie")


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _error_page(request: Request, status_code: int, title: str, message: str) -> Response:
    if request.url.path.startswith("/api/"):
        return JSONResponse({"ok": False, "message": message}, status_code=status_code)
    template = "errors/404.html" if status_code == 404 else "errors/error.html"
    meta = seo.page_meta(
        request.app.state.settings, title=title, description=message, path=request.url.path, noindex=True
    )
    return templates.TemplateResponse(
        request,
        template,
        {"meta": meta, "page": "error", "code": status_code, "title": title, "message": message},
        status_code=status_code,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    app = FastAPI(
        title="SMAHIE ORTHO CARE",
        docs_url=None,  # no public API explorer on a clinic website
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings
    app.state.engine = make_engine(settings.database_url, serverless=settings.serverless)
    app.state.session_factory = make_session_factory(app.state.engine)

    app.add_middleware(SecurityHeadersMiddleware)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    app.include_router(pages.router)
    app.include_router(forms.router)
    app.include_router(admin.router)
    app.include_router(system.router)

    @app.exception_handler(admin.LoginRequired)
    async def _login_required(request: Request, exc: admin.LoginRequired) -> Response:
        return RedirectResponse(f"/admin/login?next={exc.next_path}", status_code=303)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> Response:
        if exc.status_code == 404:
            return _error_page(
                request, 404, "Page not found", "The page you are looking for has moved or does not exist."
            )
        if exc.status_code == 405 and request.url.path.startswith("/api/"):
            return JSONResponse({"ok": False, "message": "Method not allowed."}, status_code=405)
        detail = exc.detail if isinstance(exc.detail, str) else "Something went wrong."
        return _error_page(request, exc.status_code, "Request not completed", detail)

    @app.exception_handler(Exception)
    async def _server_error(request: Request, exc: Exception) -> Response:
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        return _error_page(
            request, 500, "Something went wrong", "An unexpected error occurred. Please try again, or call the clinic."
        )

    return app


app = create_app()
