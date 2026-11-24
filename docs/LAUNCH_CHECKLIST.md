# Launch checklist — SMAHIE ORTHO CARE

The site runs in **preview mode** until every item below is done: search engines
are told not to index it (`SITE_INDEXING=false`) and draft content shows amber
"awaiting clinic review" markers (`SHOW_REVIEW_MARKERS=true`).

All clinic facts live in `app/content/`. Anything still unconfirmed is `None` or
marked `TODO(clinic)` there — nothing has been invented.

## 1. Information the clinic must confirm

Edit `app/content/clinic.py`:

| Item | Field | Where it appears |
| --- | --- | --- |
| Full street address + PIN code | `street_address`, `postal_code` | Contact cards, footer, structured data |
| Google Maps link (real pin, not guessed) | `maps_url` | "Get directions" link |
| Consultation **days** and holidays | `consultation_days` | Hours card; enables opening hours in structured data |
| Clinic email | `email` | Footer, contact page |
| WhatsApp number (only if used) | `whatsapp_e164` | Not shown until set |
| Consultation fees (if they should be published) | `consultation_fee` | — |
| Current hospital affiliations | `hospital_affiliations` | Doctor page |
| Medical council registration number | `DOCTOR.registration_number` | Doctor page |
| Languages spoken | `DOCTOR.languages` | Doctor page |
| Experience/training summary (verified) | `DOCTOR.experience_summary` | Doctor page |
| Clinical areas of interest | `DOCTOR.areas_of_interest` | Doctor page |

## 2. Content approval

- [ ] `app/content/services.py` — review every service title and description. Remove any the clinic does not offer, correct wording, then set `approved=True`.
- [ ] `app/content/site.py` — confirm the FAQ answer "What should I bring?" (set `verified=True`), the care values and the anatomy guide text.
- [ ] Homepage, About and Doctor copy (in `app/templates/`) reviewed by the doctor.
- [ ] Privacy Policy and Terms reviewed by a qualified legal adviser for Indian law, including the Digital Personal Data Protection Act, 2023. Fill in the retention period, grievance contact and governing law (marked in amber on those pages).

## 3. Images

- [ ] Confirm written permission to publish the doctor's portrait (`assets/source/doctor-portrait.png`).
- [ ] Supply the **official logo** (ideally SVG). The current navy/gold emblem in `app/static/images/logo/` is an interim recolour of the supplied blue/green artwork, made to match the clinic signage.
- [ ] Supply real, approved photos of the exterior, reception, consultation room, waiting area and signage. Add them in `app/content/site.py` (`GALLERY`) after generating sizes (see README). Never use stock or AI-generated interiors to represent the clinic.
- [ ] Re-run `python scripts/build_images.py` after replacing source images.

## 4. Technical go-live

- [ ] `ENVIRONMENT=production`, strong `SECRET_KEY`, HTTPS `SITE_URL`, PostgreSQL `DATABASE_URL`.
- [ ] `alembic upgrade head`, then create the doctor's admin account and receptionist staff accounts (`python -m scripts.create_admin`).
- [ ] SMTP configured; submit a test request and confirm the clinic inbox receives the notification.
- [ ] Daily PostgreSQL backups configured **and a restore tested** (docs/DEPLOYMENT.md).
- [ ] Retention purge scheduled (`python -m scripts.purge_old_records --days N`) with N agreed by the clinic.
- [ ] Run Lighthouse on the live HTTPS site (mobile + desktop) and check Core Web Vitals.
- [ ] Submit the sitemap in Google Search Console; create/claim the Google Business Profile with the same name, address and phone.

## 5. Switch off preview mode

When sections 1–4 are complete:

```env
SHOW_REVIEW_MARKERS=false
SITE_INDEXING=true
```

Restart the service. `robots.txt` will then allow indexing (except `/admin` and `/api/`).
