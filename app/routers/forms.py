"""Appointment and contact submissions: HTML form fallbacks and JSON API."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.content.clinic import CLINIC
from app.core.database import get_db
from app.core.security import client_fingerprint, same_origin
from app.core.timeutil import format_date
from app.routers.pages import appointment_form_context, contact_form_context, render
from app.services import email_service, seo
from app.services.submissions import Outcome, submit_appointment, submit_contact

router = APIRouter()

_APPOINTMENT_FIELDS = (
    "full_name",
    "phone",
    "email",
    "preferred_date",
    "preferred_session",
    "preferred_time",
    "message",
    "consent",
)
_CONTACT_FIELDS = ("name", "phone", "email", "message", "consent")


async def _json_body(request: Request) -> dict[str, Any] | None:
    if "application/json" not in request.headers.get("content-type", ""):
        return None
    try:
        body = await request.json()
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


async def _deliver(tasks: BackgroundTasks, request: Request, fn: Callable[..., None], *args: Any) -> None:
    settings = request.app.state.settings
    if settings.serverless:
        # A serverless function may be frozen as soon as the response is sent,
        # so send the notification before responding.
        await run_in_threadpool(fn, settings, *args)
    else:
        tasks.add_task(fn, settings, *args)


async def _notify_appointment(tasks: BackgroundTasks, request: Request, outcome: Outcome) -> None:
    if outcome.kind != "created":
        return
    appt = outcome.record
    session = CLINIC.session(appt.preferred_session)
    await _deliver(
        tasks,
        request,
        email_service.notify_new_appointment,
        appt.reference,
        format_date(appt.preferred_date),
        session.label if session else "",
    )


async def _notify_contact(tasks: BackgroundTasks, request: Request, outcome: Outcome) -> None:
    if outcome.kind == "created":
        await _deliver(tasks, request, email_service.notify_new_contact, outcome.record.id)


def _submit_args(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    return {"fingerprint": client_fingerprint(request, settings), "origin_ok": same_origin(request, settings)}


# --------------------------------------------------------------------------- appointment
@router.post("/api/appointments")
async def api_appointment(request: Request, tasks: BackgroundTasks, db: Session = Depends(get_db)) -> JSONResponse:
    data = await _json_body(request)
    if data is None:
        return JSONResponse({"ok": False, "message": "Send the request as JSON."}, status_code=415)
    outcome = submit_appointment(db, request.app.state.settings, data, **_submit_args(request))
    await _notify_appointment(tasks, request, outcome)
    return JSONResponse(outcome.as_json(), status_code=outcome.status_code, background=tasks)


@router.post("/appointment", response_class=HTMLResponse)
async def form_appointment(request: Request, tasks: BackgroundTasks, db: Session = Depends(get_db)):
    form = await request.form()
    data = {k: form.get(k) for k in (*_APPOINTMENT_FIELDS, "form_token", "website")}
    outcome = submit_appointment(db, request.app.state.settings, data, **_submit_args(request))
    if outcome.ok:
        await _notify_appointment(tasks, request, outcome)
        return RedirectResponse("/appointment/received", status_code=303, background=tasks)
    values = {k: data.get(k) or "" for k in _APPOINTMENT_FIELDS}
    meta = seo.page_meta(
        request.app.state.settings,
        title="Request an Appointment",
        description="Request an orthopaedic consultation.",
        path="/appointment",
        breadcrumbs=[("Appointment", "/appointment")],
    )
    return render(
        request,
        "pages/appointment.html",
        meta,
        page="appointment",
        status_code=outcome.status_code,
        form_message=outcome.message,
        **appointment_form_context(request, values, outcome.errors),
    )


@router.get("/appointment/received", response_class=HTMLResponse)
def appointment_received(request: Request) -> HTMLResponse:
    meta = seo.page_meta(
        request.app.state.settings,
        title="Request Received",
        description="Your appointment request has been received.",
        path="/appointment/received",
        noindex=True,
    )
    return render(request, "pages/appointment_received.html", meta, page="appointment")


# --------------------------------------------------------------------------- contact
@router.post("/api/contact")
async def api_contact(request: Request, tasks: BackgroundTasks, db: Session = Depends(get_db)) -> JSONResponse:
    data = await _json_body(request)
    if data is None:
        return JSONResponse({"ok": False, "message": "Send the request as JSON."}, status_code=415)
    outcome = submit_contact(db, request.app.state.settings, data, **_submit_args(request))
    await _notify_contact(tasks, request, outcome)
    return JSONResponse(outcome.as_json(), status_code=outcome.status_code, background=tasks)


@router.post("/contact", response_class=HTMLResponse)
async def form_contact(request: Request, tasks: BackgroundTasks, db: Session = Depends(get_db)):
    form = await request.form()
    data = {k: form.get(k) for k in (*_CONTACT_FIELDS, "form_token", "website")}
    outcome = submit_contact(db, request.app.state.settings, data, **_submit_args(request))
    if outcome.ok:
        await _notify_contact(tasks, request, outcome)
        return RedirectResponse("/contact?sent=1#contact-form", status_code=303, background=tasks)
    values = {k: data.get(k) or "" for k in _CONTACT_FIELDS}
    s = request.app.state.settings
    meta = seo.page_meta(
        s,
        title="Contact Us",
        description=f"Contact {CLINIC.name}.",
        path="/contact",
        breadcrumbs=[("Contact", "/contact")],
    )
    return render(
        request,
        "pages/contact.html",
        meta,
        page="contact",
        sent=False,
        status_code=outcome.status_code,
        contact_message=outcome.message,
        **contact_form_context(request, values, outcome.errors),
    )
