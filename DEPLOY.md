# Deployment Guide — PDF Master

PDF Master is a Django app designed to run on **Render** (free tier) via Docker,
but it works on any host that can build the Dockerfile or run gunicorn.

## 1. Deploy on Render (recommended)

The repo ships `render.yaml`, so the fastest path is:

1. Push this repo to GitHub.
2. In Render: **New → Blueprint**, select the repo. Render reads `render.yaml`
   and creates the web service with `runtime: docker`.
3. Set the env vars listed below in the Render dashboard.
4. Deploy. Migrations run automatically at container start (see the Dockerfile
   `CMD`); `collectstatic` already ran at image build time.

> **Do not** set `buildCommand` / `startCommand` in the Render dashboard when
> using the Docker runtime — the Dockerfile owns both. See the comments at the
> top of `render.yaml` for why the Docker runtime is mandatory (OCR needs
> apt-installed Tesseract).

### Render env vars

| Key | Required | Notes |
| --- | --- | --- |
| `SECRET_KEY` | ✅ | Render can `generateValue: true` for you. |
| `DEBUG` | ✅ | `"False"` in production. |
| `ALLOWED_HOSTS` | ✅ | e.g. `.onrender.com,yourdomain.com`. |
| `SITE_URL` | ✅ | Canonical URL used by SEO tags, sitemap, robots.txt, e.g. `https://yourdomain.com`. |
| `TESSERACT_CMD` | ✅ | `/usr/bin/tesseract` (already set in render.yaml). |
| `CSRF_TRUSTED_ORIGINS` | ✅ | Your domain(s), comma-separated, with scheme. |
| `AI_API_KEY` | optional | Groq key enables AI tools; leave empty to disable. |
| `ADSENSE_CLIENT_ID` | optional | e.g. `ca-pub-1234...`; empty = no ad slots rendered. |
| `AD_SLOT_LEADERBOARD` / `AD_SLOT_INLINE` | optional | AdSense slot IDs. |
| `AD_GATE_ENABLED` / `AD_GATE_URL` / `AD_GATE_COOLDOWN_MIN` | optional | Ad-gate interstitial. Opens in a **new tab** (`window.open` + `noopener`) on "Download" and "Start OCR" clicks only; the current page is never redirected and the action still completes. Per-tab cooldown via `sessionStorage` (default 10 min). No-op when disabled or URL empty. |
| `CSP_ENABLED` | optional | Content-Security-Policy header (nonce-based inline scripts; ad origins only when `ADSENSE_CLIENT_ID` is set). Defaults to `True` - only disable for local debugging. |
| `RATE_LIMIT_*` | optional | Tune/disable the built-in rate limiter (see `core/middleware.py`). |

### Scheduled cleanup

Uploads are deleted automatically after processing, but as a safety net run
the cleanup command periodically (Render **Cron Job**, or a container with
`profiles: ["maintenance"]` in docker-compose):

```bash
python manage.py cleanup_temp            # removes media/temp files > 6h old
python manage.py cleanup_temp --age 1    # more aggressive
```

## 2. Deploy with Docker Compose (any VPS / local parity)

```bash
cp .env.example .env      # fill in SECRET_KEY, ALLOWED_HOSTS, SITE_URL, ...
docker compose up --build -d
# app:    http://localhost:10000
# admin:  docker compose run --rm web python manage.py createsuperuser
# cleanup: docker compose --profile maintenance run --rm web python manage.py cleanup_temp
```

SQLite and `media/` live in named volumes (`pdfmaster-data`, `pdfmaster-media`)
so data survives rebuilds.

## 3. Classic server (no Docker)

Needs Tesseract + fonts on the host:

```bash
sudo apt install tesseract-ocr tesseract-ocr-all poppler-utils ghostscript \
    fonts-noto-core fonts-noto-core-extra fonts-noto-extra \
    fonts-noto-naskh-arabic fonts-amiri fonts-dejavu-core libgl1 libglib2.0-0

python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:10000 --workers 2 --timeout 120
```

Put nginx/Caddy in front for TLS. `DEBUG=False` requires correct
`ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` and HTTPS
(`SECURE_SSL_REDIRECT` is enabled automatically when `DEBUG=False`).

## 4. Post-deploy checklist

- [ ] `GET /health/` returns 200.
- [ ] `GET /robots.txt` shows your `SITE_URL` sitemap line.
- [ ] `GET /sitemap.xml` lists all tool + static pages.
- [ ] `GET /ads.txt` (if using AdSense) shows your publisher ID.
- [ ] Run an OCR + compress round-trip on a real PDF.
- [ ] Confirm `SECRET_KEY` is set, `DEBUG=False`, and HTTPS redirects work.

## 5. Troubleshooting

| Symptom | Fix |
| --- | --- |
| OCR says "not configured" | You're not on the Docker runtime — see the note in `render.yaml`. |
| 502 on big files | Raise gunicorn `--timeout` (OCR of a 30-page PDF can exceed 120s) or lower `OCR_MAX_PAGES`. |
| CSRF errors | Add the exact origin to `CSRF_TRUSTED_ORIGINS` (scheme included). |
| Stale files in `media/temp` | Schedule `manage.py cleanup_temp`. |
| 429 "Too many requests" | Expected under load; tune `RATE_LIMIT_MAX_POSTS` / `RATE_LIMIT_MAX_UPLOADS`, or set `RATE_LIMIT_ENABLED=False` behind a WAF. |
