"""Public pages, SEO endpoints, structured data and security headers."""

from __future__ import annotations

import json
import re

import pytest

from app.content.services import SERVICES
from tests.conftest import make_settings

PUBLIC_PAGES = [
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
    *[s.path for s in SERVICES],
]


@pytest.mark.parametrize("path", PUBLIC_PAGES)
def test_public_page_renders(client, path):
    r = client.get(path)
    assert r.status_code == 200
    html = r.text
    assert "SMAHIE" in html
    assert '<link rel="canonical" href="http://testserver' in html
    assert re.search(r"<title>[^<]+</title>", html)
    assert '<meta name="description"' in html
    assert html.count("<h1") == 1, "each page needs exactly one h1"


@pytest.mark.parametrize("path", PUBLIC_PAGES)
def test_every_inline_script_has_nonce(client, path):
    html = client.get(path).text
    for tag in re.findall(r"<script\b[^>]*>", html):
        assert "src=" in tag or "nonce=" in tag, f"inline script without nonce: {tag}"


def test_security_headers(client):
    r = client.get("/")
    csp = r.headers["content-security-policy"]
    assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert "'unsafe-inline'" not in csp
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in r.headers["permissions-policy"]
    assert "strict-transport-security" not in r.headers  # only in production


def test_nonce_changes_per_request(client):
    n1 = re.search(r"nonce-([^']+)'", client.get("/").headers["content-security-policy"]).group(1)
    n2 = re.search(r"nonce-([^']+)'", client.get("/").headers["content-security-policy"]).group(1)
    assert n1 != n2


def test_preview_mode_is_noindex(client):
    r = client.get("/")
    assert r.headers["x-robots-tag"] == "noindex, nofollow"
    assert '<meta name="robots" content="noindex, nofollow">' in r.text
    assert "Disallow: /" in client.get("/robots.txt").text


def test_launch_mode_allows_indexing(tmp_path):
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app(make_settings(tmp_path, site_indexing=True))
    with TestClient(app) as c:
        r = c.get("/")
        assert "x-robots-tag" not in r.headers
        assert '<meta name="robots" content="index, follow">' in r.text
        robots = c.get("/robots.txt").text
        assert "Disallow: /admin" in robots and "Sitemap: http://testserver/sitemap.xml" in robots
        assert c.get("/admin/login").headers["x-robots-tag"] == "noindex, nofollow"


def test_sitemap_lists_public_pages_only(client):
    xml = client.get("/sitemap.xml").text
    for path in PUBLIC_PAGES:
        assert f"<loc>http://testserver{path}</loc>" in xml
    assert "/admin" not in xml and "/api" not in xml


def _jsonld(html: str) -> list[dict]:
    return [json.loads(m) for m in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S)]


def test_home_structured_data_uses_only_verified_facts(client):
    blocks = _jsonld(client.get("/").text)
    clinic = next(b for b in blocks if b["@type"] == "MedicalClinic")
    assert clinic["name"] == "SMAHIE ORTHO CARE"
    assert clinic["telephone"] == "+919445489809"
    # Unconfirmed details must not be invented.
    assert "streetAddress" not in clinic["address"]
    assert "openingHoursSpecification" not in clinic
    assert "aggregateRating" not in clinic and "review" not in clinic
    physician = next(b for b in blocks if b["@type"] == "IndividualPhysician")
    assert physician["name"] == "Dr. Arun Selvan R"


def test_faq_structured_data_excludes_unverified_answers(client):
    faq = next(b for b in _jsonld(client.get("/faq").text) if b["@type"] == "FAQPage")
    questions = [q["name"] for q in faq["mainEntity"]]
    assert "How can I request an appointment?" in questions
    assert "What should I bring to my appointment?" not in questions


def test_breadcrumbs_on_inner_pages(client):
    blocks = _jsonld(client.get("/services/knee-and-hip-concerns").text)
    crumbs = next(b for b in blocks if b["@type"] == "BreadcrumbList")["itemListElement"]
    assert [c["name"] for c in crumbs] == ["Home", "Services", "Knee and Hip Concerns"]


def test_custom_404_page(client):
    r = client.get("/no-such-page")
    assert r.status_code == 404
    assert "Page not found" in r.text and "Back to home" in r.text


def test_unknown_service_is_404(client):
    assert client.get("/services/brain-surgery").status_code == 404


def test_api_404_is_json(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
    assert r.json()["ok"] is False


def test_static_assets_are_cache_busted(client):
    html = client.get("/").text
    assert re.search(r"/static/css/base\.css\?v=[0-9a-f]{10}", html)
    importmap = json.loads(re.search(r'<script type="importmap"[^>]*>(.*?)</script>', html, re.S).group(1))
    assert importmap["imports"]["/static/js/home.js"].startswith("/static/js/home.js?v=")


def test_review_markers_visible_in_preview(client):
    html = client.get("/services").text
    assert "awaiting clinic approval" in html


def test_review_markers_can_be_hidden(tmp_path):
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app(make_settings(tmp_path, show_review_markers=False))
    with TestClient(app) as c:
        assert "review-flag" not in c.get("/services").text


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "database": "ok"}


def test_favicon_and_manifest(client):
    assert client.get("/favicon.ico").status_code == 200
    manifest = client.get("/site.webmanifest")
    assert manifest.status_code == 200 and manifest.json()["name"] == "SMAHIE ORTHO CARE"


def test_no_public_api_docs(client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404
