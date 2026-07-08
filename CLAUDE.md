# Vivid Space (Mindspace) — project guide

Premium flexible-workspace site: a public marketing/landing page with member auth, tour
booking, space booking, and a member dashboard — plus an admin panel to manage everything.
Django REST backend + React (Vite) frontend. UI is styled entirely with **inline styles**
driven by shared design tokens (there is no CSS framework and almost no CSS classes).

## Layout
```
backend/    Django 4.2 + DRF (Postgres). Apps: accounts, bookings, adminpanel, config
frontend/   React 19 + Vite 8, react-router 7, axios. Inline-styled, token-driven UI
```

## Run / build / test
- Frontend dev: `cd frontend && npm run dev` (Vite; proxies `/api` and `/media` → `http://localhost:8000`)
- Frontend build / lint: `npm run build` · `npm run lint` (oxlint). **Always `npm run build` after JS/JSX edits** — it's the fastest correctness check here.
- Backend: `cd backend && python manage.py runserver` (needs Postgres + `.env`; see `backend/README.md`)
- Backend tests: `python manage.py test --settings=config.test_settings`
- Seed demo data: `python manage.py seed_demo` (demo/admin credentials are in `backend/README.md`)
- The whole app is served through one origin via the Vite proxy (ngrok-friendly); API base is `/api` (override with `VITE_API_URL`).

## Frontend architecture
- **Routes** (`src/App.jsx`): only `/` (`pages/Landing.jsx`) and `/admin` (`pages/Admin.jsx`). Login/register and the member dashboard are **modals on the landing page**, not routes.
- **The whole app is essentially two big files**: `pages/Landing.jsx` (~1400 lines: nav, hero, all sections, auth/booking/dashboard modals) and `pages/Admin.jsx` (sidebar, top bar, every management table + modals). Components are defined inline within these files.
- `lib/ms.js` — **design tokens `MS` (colors/fonts), `TONES` (badge colors), and the `useVW()` hook** (viewport width, updates on resize). Also `buildCalendar`, `fmtDate`, `apiError`. This is the most-imported module.
- `lib/api.js` — axios instance (`withCredentials`). **JWTs live in httpOnly cookies** (`vs_access`/`vs_refresh`), set by the backend and never readable from JS. A request interceptor echoes Django's `csrftoken` cookie as the `X-CSRFToken` header on unsafe methods; a 401 triggers a one-shot cookie-based refresh. See `backend/accounts/authentication.py` (`CookieJWTAuthentication` + CSRF) and `accounts/cookies.py`.
- `lib/services.js` — every API call wrapped as a named function (`getSite`, `submitTour`, `createBooking`, `admin*`, …). Add new endpoints here.
- `context/AuthContext.jsx` — `useAuth()` → `{ user, isAuthed, role, loading, login, register, logout, requestReset, confirmReset, setUser }`. Tokens are **not** handled here (backend sets cookies); on mount it verifies the session via `GET /auth/me/` (`loading` gates that), and keeps a **non-sensitive** `vs_user` profile in `localStorage` for instant UI (not a credential). `safeUrl(v)` in `lib/ms.js` strips non-http(s) schemes before any href/iframe render.
- `lib/motion.jsx` — the **active motion system** (see below). Imported only by Landing.
- `index.css` — global stylesheet: font imports, CSS variables, `@keyframes`, a handful of utility classes (`.ms-input`, `.ms-submit`, `.ms-ghost`, `.ms-card`, `.ms-zoom`, `.adm-row`, `.adm-scroll`, `.ms-rail`, `.ms-hero`), `prefers-reduced-motion`, and mobile overflow guards. **This is where breakpoint/keyframe CSS goes** — inline styles can't do media queries or `:hover`.
- Legacy/unused scaffolding (not wired into the pages): `hooks/useReveal.js`, `lib/photos.js`, `lib/theme.js`, `components/Brand.jsx`, `components/Icon.jsx`. Don't build on these; the pages use `lib/motion.jsx` + inline styles.

### Styling conventions (important)
- **Inline styles only**, composed from `MS.*` tokens. No Tailwind, no CSS modules. Match the surrounding inline-style idiom.
- **Responsive = JS, not CSS media queries.** Read `const vw = useVW()` and branch (`vw < 768 ? … : …`). Existing breakpoints: nav hamburger `< 980`, admin sidebar drawer `< 900`, general mobile `< 768`, hero glass-card layout `< 1024`. Grids mostly use `repeat(auto-fit, minmax(…,1fr))` so they collapse without a breakpoint.
- Put only keyframes, `:hover`, `::placeholder`, media queries, and reduced-motion rules in `index.css`; keep layout inline.
- Desktop appearance must stay pixel-identical when adding mobile behavior — gate changes behind `vw` branches or lowered `clamp()` minimums (lowering a `clamp()` min only affects small screens).

### Motion system (`lib/motion.jsx`)
- One shared `IntersectionObserver` (`observe(el, cb)`, one-shot at ~15% visibility) reused by everything.
- `useReveal()` → `[ref, shown]`; `<Reveal>` (renders any tag directly — no wrapper div, safe inside grids); `<RevealCard>` (reveal + hover lift/scale/shadow composed into one transform so they don't fight); `<CountUp>` (ease-out count-up that starts when scrolled into view).
- Everything **defaults to visible** if the observer never runs, and respects `prefers-reduced-motion`.

## Backend architecture
- Apps: **`accounts`** (custom `User`, JWT auth, approval flow), **`bookings`** (core domain: plans, memberships, spaces, bookings, gallery, faqs, promo codes, tours, blocked slots, site content/settings), **`adminpanel`** (admin-only management endpoints), **`config`** (settings/urls).
- URLs: `/api/auth/` (accounts), `/api/admin/` (adminpanel, admin-only), `/api/` (bookings public + member). Django admin at `/django-admin/`.
- `AUTH_USER_MODEL = accounts.User`. Roles: `member` | `admin` (`user.is_staff_admin`/`role`); new members require `is_approved` (admin approves before login works — "pending" flow).
- DB: PostgreSQL. Media uploads served from `/media` in DEBUG.

### Security model (auth, CSRF, hardening) — read before touching auth
- **httpOnly-cookie JWT.** Access + refresh tokens ride in httpOnly/SameSite=Lax cookies (`vs_access`/`vs_refresh`), never in JSON bodies or JS-readable storage. `accounts/authentication.py` `CookieJWTAuthentication` is the **sole** `DEFAULT_AUTHENTICATION_CLASSES` — it reads the access cookie and **enforces CSRF** (double-submit `X-CSRFToken` vs `csrftoken` cookie) on unsafe methods. `accounts/cookies.py` sets/clears cookies consistently (login/refresh/logout must go through it).
- **Refresh rotation + blacklist.** `ROTATE_REFRESH_TOKENS` + `BLACKLIST_AFTER_ROTATION` + the `token_blacklist` app (needs `migrate`). Login sets cookies & returns only `{user, csrftoken}`; `CookieTokenRefreshView` rotates from the cookie (empty body); logout blacklists the refresh token. Access TTL is 15 min.
- **Revoke on password change.** Any password reset calls `accounts/tokens.blacklist_user_tokens(user)` so pre-reset tokens die. Do the same for any new credential-changing endpoint.
- **Anti-enumeration.** `POST /auth/register/` returns an identical generic response for new vs. existing emails (real owner gets an out-of-band email); the email field is declared explicitly to drop DRF's `UniqueValidator` 400. Don't reintroduce "email already exists" leaks on public endpoints.
- **Rate limiting / lockout.** DRF throttling (needs a shared cache — set `REDIS_URL` in prod; LocMem is per-process). Login has per-IP **and** per-account throttles (`accounts/throttling.py`); register/password-reset are scoped too.
- **Admin/URL safety.** Admin-set URL fields (`maps_url`, `hero_media_url`) are validated http(s)/relative-only via `bookings.serializers.validate_safe_url` (+ frontend `safeUrl`). Admin serializers are read-only where they should be; `AdminUserViewSet` create is intentionally `405` (users self-register).
- **UUIDs.** Every `User` has a non-sequential `uuid` (unique, exposed in user/admin payloads) for use as a public identifier; internal routing still uses the integer pk.
- **Config.** `DEBUG` **defaults to False** and the app refuses the insecure default `SECRET_KEY` in prod. Security headers/HSTS/secure-cookies/SSL-redirect engage when `DEBUG` is off; CSP is always sent (`config/middleware.py`, `CONTENT_SECURITY_POLICY`). Tunables (`THROTTLE_*`, `AUTH_COOKIE_*`, `CSRF_TRUSTED_ORIGINS`, `REDIS_URL`) are in `.env.example`.

### Key domain: free meeting-room hours (`bookings/models.py`, `serializers.py`, `views.py`)
Free hours are a **recurring monthly plan allowance**, not accrued/earned:
- `MembershipPlan.room_hours` = hours/month; `Membership.monthly_hours` = optional per-member admin override. `Membership.effective_hours` resolves override-else-plan.
- `room_hours_used` + `hours_period` (`YYYY-MM`) track usage; `sync_period()` lazily zeros usage on month rollover (no carryover). Also a `reset_monthly_hours` management command.
- `room_hours_left = max(0, effective_hours − room_hours_used)`.
- Consumed only when booking an **hourly** space with `Space.uses_free_hours=True`: `BookingCreateSerializer` validates balance, deducts atomically (`select_for_update`), marks booking `is_free`/`price=None`, and snapshots `Booking.free_hours_used`.
- Cancel → `_refund_free_hours()` (in `views.py`) returns exactly `free_hours_used` to the balance.

## Deployment — AWS via Terraform/OpenTofu (`terraform/`, Option A)
Infra-as-code for `AWS_DEPLOY.md` **Option A** (single EC2 + RDS + S3 + SES) lives in
`terraform/`. It provisions: default-VPC security groups (web: 80/443 open, 22 locked to
`admin_cidr`; RDS: 5432 from the web SG only), an EC2 box (Ubuntu 24.04, Elastic IP), RDS
PostgreSQL (`db.t4g.micro`, encrypted, private, deletion-protected), an S3 media bucket
(public-read + CORS), an IAM instance role (S3 RW + SES send + SSM), and optional Route 53
+ SES (DKIM). `user_data.sh.tftpl` is the cloud-init bootstrap that runs steps 4–9 of the
guide (clone repo, venv, `.env`, migrate, collectstatic, gunicorn systemd, frontend build,
nginx, cron).
- **Use OpenTofu, not Terraform.** HashiCorp's provider registry is **geo-blocked** in this
  region ("Content not available in your region"), so `terraform init` fails. OpenTofu
  (`tofu`, installed via winget `OpenTofu.Tofu`) uses `registry.opentofu.org` and works.
  Same HCL/state/providers. Binary lives under `~/AppData/Local/Microsoft/WinGet/Packages/`.
- **One toggle drives everything: `domain_name`.** Empty `""` = **test mode** (raw Elastic
  IP over HTTP: `DEBUG=True`, non-Secure cookies, `SECURE_SSL_REDIRECT=False`, console email
  backend, catch-all nginx `server_name`, no certbot/SES — a throwaway box, `DEBUG` exposes
  tracebacks). A real domain = **prod path** (`DEBUG=False`, Secure cookies, HSTS, certbot
  TLS, SES SMTP). Derived strings (`allowed_hosts`, `web_origins`, `server_name`,
  `email_backend`) are computed in `ec2.tf` `locals`; the EIP is allocated **before** the
  instance (separate `aws_eip` + `aws_eip_association`) so its address can be baked into
  `ALLOWED_HOSTS`/CSRF/CORS.
- **Config lives in `terraform/terraform.tfvars`** (gitignored — holds no secrets but is
  env-specific). `terraform.tfvars.example` is the template. State (`*.tfstate`) contains the
  generated DB password + `SECRET_KEY` in plaintext → **not** committed; move to an encrypted
  S3 backend before this is a shared/real env.
- **Email.** Test mode = `console.EmailBackend` (emails printed to `journalctl -u vivid`, not
  sent). Prod = `smtp.EmailBackend` → SES (`email-smtp.<region>.amazonaws.com:587`), creds
  from `ses_smtp_username/password` tfvars. Django auto-switches to SMTP once `EMAIL_HOST_USER`
  is set; an explicit `EMAIL_BACKEND` always wins (`settings.py`). SES starts **sandboxed** —
  request production access separately.
- **Console access without SSH:** the instance role has `AmazonSSMManagedInstanceCore`, so
  **EC2 → Connect → Session Manager** works with no key and no inbound 22 (SSM agent is
  preinstalled on the Ubuntu AMI). Prefer this over EC2 Instance Connect (which would need the
  SG opened to AWS's IP range).
- **Re-provisioning:** `user_data_replace_on_change = true`, so editing the bootstrap template
  replaces the instance on the next `tofu apply` (RDS/S3/EIP untouched, EIP address preserved).
  Pushing only app-code changes needs `tofu apply -replace=aws_instance.web` to re-run the
  clone/build.
- **Live test box (throwaway):** `eu-central-1`, `http://35.157.5.65`, bucket
  `vivid-space-test-f6225b03`, temp superuser `admin@vivid.test` (pw in `terraform/.admin_pw.tmp`,
  gitignored). Tear down with `tofu destroy` after flipping `deletion_protection = false` on RDS.
- **What's left for prod** (mostly tfvars flips, since the hardened path is already coded):
  own a domain → set `domain_name`/`manage_dns`/`manage_ses`; SES production access + a real
  superuser (delete the temp one); move state to encrypted S3; add CloudWatch alarms; consider
  IMDSv2 enforcement, a real `vivid-media-prod` bucket, and ElastiCache/Multi-AZ when scaling.

## Gotchas learned here
- **Deploy: `collectstatic` needs `STATIC_ROOT`.** `settings.py` sets `STATIC_ROOT`
  (`BASE_DIR/staticfiles`, env-overridable via `DJANGO_STATIC_ROOT`); without it `manage.py
  collectstatic` (guide step 6 / bootstrap) raises `ImproperlyConfigured`. nginx serves it via
  a `location /static/` alias and proxies `/django-admin` to gunicorn.
- **Deploy: `redis` is a runtime dependency.** It's in `requirements.txt`. Setting `REDIS_URL`
  switches Django's cache to the Redis backend, which imports the `redis` package — missing it
  makes **every** API request 500 (`No module named 'redis'`). The bootstrap installs
  `redis-server` (the daemon) separately.
- **Deploy: nginx must traverse `/opt/vivid`.** `adduser --home /opt/vivid` creates it `0750`,
  so nginx's `www-data` gets `13: Permission denied` (→ 500) serving `dist/`. The bootstrap
  `chmod 755 /opt/vivid` after creating the user.
- **Deploy: nginx upload cap.** `client_max_body_size 25m` in the server block — the default
  1 MB otherwise 413s gallery-image uploads before they reach Django.
- **Deploy: use `deploy.sh` for app-code updates.** `deploy.sh` (repo root) does the full
  update in order — pull → `pip install` → `migrate` → `collectstatic` → frontend `npm ci &&
  build` → restart gunicorn → reload nginx → health-check — and aborts loudly (`set -euo
  pipefail`) instead of masking a failed step. Run it on the box as root:
  `sudo bash /opt/vivid/app/deploy.sh` (paths overridable via `APP_DIR`/`APP_USER`/`SERVICE`/
  `BRANCH`). The layout it targets: repo at **`/opt/vivid/app`**, service user **`vivid_app`**,
  venv `backend/venv`, systemd unit **`vivid`** (gunicorn on `127.0.0.1:8001`).
- **Deploy: the frontend tree must be owned by `vivid_app`.** The cloud-init bootstrap runs
  `npm ci` as root, so `frontend/node_modules` ends up root-owned; a later `vite build` run as
  `vivid_app` then dies with `EACCES` writing `node_modules/.vite-temp/…` and the frontend
  **silently stays stale** (backend deploys fine, so it's easy to miss). `deploy.sh` fixes this
  by `chown -R vivid_app:vivid_app frontend` before building. Also: never pipe the build to
  `tail`/`head` in a `set -e` script — the pipe's exit status hides a build failure.
- **`*.sh` files are pinned to LF via `.gitattributes`** (repo has `autocrlf=true`); a CRLF
  shebang would be a "bad interpreter" error on the Linux box.
- **`backdrop-filter`/`filter`/`transform` create a containing block for `position:fixed` descendants.** The nav header uses `backdrop-filter` when solid, so any `position:fixed` child (e.g. the mobile menu panel) resolves against the header box, not the viewport — render such overlays as **siblings of the header**, not children.
- Page-level horizontal-overflow guard uses `overflow-x: clip` (not `hidden`) on `html, body` so it doesn't turn the root into a scroll container and break `position: sticky` headers/sidebars.
- Hero content is gated behind a `siteReady` flag so it doesn't flash the bundled fallback before `/site/` resolves (cache makes returning visits instant; `.finally` preserves the offline fallback).
- Hero section uses `.ms-hero` (`min-height: max(620px, 100svh)` + padding) so it grows with content; background media is `object-fit: cover` at all sizes (never `contain` — that letterboxes).
- Admin data tables: each header row and data row is its **own** grid. Every table defines one shared `const cols` template string used by both, with a **fixed-px Actions column** (so a variable number of action buttons can't reflow the other columns) and `minmax()` text columns; buttons are `flex:0 0 auto; white-space:nowrap`. Keep the `overflowX:auto` + inner `minWidth` wrapper.
- Vite/dev serves styles via JS — after edits, hard-refresh (Ctrl+F5) if viewing an already-open tab.
- **Auth tests:** DRF's `APIClient` disables CSRF by default, so `CookieJWTAuthentication.enforce_csrf` is a no-op there — to test CSRF rejection you must use `APIClient(enforce_csrf_checks=True)`. `config/test_settings.py` sets throttle rates absurdly high (throttle state persists in the process cache across test methods and would otherwise cause order-dependent 429s); the login view's **explicit** throttles still require those scope rates to exist, so don't remove them.
- The `backdrop-filter`/containing-block trap (see above) also applies to any new fixed overlay: mount it as a header **sibling**.
