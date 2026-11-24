"""Public website pages."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.content.clinic import CLINIC, DOCTOR
from app.content.services import SERVICES, get_service
from app.content.site import ANATOMY, FAQS, GALLERY, VALUES, VISIT_STEPS
from app.core.security import issue_form_token
from app.core.templating import templates
from app.core.timeutil import today_ist
from app.services import seo

router = APIRouter()


def render(
    request: Request, template: str, meta: dict[str, Any], *, page: str, status_code: int = 200, **context: Any
) -> HTMLResponse:
    return templates.TemplateResponse(
        request, template, {"meta": meta, "page": page, **context}, status_code=status_code
    )


def appointment_form_context(
    request: Request, values: dict | None = None, errors: dict | None = None
) -> dict[str, Any]:
    settings = request.app.state.settings
    today = today_ist()
    return {
        "form_token": issue_form_token(settings),
        "min_date": today.isoformat(),
        "max_date": (today + timedelta(days=settings.appointment_max_days_ahead)).isoformat(),
        "max_days": settings.appointment_max_days_ahead,
        "values": values or {},
        "errors": errors or {},
    }


def contact_form_context(request: Request, values: dict | None = None, errors: dict | None = None) -> dict[str, Any]:
    return {
        "contact_token": issue_form_token(request.app.state.settings),
        "contact_values": values or {},
        "contact_errors": errors or {},
    }


@router.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    s = request.app.state.settings
    meta = seo.page_meta(
        s,
        title=f"{CLINIC.name} | Orthopaedic Clinic in Perungudi, Chennai",
        description=(
            f"{CLINIC.name} in {CLINIC.locality}, {CLINIC.area}, Chennai — orthopaedic consultations "
            f"with {DOCTOR.name}, {DOCTOR.qualifications}. Care for bones, joints, spine and movement."
        ),
        path="/",
        jsonld=[seo.clinic_jsonld(s), seo.physician_jsonld(s)],
    )
    return render(
        request,
        "pages/home.html",
        meta,
        page="home",
        values_list=VALUES,
        anatomy=ANATOMY,
        faqs=FAQS[:5],
        gallery=GALLERY[:4],
        services=SERVICES,
    )


@router.get("/about", response_class=HTMLResponse)
def about(request: Request) -> HTMLResponse:
    s = request.app.state.settings
    meta = seo.page_meta(
        s,
        title="About the Clinic",
        description=(
            f"About {CLINIC.name}, an orthopaedic clinic in {CLINIC.area}, Chennai focused on clear "
            "communication and care for bones, joints, spine and movement."
        ),
        path="/about",
        breadcrumbs=[("About", "/about")],
        jsonld=[seo.clinic_jsonld(s)],
    )
    return render(request, "pages/about.html", meta, page="about", values_list=VALUES, steps=VISIT_STEPS)


@router.get("/doctor", response_class=HTMLResponse)
def doctor(request: Request) -> HTMLResponse:
    s = request.app.state.settings
    meta = seo.page_meta(
        s,
        title=f"{DOCTOR.name} — {DOCTOR.title}",
        description=(
            f"Meet {DOCTOR.name}, {DOCTOR.qualifications}, {DOCTOR.title} at {CLINIC.name}, {CLINIC.area}, Chennai."
        ),
        path="/doctor",
        breadcrumbs=[("Meet the Doctor", "/doctor")],
        jsonld=[seo.physician_jsonld(s)],
    )
    return render(request, "pages/doctor.html", meta, page="doctor")


@router.get("/services", response_class=HTMLResponse)
def services(request: Request) -> HTMLResponse:
    meta = seo.page_meta(
        request.app.state.settings,
        title="Orthopaedic Services",
        description=(
            f"Orthopaedic consultations at {CLINIC.name}, Perungudi — bone and fracture care, joint "
            "pain, knee and hip, back and spine, and sports injuries."
        ),
        path="/services",
        breadcrumbs=[("Services", "/services")],
    )
    return render(request, "pages/services.html", meta, page="services", services=SERVICES)


@router.get("/services/{slug}", response_class=HTMLResponse)
def service_detail(request: Request, slug: str) -> HTMLResponse:
    service = get_service(slug)
    if service is None:
        raise HTTPException(status_code=404)
    meta = seo.page_meta(
        request.app.state.settings,
        title=service.title,
        description=f"{service.summary} {CLINIC.name}, {CLINIC.area}, Chennai.",
        path=service.path,
        breadcrumbs=[("Services", "/services"), (service.title, service.path)],
    )
    others = [s for s in SERVICES if s.slug != slug][:3]
    regions = [r for r in ANATOMY if r.key in service.anatomy]
    return render(
        request, "pages/service_detail.html", meta, page="service", service=service, others=others, regions=regions
    )


@router.get("/gallery", response_class=HTMLResponse)
def gallery(request: Request) -> HTMLResponse:
    meta = seo.page_meta(
        request.app.state.settings,
        title="Clinic Gallery",
        description=f"Photographs of {CLINIC.name} in {CLINIC.locality}, {CLINIC.area}, Chennai.",
        path="/gallery",
        breadcrumbs=[("Gallery", "/gallery")],
    )
    return render(request, "pages/gallery.html", meta, page="gallery", gallery=GALLERY)


@router.get("/faq", response_class=HTMLResponse)
def faq(request: Request) -> HTMLResponse:
    meta = seo.page_meta(
        request.app.state.settings,
        title="Patient Information & FAQ",
        description=(
            f"Answers to common questions about appointments, consultation hours and visiting "
            f"{CLINIC.name} in Perungudi, Chennai."
        ),
        path="/faq",
        breadcrumbs=[("Patient Information", "/faq")],
        jsonld=[seo.faq_jsonld()],
    )
    return render(request, "pages/faq.html", meta, page="faq", faqs=FAQS, steps=VISIT_STEPS)


@router.get("/contact", response_class=HTMLResponse)
def contact(request: Request, sent: int = 0) -> HTMLResponse:
    s = request.app.state.settings
    meta = seo.page_meta(
        s,
        title="Contact Us",
        description=(
            f"Contact {CLINIC.name}, {CLINIC.locality}, {CLINIC.area}, Chennai. Call "
            f"{CLINIC.phone_display}. Consultations {CLINIC.sessions[0].display} and "
            f"{CLINIC.sessions[1].display}."
        ),
        path="/contact",
        breadcrumbs=[("Contact", "/contact")],
        jsonld=[seo.clinic_jsonld(s)],
    )
    return render(request, "pages/contact.html", meta, page="contact", sent=bool(sent), **contact_form_context(request))


@router.get("/appointment", response_class=HTMLResponse)
def appointment(request: Request) -> HTMLResponse:
    meta = seo.page_meta(
        request.app.state.settings,
        title="Request an Appointment",
        description=(
            f"Request an orthopaedic consultation with {DOCTOR.name} at {CLINIC.name}, Perungudi. "
            "The clinic team will call to confirm availability."
        ),
        path="/appointment",
        breadcrumbs=[("Appointment", "/appointment")],
    )
    return render(request, "pages/appointment.html", meta, page="appointment", **appointment_form_context(request))


@router.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request) -> HTMLResponse:
    meta = seo.page_meta(
        request.app.state.settings,
        title="Privacy Policy",
        description=f"How {CLINIC.name} collects, uses and protects information submitted on this website.",
        path="/privacy",
        breadcrumbs=[("Privacy Policy", "/privacy")],
    )
    return render(request, "pages/privacy.html", meta, page="legal")


@router.get("/terms", response_class=HTMLResponse)
def terms(request: Request) -> HTMLResponse:
    meta = seo.page_meta(
        request.app.state.settings,
        title="Terms and Conditions",
        description=f"Terms for using the {CLINIC.name} website.",
        path="/terms",
        breadcrumbs=[("Terms and Conditions", "/terms")],
    )
    return render(request, "pages/terms.html", meta, page="legal")
