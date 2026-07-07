# Deploying Vivid Space on a ScalaHosting SPanel VPS

Target: **Managed Cloud VPS (SPanel), Ubuntu, ~2 vCPU / 4 GB RAM**, root/SSH access.
This maps `DEPLOY_CHECKLIST.md` onto concrete commands.

Architecture on this box:
```
Internet → SPanel web server (LiteSpeed/Apache, :443, TLS)  ← SPanel manages domain + Let's Encrypt
                    │  reverse proxy
                    ▼
             gunicorn (Django API)  :8001  ← systemd service
             PostgreSQL             :5432  ← local
             Redis                  :6379  ← local (throttling cache)
             React build (static)          ← served by the web server / CDN
```
> Why proxy instead of a hand-installed nginx: SPanel already owns ports 80/443.
> Let it terminate TLS and forward to gunicorn on an internal port. If you're on an
> **unmanaged** VPS with no SPanel web stack, you can install nginx yourself instead
> (see "Alternative: raw nginx" at the bottom).

---

## 0. Provision & DNS
1. Order the Managed Cloud VPS, choose **Ubuntu**.
2. In SPanel/client area, point your domain's **A record** to the VPS IP
   (and `www` CNAME → root). Wait for DNS to resolve.
3. In SPanel, create the website/domain entry and issue a **Let's Encrypt SSL**
   for `your-domain.com` + `www`.
4. SSH in as root: `ssh root@<VPS_IP>`

## 1. System packages
```bash
apt update && apt upgrade -y
apt install -y python3-venv python3-pip postgresql postgresql-contrib redis-server git curl
# Node for building the frontend (or build locally and upload dist/):
curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt install -y nodejs
systemctl enable --now postgresql redis-server
```

## 2. PostgreSQL
```bash
sudo -u postgres psql <<'SQL'
CREATE ROLE vivid LOGIN PASSWORD 'CHANGE_ME_STRONG_DB_PW';
CREATE DATABASE vivid_space OWNER vivid;
\c vivid_space
GRANT ALL ON SCHEMA public TO vivid;
ALTER SCHEMA public OWNER TO vivid;
SQL
```

## 3. App user + code
```bash
adduser --system --group --home /opt/vivid vivid_app
cd /opt/vivid
git clone <YOUR_REPO_URL> app   # or scp/rsync the project up
cd app/backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/pip install gunicorn
```

## 4. Production .env
```bash
cp .env.production.template .env
nano .env      # fill every placeholder — see notes below
chown vivid_app:vivid_app .env && chmod 600 .env
```
Critical values (from `DEPLOY_CHECKLIST.md`):
- `DJANGO_DEBUG=False`, fresh `DJANGO_SECRET_KEY` (already in the template)
- `DJANGO_ALLOWED_HOSTS=your-domain.com,www.your-domain.com`
- `CSRF_TRUSTED_ORIGINS` / `CORS_ALLOWED_ORIGINS` = `https://your-domain.com,https://www.your-domain.com`
- `FRONTEND_URL=https://your-domain.com`
- `POSTGRES_PASSWORD` = the strong password from step 2, `POSTGRES_HOST=localhost`
- `REDIS_URL=redis://127.0.0.1:6379/1`
- **Rotated** SMTP creds (do NOT reuse the leaked dev Gmail app password)

## 5. Migrate, static, admin
```bash
cd /opt/vivid/app/backend
./venv/bin/python manage.py check --deploy      # should be clean with DEBUG=False
./venv/bin/python manage.py migrate             # includes token_blacklist tables
./venv/bin/python manage.py collectstatic --noinput
./venv/bin/python manage.py createsuperuser     # real admin — do NOT run seed_demo
chown -R vivid_app:vivid_app /opt/vivid
```

## 6. gunicorn as a systemd service
Create `/etc/systemd/system/vivid.service`:
```ini
[Unit]
Description=Vivid Space (gunicorn)
After=network.target postgresql.service redis-server.service

[Service]
User=vivid_app
Group=vivid_app
WorkingDirectory=/opt/vivid/app/backend
EnvironmentFile=/opt/vivid/app/backend/.env
ExecStart=/opt/vivid/app/backend/venv/bin/gunicorn config.wsgi:application \
    --bind 127.0.0.1:8001 --workers 3 --timeout 60
Restart=always

[Install]
WantedBy=multi-user.target
```
> `config.wsgi` matches the `config` Django project. Workers ≈ (2 × cores) + 1;
> 3 is right for 2 cores / 4 GB. Then:
```bash
systemctl daemon-reload && systemctl enable --now vivid
systemctl status vivid          # confirm it's running
curl -s localhost:8001/api/ -o /dev/null -w "%{http_code}\n"   # sanity check
```

## 7. Reverse proxy through SPanel
In **SPanel → your domain → Reverse Proxy** (or the Apache/LiteSpeed custom config),
forward the app so TLS terminates at SPanel and traffic reaches gunicorn:
- Proxy **`/api`** → `http://127.0.0.1:8001/api`
- Proxy **`/media`** → `http://127.0.0.1:8001/media` (uploaded files)
- Serve **`/`** (everything else) from the React build (next step)

If SPanel's UI can't express path-based proxying, drop an Apache vhost include:
```apache
ProxyPreserveHost On
ProxyPass        /api  http://127.0.0.1:8001/api
ProxyPassReverse /api  http://127.0.0.1:8001/api
ProxyPass        /media http://127.0.0.1:8001/media
ProxyPassReverse /media http://127.0.0.1:8001/media
# SPA fallback: serve index.html for client routes
```

## 8. Frontend build
Same-origin means **no `VITE_API_URL` needed** — the SPA calls `/api` and the proxy
handles it (exactly like the Vite dev proxy does locally).
```bash
cd /opt/vivid/app/frontend
npm ci && npm run build          # outputs dist/
```
Deploy `dist/` to your domain's web root (e.g. `/home/<spanel_user>/public_html`),
or point the vhost DocumentRoot at `/opt/vivid/app/frontend/dist`. Ensure the SPA
fallback rewrites unknown paths to `index.html`.
> Also remove the dev-only ngrok host from `frontend/vite.config.js` `allowedHosts`.

## 9. Monthly free-hours cron
```bash
crontab -u vivid_app -e
# 5 past midnight on the 1st:
5 0 1 * * cd /opt/vivid/app/backend && ./venv/bin/python manage.py reset_monthly_hours
```

## 10. Verify (with TLS live)
- [ ] `https://your-domain.com` loads; `http://` redirects to `https://`.
- [ ] Login works; in dev-tools the `vs_access`/`vs_refresh` cookies show
      **Secure + HttpOnly + SameSite=Lax**.
- [ ] HSTS + CSP + `X-Frame-Options: DENY` headers present.
- [ ] A booking/tour/password-reset sends real email to a real inbox.
- [ ] Hammer the login form → lockout triggers (proves Redis throttling is shared).
- [ ] Admin → Settings `notification_email` = your real inbox (not `owner@vividspace.co`).

## 11. Ops
- [ ] SPanel automated **backups** enabled (DB + files); test a restore.
- [ ] Enable SPanel firewall; only expose 80/443/SSH.
- [ ] Log rotation + an uptime check on `https://your-domain.com/api/`.
- [ ] Periodic `manage.py flushexpiredtokens` (weekly cron) to trim the blacklist.

---

## Alternative: raw nginx (unmanaged VPS, no SPanel web stack)
`apt install nginx certbot python3-certbot-nginx`, then an nginx server block that:
`location /api` and `location /media` → `proxy_pass http://127.0.0.1:8001;`,
`location /` → `root /opt/vivid/app/frontend/dist; try_files $uri /index.html;`,
and run `certbot --nginx -d your-domain.com -d www.your-domain.com` for TLS.

---

## Redeploying later
```bash
cd /opt/vivid/app && git pull
cd backend && ./venv/bin/pip install -r requirements.txt \
  && ./venv/bin/python manage.py migrate \
  && ./venv/bin/python manage.py collectstatic --noinput
cd ../frontend && npm ci && npm run build
systemctl restart vivid
```
