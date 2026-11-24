"""Protected clinic admin area: appointment requests, messages and export."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.content.clinic import CLINIC
from app.core import rate_limit
from app.core.database import get_db, utcnow
from app.core.security import (
    FormTokenStatus,
    check_form_token,
    client_fingerprint,
    issue_form_token,
    same_origin,
    tokens_match,
)
from app.core.templating import templates
from app.core.timeutil import format_datetime, format_time, today_ist
from app.models import (
    APPOINTMENT_STATUSES,
    AdminSession,
    AdminUser,
    Appointment,
    AuditLog,
    ContactMessage,
)
from app.services.auth_service import (
    SESSION_COOKIE,
    audit,
    authenticate,
    create_session,
    load_session,
    revoke_session,
)

router = APIRouter(prefix="/admin")
PAGE_SIZE = 25


class LoginRequired(Exception):
    def __init__(self, next_path: str = "/admin/appointments") -> None:
        self.next_path = next_path


@dataclass
class AdminContext:
    user: AdminUser
    session: AdminSession


def current_admin(request: Request, db: Session = Depends(get_db)) -> AdminContext:
    sess = load_session(db, request.cookies.get(SESSION_COOKIE))
    if sess is None:
        raise LoginRequired(request.url.path)
    return AdminContext(user=sess.user, session=sess)


def require_admin_role(ctx: AdminContext = Depends(current_admin)) -> AdminContext:
    if not ctx.user.is_admin:
        raise HTTPException(status_code=403, detail="Only clinic administrators can do this.")
    return ctx


def verify_post(request: Request, ctx: AdminContext, csrf_token: str) -> None:
    if not same_origin(request, request.app.state.settings) or not tokens_match(ctx.session.csrf_token, csrf_token):
        raise HTTPException(status_code=403, detail="This form has expired. Please reload the page.")


def _safe_next(path: str | None) -> str:
    if path and re.fullmatch(r"/admin(/[A-Za-z0-9/_\-]*)?", path) and path != "/admin/login":
        return path
    return "/admin/appointments"


def _render(
    request: Request, template: str, ctx: AdminContext | None, status_code: int = 200, **context: Any
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        template,
        {
            "admin": ctx.user if ctx else None,
            "csrf": ctx.session.csrf_token if ctx else "",
            "statuses": APPOINTMENT_STATUSES,
            **context,
        },
        status_code=status_code,
    )


# --------------------------------------------------------------------------- auth
@router.get("", include_in_schema=False)
def admin_root() -> RedirectResponse:
    return RedirectResponse("/admin/appointments", status_code=303)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str | None = None, db: Session = Depends(get_db)):
    if load_session(db, request.cookies.get(SESSION_COOKIE)):
        return RedirectResponse(_safe_next(next), status_code=303)
    return _render(
        request,
        "admin/login.html",
        None,
        form_token=issue_form_token(request.app.state.settings),
        next=_safe_next(next),
        error=None,
        email="",
    )


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    email: str = Form(""),
    password: str = Form(""),
    form_token: str = Form(""),
    next: str = Form("/admin/appointments"),
    db: Session = Depends(get_db),
):
    settings = request.app.state.settings

    def fail(message: str, status: int) -> HTMLResponse:
        return _render(
            request,
            "admin/login.html",
            None,
            status_code=status,
            form_token=issue_form_token(settings),
            next=_safe_next(next),
            error=message,
            email=email[:254],
        )

    token_status = check_form_token(form_token, settings)
    if not same_origin(request, settings) or token_status in (FormTokenStatus.INVALID, FormTokenStatus.EXPIRED):
        return fail("The sign-in form expired. Please try again.", 400)

    fingerprint = client_fingerprint(request, settings)
    account_key = email.strip().lower()[:254]
    if not rate_limit.allow(db, f"login-ip:{fingerprint}", limit=10, window_seconds=900) or not rate_limit.allow(
        db, f"login-acct:{account_key}", limit=5, window_seconds=900
    ):
        return fail("Too many sign-in attempts. Please wait 15 minutes and try again.", 429)

    user = authenticate(db, email, password)
    if user is None:
        return fail("The email or password is incorrect.", 400)

    token = create_session(db, user, settings)
    audit(db, user.id, "login")
    db.commit()
    response = RedirectResponse(_safe_next(next), status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.admin_session_hours * 3600,
        path="/admin",
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
    )
    return response


@router.post("/logout")
def logout(
    request: Request,
    csrf_token: str = Form(""),
    ctx: AdminContext = Depends(current_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    verify_post(request, ctx, csrf_token)
    audit(db, ctx.user.id, "logout")
    db.commit()
    revoke_session(db, ctx.session)
    response = RedirectResponse("/admin/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE, path="/admin")
    return response


# --------------------------------------------------------------------------- appointments
@dataclass
class Filters:
    status: str = ""
    q: str = ""
    date_from: date | None = None
    date_to: date | None = None

    @classmethod
    def from_request(cls, request: Request) -> Filters:
        p = request.query_params
        status = p.get("status", "")

        def parse(v: str | None) -> date | None:
            try:
                return date.fromisoformat(v) if v else None
            except ValueError:
                return None

        return cls(
            status=status if status in APPOINTMENT_STATUSES else "",
            q=(p.get("q") or "").strip()[:80],
            date_from=parse(p.get("from")),
            date_to=parse(p.get("to")),
        )

    def apply(self, stmt):
        if self.status:
            stmt = stmt.where(Appointment.status == self.status)
        if self.date_from:
            stmt = stmt.where(Appointment.preferred_date >= self.date_from)
        if self.date_to:
            stmt = stmt.where(Appointment.preferred_date <= self.date_to)
        if self.q:
            digits = re.sub(r"\D", "", self.q)
            conds = [
                func.lower(Appointment.full_name).contains(self.q.lower(), autoescape=True),
                func.upper(Appointment.reference).contains(self.q.upper(), autoescape=True),
            ]
            if len(digits) >= 4:
                conds.append(Appointment.phone.contains(digits, autoescape=True))
            stmt = stmt.where(or_(*conds))
        return stmt

    def query_string(self) -> str:
        parts = []
        if self.status:
            parts.append(f"status={self.status}")
        if self.q:
            parts.append(f"q={quote(self.q)}")
        if self.date_from:
            parts.append(f"from={self.date_from.isoformat()}")
        if self.date_to:
            parts.append(f"to={self.date_to.isoformat()}")
        return "&".join(parts)


@router.get("/appointments", response_class=HTMLResponse)
def appointments(
    request: Request, page: int = 1, ctx: AdminContext = Depends(current_admin), db: Session = Depends(get_db)
) -> HTMLResponse:
    filters = Filters.from_request(request)
    page = max(page, 1)
    base = filters.apply(select(Appointment))
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(
        base.order_by(Appointment.created_at.desc()).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    ).all()
    counts = dict(db.execute(select(Appointment.status, func.count()).group_by(Appointment.status)).all())
    return _render(
        request,
        "admin/appointments.html",
        ctx,
        rows=rows,
        filters=filters,
        total=total,
        page=page,
        pages=max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1),
        counts=counts,
        today=today_ist(),
    )


def _get_appointment(db: Session, appointment_id: int) -> Appointment:
    appt = db.get(Appointment, appointment_id)
    if appt is None:
        raise HTTPException(status_code=404)
    return appt


@router.get("/appointments/{appointment_id}", response_class=HTMLResponse)
def appointment_detail(
    request: Request,
    appointment_id: int,
    updated: str = "",
    ctx: AdminContext = Depends(current_admin),
    db: Session = Depends(get_db),
):
    appt = _get_appointment(db, appointment_id)
    history = db.scalars(
        select(AuditLog)
        .where(AuditLog.target_type == "appointment", AuditLog.target_id == appt.id)
        .order_by(AuditLog.created_at.desc())
    ).all()
    return _render(
        request,
        "admin/appointment_detail.html",
        ctx,
        appt=appt,
        history=history,
        updated=updated,
        session=CLINIC.session(appt.preferred_session),
    )


@router.post("/appointments/{appointment_id}/status")
def appointment_status(
    request: Request,
    appointment_id: int,
    status: str = Form(...),
    csrf_token: str = Form(""),
    ctx: AdminContext = Depends(current_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    verify_post(request, ctx, csrf_token)
    appt = _get_appointment(db, appointment_id)
    if status not in appt.allowed_transitions:
        raise HTTPException(status_code=400, detail=f"Cannot change a {appt.status} request to {status}.")
    previous = appt.status
    appt.status = status
    audit(db, ctx.user.id, "status", "appointment", appt.id, f"{previous} → {status}")
    db.commit()
    return RedirectResponse(f"/admin/appointments/{appt.id}?updated=status", status_code=303)


@router.post("/appointments/{appointment_id}/notes")
def appointment_notes(
    request: Request,
    appointment_id: int,
    notes: str = Form(""),
    csrf_token: str = Form(""),
    ctx: AdminContext = Depends(current_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    verify_post(request, ctx, csrf_token)
    appt = _get_appointment(db, appointment_id)
    appt.admin_notes = notes.strip()[:2000] or None
    audit(db, ctx.user.id, "notes", "appointment", appt.id, "internal notes updated")
    db.commit()
    return RedirectResponse(f"/admin/appointments/{appt.id}?updated=notes", status_code=303)


def _csv_safe(value: Any) -> str:
    """Neutralise spreadsheet formula injection."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@router.get("/export.csv")
def export_csv(
    request: Request, ctx: AdminContext = Depends(require_admin_role), db: Session = Depends(get_db)
) -> StreamingResponse:
    filters = Filters.from_request(request)
    rows = db.scalars(filters.apply(select(Appointment)).order_by(Appointment.created_at.desc())).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Reference",
            "Received (IST)",
            "Name",
            "Mobile",
            "Email",
            "Preferred date",
            "Session",
            "Preferred time",
            "Status",
            "Message",
            "Internal notes",
        ]
    )
    for a in rows:
        writer.writerow(
            [
                _csv_safe(v)
                for v in (
                    a.reference,
                    format_datetime(a.created_at),
                    a.full_name,
                    a.phone,
                    a.email,
                    a.preferred_date.isoformat(),
                    a.preferred_session,
                    format_time(a.preferred_time),
                    a.status,
                    a.message,
                    a.admin_notes,
                )
            ]
        )
    audit(db, ctx.user.id, "export", "appointment", None, f"{len(rows)} rows")
    db.commit()
    filename = f"appointments-{today_ist().isoformat()}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --------------------------------------------------------------------------- messages
@router.get("/messages", response_class=HTMLResponse)
def messages(
    request: Request, show: str = "open", ctx: AdminContext = Depends(current_admin), db: Session = Depends(get_db)
) -> HTMLResponse:
    stmt = select(ContactMessage).order_by(ContactMessage.created_at.desc()).limit(200)
    if show == "open":
        stmt = stmt.where(ContactMessage.is_handled.is_(False))
    rows = db.scalars(stmt).all()
    return _render(request, "admin/messages.html", ctx, rows=rows, show=show)


@router.post("/messages/{message_id}/handled")
def message_handled(
    request: Request,
    message_id: int,
    csrf_token: str = Form(""),
    ctx: AdminContext = Depends(current_admin),
    db: Session = Depends(get_db),
):
    verify_post(request, ctx, csrf_token)
    msg = db.get(ContactMessage, message_id)
    if msg is None:
        raise HTTPException(status_code=404)
    msg.is_handled = not msg.is_handled
    msg.handled_at = utcnow() if msg.is_handled else None
    audit(db, ctx.user.id, "message", "contact", msg.id, "handled" if msg.is_handled else "reopened")
    db.commit()
    return RedirectResponse("/admin/messages", status_code=303)
