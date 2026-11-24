# Deploying to Vercel

## How it runs on Vercel

- Vercel runs the FastAPI app (`app.main:app`, Python 3.12) as a serverless function.
- `/static/*` (CSS, JS, fonts, images) is served from Vercel's CDN with one-year caching.
- After installing dependencies, Vercel runs `python -m scripts.vercel_build`, which
  checks the configuration and applies database migrations — **on production deploys only**,
  so preview deploys never change the live database.
- Data is stored in a hosted **PostgreSQL** database (Neon, via Vercel Storage). Vercel's
  filesystem is temporary, so SQLite cannot be used; the app refuses to start in production
  without PostgreSQL rather than silently losing appointment requests.
- Functions run in Singapore (`sin1`, set in `vercel.json`), next to the database.

The app detects Vercel automatically: production mode, the `https://` site address,
real visitor IPs from Vercel's `X-Forwarded-For` header (for rate limiting), no in-process
connection pooling, and email notifications sent before the response (serverless functions
can be frozen once they reply).

> **Plan:** check Vercel's Terms of Service for whether a clinic website may use the free
> Hobby plan or needs Pro. Hobby keeps runtime logs for 1 hour only.

## One-time setup

### 1. Log in and link the project

```bash
cd /Users/sundareswaran/Desktop/Sundar_Project/Ortho_website
npx vercel login
npx vercel link            # create a new project, e.g. "smahie-ortho-care"
```

### 2. Create and connect the database

Vercel dashboard → your project → **Storage** → **Create Database** → **Neon (Postgres)**:

- Region: **Singapore (aws-ap-southeast-1)** — matches `sin1` in `vercel.json`.
  (If you choose another region, change `"regions"` in `vercel.json` to the nearest Vercel region.)
- Connect it to the project for **Production** and **Preview**.

This adds `DATABASE_URL` (pooled), `DATABASE_URL_UNPOOLED` and related variables to the project.

### 3. Environment variables

Project → **Settings → Environment Variables** (Production and Preview):

| Name | Value |
| --- | --- |
| `SECRET_KEY` | output of `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `SITE_INDEXING` | `false` until [LAUNCH_CHECKLIST.md](LAUNCH_CHECKLIST.md) is complete |
| `SHOW_REVIEW_MARKERS` | `true` until the clinic approves the content |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, `CLINIC_NOTIFICATION_EMAIL` | optional, for email alerts |

Not needed on Vercel: `ENVIRONMENT` (automatic) and `SITE_URL` (automatic from the
project's production domain; set it only if you want a specific custom domain used in
canonical links and the sitemap).

### 4. Deploy

```bash
npx vercel deploy --prod
```

The build log should end with `Database migrations applied (alembic upgrade head).`
Check `https://<your-project>.vercel.app/health` → `{"status":"ok","database":"ok"}`.

### 5. Create the first admin account

Copy the database connection string from Vercel → **Storage** → your database →
**Quickstart / .env.local** (`DATABASE_URL`), then on your Mac:

```bash
DATABASE_URL='postgres://...paste...' ./venv/bin/python -m scripts.create_admin doctor@example.com
DATABASE_URL='postgres://...paste...' ./venv/bin/python -m scripts.create_admin reception@example.com --role staff
```

Sign in at `https://<your-project>.vercel.app/admin`.

## Later

- **Updates:** `npx vercel deploy --prod` (migrations run automatically). Every
  `npx vercel deploy` without `--prod` creates a preview URL for checking changes first.
- **Custom domain:** Project → Settings → **Domains**. Vercel issues HTTPS automatically.
- **Backups:** Neon keeps point-in-time history (length depends on your Neon plan). For an
  independent copy, from your Mac:
  `pg_dump "$DATABASE_URL_UNPOOLED" -Fc > smahie-$(date +%F).dump`
- **Data retention:** run the purge from your Mac with the same `DATABASE_URL`:
  `DATABASE_URL='...' ./venv/bin/python -m scripts.purge_old_records --days 365`
- **Logs:** Project → **Logs** (method, path, status and timing only — no patient data).
