# SMAHIE ORTHO CARE — website

Website and appointment-request system for **SMAHIE ORTHO CARE**, an orthopaedic
clinic in Thirumalai Nagar, Perungudi, Chennai, with **Dr. Arun Selvan R**,
MBBS, MS (Ortho), Consultant Orthopaedic Surgeon.

*Care That Keeps You Moving.* — Bone · Spine · Joint · Movement

> **Preview mode.** Indexing is off and draft content shows amber "awaiting clinic
> review" markers until the items in [docs/LAUNCH_CHECKLIST.md](docs/LAUNCH_CHECKLIST.md)
> are confirmed. No address, credentials, experience, ratings, outcomes or
> testimonials have been invented.

## Stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.11+, FastAPI, Jinja2, SQLAlchemy 2, Alembic, Pydantic v2, pydantic-settings |
| Database | SQLite (development/tests), PostgreSQL (production, psycopg 3) |
| Frontend | Semantic HTML, Bootstrap 5.3 (CSS + JS components), custom CSS design system, vanilla ES modules |
| Motion | GSAP 3 + ScrollTrigger + SplitText, Lenis smooth scrolling, SVG animation |
| Quality | Pytest (119 tests), Playwright (31 browser tests), Ruff |
| Ops | Uvicorn, Docker / Docker Compose, Nginx, systemd |

No React/Vue/SPA framework. No CDN: every script, font and image is served from
the site's own origin under a strict nonce-based Content-Security-Policy.

## Quick start (development)

```bash
python3 -m venv venv            # or reuse the existing ./venv (Python 3.11)
./venv/bin/pip install -r requirements-dev.txt
cp .env.example .env            # optional in development
./venv/bin/alembic upgrade head # creates data/smahie.db (SQLite)
./venv/bin/python -m scripts.create_admin you@example.com
./venv/bin/uvicorn app.main:app --reload
```

Open http://localhost:8000 — admin area at http://localhost:8000/admin.

`make dev`, `make test`, `make e2e`, `make lint` are shortcuts (see `Makefile`).

### Frontend dependencies

Browser builds of Bootstrap, GSAP, Lenis and the self-hosted fonts are already
copied into `app/static/vendor/` and `app/static/fonts/`, so Node is **not**
needed to run the site. To update them:

```bash
npm ci && npm run vendor        # versions pinned in package.json
```

### Images

Source images live in `assets/source/`. Regenerate the optimised AVIF/WebP/JPEG
sizes, favicons and the social-sharing image with:

```bash
./venv/bin/python scripts/build_images.py
```

## Tests

```bash
./venv/bin/python -m pytest -m "not browser"   # backend: routes, validation, auth, CSRF, migrations
./venv/bin/python -m pytest -m browser         # Playwright end-to-end (uses local Google Chrome)
PW_CHANNEL="" ./venv/bin/python -m pytest -m browser   # bundled Chromium (after `playwright install chromium`)
./venv/bin/ruff check . && ./venv/bin/ruff format --check .
```

Browser tests cover desktop/mobile navigation, the services dropdown, the
off-canvas menu (focus + Esc), skip link, no horizontal overflow at 320 px,
appointment form validation and submission, the anatomy guide's keyboard tabs,
gallery lightbox keyboard control, FAQ accordion, copy-to-clipboard, back-to-top,
reduced-motion behaviour, scroll reveals, no-JavaScript fallbacks and zero
console errors on every page.

## Project structure

```
app/
  main.py                 app factory, error pages
  core/                   config, database, security, middleware (CSP/headers), templating, rate limiting, IST time
  content/                clinic facts, services, FAQ, anatomy guide, gallery  ← edit content here
  models/                 Appointment, ContactMessage, AdminUser, AdminSession, AuditLog, RateLimitHit
  schemas/forms.py        Pydantic validation (Indian mobile numbers, dates, sessions, consent)
  services/               submissions (anti-spam, dedupe), auth, email, SEO/JSON-LD
  routers/                pages, forms (HTML + JSON API), admin, system (sitemap/robots/health)
  templates/              base, components/, home/ (homepage sections), pages/, admin/, errors/
  static/css/             variables · base · layout · components · sections · animations · admin
  static/js/              main · animations · scroll · navigation · forms · gallery · anatomy · home · utils
  static/images/          generated web images (logo, doctor, icons, og)
alembic/                  migrations
scripts/                  create_admin, purge_old_records, build_images, vendor.mjs
tests/                    pytest suite; tests/e2e/ Playwright suite
deploy/                   nginx and systemd configuration
docs/                     DEPLOYMENT.md, LAUNCH_CHECKLIST.md
```

Responsive rules live next to the component they modify (mobile-first), rather
than in one separate `responsive.css`, which keeps each component self-contained.

## Pages and routes

| Public | Admin (login required) | System |
| --- | --- | --- |
| `/` Home · `/about` · `/doctor` · `/services` · `/services/{slug}` · `/appointment` · `/gallery` · `/faq` · `/contact` · `/privacy` · `/terms` · custom 404/error pages | `/admin/appointments` (search, status/date filters) · `/admin/appointments/{id}` (status, internal notes, history) · `/admin/messages` · `/admin/export.csv` (admin role only) | `/sitemap.xml` · `/robots.txt` · `/health` · `/site.webmanifest` |

JSON endpoints: `POST /api/appointments`, `POST /api/contact`. There is no public
endpoint that returns patient data.

## Design system

- **Colours** (from the clinic signage): navy `#102F4A`, midnight `#071B2D`, gold `#C9A24F`,
  soft gold `#E5D4A7`, ivory `#F8F6F1`, medical blue `#3A779A`, charcoal `#273645`.
  Gold is decorative on light backgrounds; gold-toned *text* uses `#7E6020` for WCAG AA contrast.
- **Type**: Manrope (UI, headings, body) + Playfair Display italic as an editorial accent
  (e.g. "Live *Stronger.*"). Fluid sizes with `clamp()`; body text 17–18 px for older readers.
- **Shape & depth**: generous radii, soft navy-tinted shadows, arch-framed portraits, thin gold rules and rings.
- All tokens are CSS custom properties in `app/static/css/variables.css`.

## Animation architecture

`static/js/animations.js` is an attribute-driven engine, so templates never contain ad-hoc scripts:

| Attribute | Effect |
| --- | --- |
| `data-anim="up"` / `"fade"` | scroll reveal |
| `data-anim="stagger"` + `data-anim-child` | sequenced reveal of children |
| `data-anim="lines"` | SplitText masked line reveal for headings |
| `data-anim="mask"` | clip-path image reveal |
| `data-anim="rule"` / `"draw"` | gold rule growth / SVG line drawing |
| `data-parallax="0.25"` | subtle parallax (desktop only) |
| `data-magnetic` | magnetic button (fine pointers only) |

Homepage-only choreography (`home.js`, loaded on demand): short logo loader (first
visit per session), cinematic hero timeline, a navy intro panel that expands as you
scroll with word-by-word text reveal, one pinned four-step storytelling section on
desktop (a natural stacked timeline on mobile), and hero pointer depth.

Rules followed: transform/opacity only; everything inside `gsap.matchMedia()` with
desktop/mobile/reduced-motion branches and automatic cleanup; Lenis disabled on touch
devices and for reduced motion, and paused while menus/dialogs are open; reveals use
opacity (never `visibility`) so un-revealed content stays focusable and readable by
screen readers; content is never permanently hidden if scripts fail (4-second failsafe).

**Three.js was deliberately not used.** The interactive anatomy guide is a lightweight
SVG with an accessible tab interface; it works on every device, needs no WebGL, and
falls back to a fully readable list without JavaScript.

## Appointment workflow

1. Patient submits name, mobile, optional email, preferred date (next 90 days), session
   (morning/evening), optional preferred time and a short message, with privacy consent.
2. Server validates (Pydantic), normalises the mobile number to `+91XXXXXXXXXX`, checks the
   signed form token, honeypot, Origin, rate limits and duplicates, then stores it as **pending**.
3. The patient sees: *"Your appointment request has been received. Our clinic team will contact
   you to confirm the availability."* — never an automatic confirmation.
4. If SMTP is configured, the clinic receives a notification containing only a reference and a link.
5. Staff update the status (pending → confirmed → completed, or cancelled) in the admin area;
   every change is audit-logged.

## Content and placeholders

- Clinic and doctor facts: `app/content/clinic.py` (unconfirmed fields are `None`, marked `TODO(clinic)`).
- Services: `app/content/services.py` (all `approved=False` — proposed categories only).
- FAQ, care values, anatomy text, gallery: `app/content/site.py`.
- The logo in `app/static/images/logo/` is an interim navy/gold recolour of the supplied
  blue/green emblem, to match the signage; replace it with the official artwork.
- Gallery tiles for the exterior, reception, consultation room, waiting area and signage are
  clearly labelled placeholders until real photos are supplied.

## Deployment

- **Vercel:** [docs/DEPLOY_VERCEL.md](docs/DEPLOY_VERCEL.md) — serverless FastAPI + Neon PostgreSQL,
  configured in `pyproject.toml` (`[tool.vercel]`), `vercel.json` and `.vercelignore`.
- **Ubuntu VPS / Docker:** [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — PostgreSQL, systemd, Nginx,
  Let's Encrypt, backups, retention, and Docker Compose.

## Licences

Bootstrap and Lenis: MIT. GSAP: GreenSock standard "no charge" licence. Manrope and
Playfair Display: SIL Open Font License 1.1.
