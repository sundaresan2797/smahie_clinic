# Deployment guide — Ubuntu VPS

Two supported options:

- **A. Native install** (recommended for a single small VPS): PostgreSQL + Python venv + systemd + Nginx + Let's Encrypt.
- **B. Docker Compose**: PostgreSQL, migrations, app and Nginx containers.

Both assume Ubuntu 24.04 LTS, a domain whose DNS `A`/`AAAA` records point at the server, and SSH access.

---

## A. Native install

### 1. System packages and user

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip postgresql nginx certbot python3-certbot-nginx ufw
sudo ufw allow OpenSSH && sudo ufw allow 'Nginx Full' && sudo ufw enable
sudo adduser --system --group --home /srv/smahie smahie
```

### 2. Database

```bash
sudo -u postgres psql <<'SQL'
CREATE USER smahie WITH PASSWORD 'REPLACE_WITH_A_STRONG_PASSWORD';
CREATE DATABASE smahie OWNER smahie;
SQL
```

### 3. Application code

Copy the project to `/srv/smahie` (for example with `git clone` or `rsync`), then:

```bash
cd /srv/smahie
sudo -u smahie python3 -m venv .venv
sudo -u smahie .venv/bin/pip install -r requirements.txt
sudo -u smahie cp .env.example .env
sudo -u smahie nano .env      # see below
sudo chmod 600 .env
```

Minimum production `.env`:

```env
ENVIRONMENT=production
SECRET_KEY=<python3 -c "import secrets; print(secrets.token_urlsafe(48))">
DATABASE_URL=postgresql+psycopg://smahie:REPLACE_WITH_A_STRONG_PASSWORD@127.0.0.1:5432/smahie
SITE_URL=https://example.com
SITE_INDEXING=false          # true only after docs/LAUNCH_CHECKLIST.md is complete
SHOW_REVIEW_MARKERS=true
SMTP_HOST=...  SMTP_FROM=...  CLINIC_NOTIFICATION_EMAIL=...
```

The app refuses to start in production with a weak secret, a non-HTTPS site URL or SQLite.

### 4. Migrations and first admin

```bash
cd /srv/smahie
sudo -u smahie .venv/bin/alembic upgrade head
sudo -u smahie .venv/bin/python -m scripts.create_admin doctor@example.com
sudo -u smahie .venv/bin/python -m scripts.create_admin reception@example.com --role staff
```

(`alembic` and the scripts read `/srv/smahie/.env` automatically.)

### 5. Service

```bash
sudo cp deploy/systemd/smahie.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now smahie
sudo systemctl status smahie
curl -s http://127.0.0.1:8000/health    # {"status":"ok","database":"ok"}
```

Uvicorn runs 2 worker processes behind Nginx, trusts `X-Forwarded-*` only from
`127.0.0.1`, and has access logging disabled (admin search URLs can contain
patient names). Rate limits are stored in PostgreSQL, so they work across workers.

### 6. Nginx and HTTPS

```bash
sudo cp deploy/nginx/smahie-proxy.conf /etc/nginx/snippets/smahie-proxy.conf
sudo cp deploy/nginx/smahie.conf /etc/nginx/sites-available/smahie
sudo sed -i 's/example.com/YOUR-DOMAIN/g' /etc/nginx/sites-available/smahie
sudo ln -s /etc/nginx/sites-available/smahie /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
# First certificate: temporarily comment out the two 443 server blocks, reload, then:
sudo certbot certonly --nginx -d YOUR-DOMAIN -d www.YOUR-DOMAIN
# Restore the 443 blocks:
sudo nginx -t && sudo systemctl reload nginx
```

Certbot installs a renewal timer automatically (`systemctl list-timers | grep certbot`).
Nginx serves `/static/` directly with one-year caching (URLs are content-hashed),
gzip compression and an extra request-rate limit on form endpoints.

### 7. Backups (required before launch)

```bash
sudo mkdir -p /var/backups/smahie && sudo chown postgres /var/backups/smahie
sudo -u postgres crontab -e
# Daily at 02:30, keep 14 days:
30 2 * * * pg_dump -Fc smahie > /var/backups/smahie/smahie-$(date +\%F).dump && find /var/backups/smahie -name '*.dump' -mtime +14 -delete
```

Copy backups off the server (e.g. encrypted with `age`/`gpg` to object storage).
**Test a restore** into a scratch database:

```bash
sudo -u postgres createdb smahie_restore_test
sudo -u postgres pg_restore -d smahie_restore_test /var/backups/smahie/smahie-YYYY-MM-DD.dump
```

### 8. Data retention

Agree a retention period with the clinic, then schedule the purge (as the `smahie` user):

```bash
# Weekly, Sunday 03:00 — deletes requests/messages older than 365 days
0 3 * * 0 cd /srv/smahie && .venv/bin/python -m scripts.purge_old_records --days 365
```

### 9. Updating

```bash
cd /srv/smahie && sudo -u smahie git pull
sudo -u smahie .venv/bin/pip install -r requirements.txt
sudo -u smahie .venv/bin/alembic upgrade head
sudo systemctl restart smahie
```

### 10. Logs

```bash
journalctl -u smahie -f            # app: method, path, status, timing — no patient data
sudo tail -f /var/log/nginx/error.log
```

Nginx access logs contain IP addresses and URLs. Admin URLs can include search
terms, so keep log retention short (logrotate default: 14 days) or disable
`access_log` for `/admin` if required by the clinic's privacy policy.

---

## B. Docker Compose

```bash
sudo apt install -y docker.io docker-compose-v2
cp .env.example .env      # ENVIRONMENT=production, SECRET_KEY, SITE_URL (https), POSTGRES_PASSWORD
docker compose up -d --build
docker compose exec web python -m scripts.create_admin doctor@example.com
```

`migrate` runs `alembic upgrade head` once before `web` starts. Nginx listens on
port 80 inside the stack. For HTTPS either:

- put a TLS terminator in front (e.g. the host Nginx from option A proxying to port 80), or
- obtain certificates on the host with certbot, mount `/etc/letsencrypt` into the
  `nginx` service and add a 443 server block based on `deploy/nginx/smahie.conf`.

Backups: `docker compose exec db pg_dump -U smahie -Fc smahie > smahie-$(date +%F).dump`.

---

## Security notes

- Secrets only in `.env` (mode 600), never in git.
- Staff passwords: Argon2id, minimum 12 characters, created via the CLI only.
- Sessions: random tokens stored as SHA-256 hashes, 8-hour expiry, HttpOnly +
  SameSite=Lax + Secure cookies scoped to `/admin`; revoked on sign-out and password reset.
- CSRF: per-session tokens on all admin forms; signed, time-limited tokens plus
  Origin checks on public forms; honeypot and minimum fill time against bots.
- Strict Content-Security-Policy with per-request nonces (no inline scripts or
  styles without a nonce, no third-party origins), HSTS, frame denial.
- Patient data appears only in the authenticated admin area; there is no public
  API that returns records; email notifications contain no patient details.
- Review the privacy workflow against current Indian requirements (DPDP Act, 2023)
  with a qualified adviser before launch.
