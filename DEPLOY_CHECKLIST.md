# Vivid Space — Production Deploy Checklist

Work top to bottom. Don't skip the security section — several items only take
effect once `DEBUG=False`.

## 0. Secrets hygiene (do this first)
- [ ] **Rotate the Gmail app password** that was committed in the dev `.env`
      (revoke it at https://myaccount.google.com/apppasswords and issue a new one).
- [ ] Confirm the real `.env` is **git-ignored** and never committed.
- [ ] Move secrets into your host's secret store / env vars where possible.

## 1. Environment config
- [ ] Copy `backend/.env.production.template` → server `.env` and fill every placeholder.
- [ ] `DJANGO_DEBUG=False`
- [ ] Fresh `DJANGO_SECRET_KEY` (one is pre-generated in the template).
- [ ] `DJANGO_ALLOWED_HOSTS` = your real domain(s).
- [ ] `CSRF_TRUSTED_ORIGINS` + `CORS_ALLOWED_ORIGINS` = your real https origins.
- [ ] `FRONTEND_URL` = your public site (used in email links).
- [ ] Strong `POSTGRES_PASSWORD`; correct `POSTGRES_HOST`.
- [ ] `REDIS_URL` set (shared cache for rate limiting / brute-force lockout).

## 2. Database
- [ ] Provision production Postgres; create the `vivid` role + `vivid_space` DB.
- [ ] `python manage.py migrate` (includes the `token_blacklist` tables).
- [ ] **Do NOT run `seed_demo`** in prod — it creates demo users with fake emails.
- [ ] Create a real admin: `python manage.py createsuperuser` (or a first admin
      account through your own flow).
- [ ] Set up scheduled `python manage.py reset_monthly_hours` (cron / Task
      Scheduler) as a belt-and-braces monthly free-hours reset.
- [ ] Optional: periodic `python manage.py flushexpiredtokens` to purge the blacklist.

## 3. Backend runtime
- [ ] Run under a real WSGI server (gunicorn / uvicorn+gunicorn), **not** `runserver`.
- [ ] Put it behind nginx (or your platform's proxy) terminating TLS.
- [ ] Set `SECURE_PROXY_SSL_HEADER` awareness — the app already trusts
      `X-Forwarded-Proto`; make sure the proxy sets it.
- [ ] `python manage.py check --deploy` returns no warnings.
- [ ] `python manage.py collectstatic` if serving Django static via the proxy.
- [ ] Media uploads: serve `/media` via nginx or object storage (NOT Django/DEBUG).

## 4. Frontend
- [ ] `cd frontend && npm run build` → deploy the `dist/` output to your static host / CDN.
- [ ] If the API is on a different origin than the SPA, set `VITE_API_URL` at
      build time; otherwise keep same-origin and proxy `/api` + `/media` at the
      edge (nginx) the way Vite does in dev.
- [ ] Remove the dev-only ngrok host from `vite.config.js` `allowedHosts` if not needed.

## 5. TLS & security verification (with DEBUG=False live)
- [ ] Site loads over **https**; http redirects to https.
- [ ] Auth cookies (`vs_access`/`vs_refresh`) show **Secure + HttpOnly + SameSite=Lax**
      in browser dev tools.
- [ ] HSTS header present; `X-Frame-Options: DENY`; CSP header present.
- [ ] Login, logout, token refresh, and a CSRF-protected write all work end-to-end.
- [ ] Login brute-force lockout actually triggers (proves Redis throttling is shared).

## 6. Email
- [ ] Send a real test (booking / tour / password reset) to a real inbox.
- [ ] `DEFAULT_FROM_EMAIL` uses your domain; set up SPF/DKIM/DMARC on that domain
      so mail isn't marked spam (especially if moving off Gmail to SendGrid/SES).
- [ ] Confirm Admin → Settings `notification_email` points at a real owner inbox
      (the dev DB had `owner@vividspace.co`, which bounces).

## 7. Ops
- [ ] Backups for Postgres (automated + tested restore).
- [ ] Error monitoring / logging (e.g. Sentry) and uptime checks.
- [ ] `python manage.py test --settings=config.test_settings` green in CI before deploy.

---
Generated as a starting point — adapt to your actual host (Render / Fly / Railway /
VPS / etc.). The application code is production-grade; these are config + ops steps.
