"""Page metadata and JSON-LD structured data built only from verified facts."""

from __future__ import annotations

from typing import Any

from app.content.clinic import CLINIC, DOCTOR
from app.content.site import FAQS
from app.core.config import Settings

SITE_NAME = CLINIC.name
OG_IMAGE = "/static/images/og/social-preview.jpg"


def page_meta(
    settings: Settings,
    *,
    title: str,
    description: str,
    path: str,
    breadcrumbs: list[tuple[str, str]] | None = None,
    jsonld: list[dict[str, Any]] | None = None,
    noindex: bool = False,
    image: str = OG_IMAGE,
) -> dict[str, Any]:
    full_title = title if SITE_NAME in title else f"{title} | {SITE_NAME}"
    crumbs = [("Home", "/"), *breadcrumbs] if breadcrumbs else []
    blocks = list(jsonld or [])
    if crumbs:
        blocks.append(breadcrumb_jsonld(settings, crumbs))
    return {
        "title": full_title,
        "description": description,
        "canonical": settings.site_url + path,
        "image": settings.site_url + image,
        "image_alt": f"{SITE_NAME} — {CLINIC.tagline}",
        "breadcrumbs": crumbs,
        "jsonld": blocks,
        "robots": "noindex, nofollow" if (noindex or not settings.site_indexing) else "index, follow",
    }


def _address() -> dict[str, Any]:
    address: dict[str, Any] = {
        "@type": "PostalAddress",
        "addressLocality": f"{CLINIC.locality}, {CLINIC.area}, {CLINIC.city}",
        "addressRegion": CLINIC.state,
        "addressCountry": CLINIC.country_code,
    }
    if CLINIC.street_address:
        address["streetAddress"] = CLINIC.street_address
    if CLINIC.postal_code:
        address["postalCode"] = CLINIC.postal_code
    return address


def clinic_jsonld(settings: Settings) -> dict[str, Any]:
    base = settings.site_url
    data: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "MedicalClinic",
        "@id": f"{base}/#clinic",
        "name": CLINIC.name,
        "slogan": CLINIC.tagline,
        "url": f"{base}/",
        "logo": f"{base}/static/images/logo/emblem-512.png",
        "image": f"{base}{OG_IMAGE}",
        "telephone": CLINIC.phone_e164,
        "medicalSpecialty": "Musculoskeletal",
        "address": _address(),
        "employee": {"@id": f"{base}/doctor#physician"},
    }
    if CLINIC.maps_url:
        data["hasMap"] = CLINIC.maps_url
    # openingHoursSpecification is added only once consultation days are confirmed.
    return data


def physician_jsonld(settings: Settings) -> dict[str, Any]:
    base = settings.site_url
    return {
        "@context": "https://schema.org",
        "@type": "IndividualPhysician",
        "@id": f"{base}/doctor#physician",
        "name": DOCTOR.name,
        "description": f"{DOCTOR.title} — {DOCTOR.qualifications}",
        "medicalSpecialty": "Musculoskeletal",
        "url": f"{base}/doctor",
        "image": f"{base}/static/images/doctor/portrait-800.jpg",
        "telephone": CLINIC.phone_e164,
        "address": _address(),
        "practicesAt": {"@id": f"{base}/#clinic"},
    }


def breadcrumb_jsonld(settings: Settings, crumbs: list[tuple[str, str]]) -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": name, "item": settings.site_url + path}
            for i, (name, path) in enumerate(crumbs, start=1)
        ],
    }


def faq_jsonld() -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": f.question,
                "acceptedAnswer": {"@type": "Answer", "text": " ".join(f.answer)},
            }
            for f in FAQS
            if f.verified
        ],
    }
