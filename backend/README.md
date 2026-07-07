# Vivid Space — Backend

Django REST Framework API (JWT auth via SimpleJWT) backing the Vivid Space
coworking frontend. PostgreSQL database.

## Stack
- Django 4.2 (LTS) + Django REST Framework
- SimpleJWT — access/refresh tokens delivered as **httpOnly cookies** (not JS-readable),
  with refresh **rotation + blacklist** (`token_blacklist` app)
- PostgreSQL (via `psycopg` 3)
- django-cors-headers (allows the Vite dev server)
- Console email backend by default (Book-a-Tour notifications print to the server
  console; set `EMAIL_BACKEND` + `EMAIL_*` in `.env` for real SMTP delivery)

## Setup

```powershell
cd backend
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # then edit values
```

Create the database and role (run as the postgres superuser):

```sql
CREATE ROLE vivid LOGIN PASSWORD 'vivid_dev_pw';
CREATE DATABASE vivid_space OWNER vivid;
-- On PostgreSQL 15+, also:
\c vivid_space
GRANT ALL ON SCHEMA public TO vivid;
ALTER SCHEMA public OWNER TO vivid;
```

Migrate, seed demo data, and run:

```powershell
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

The API serves at `http://localhost:8000/api/`.

## Demo accounts (from `seed_demo`)
| Role   | Email                   | Password   |
|--------|-------------------------|------------|
| Member | mohammad@loopstudio.co  | demo1234   |
| Admin  | admin@vividspace.co     | admin1234  |
| Pending signup | casey@northwind.io | demo1234 (awaiting approval) |

## Endpoints

### Auth (`/api/auth/`)
Tokens travel **only in httpOnly cookies** (`vs_access` / `vs_refresh`); the JSON
bodies never contain them, so nothing token-shaped is exposed to JavaScript. Unsafe
requests must echo the `csrftoken` cookie in the `X-CSRFToken` header.
- `POST register/` — create a pending member account (throttled)
- `POST login/` — sets the JWT cookies; returns `{ user, csrftoken }` (blocks unapproved members; throttled)
- `POST token/refresh/` — rotates using the `vs_refresh` cookie (no body); blacklists the old refresh token, sets fresh cookies
- `POST logout/` — blacklists the refresh token and clears the cookies (auth required)
- `GET csrf/` — primes the `csrftoken` cookie for the SPA
- `POST password-reset/` — always 200 (throttled)
- `GET/PATCH me/` — current user's profile

### Public (`/api/`, no auth)
- `GET packages/?category=<slug>` — visible, non-archived packages with nested `category`, `badge`, `images`, `description`, `details` (e.g. Private Office `offices` list)
- `GET categories/` — visible package categories (admin-managed, unlimited)
- `GET spaces/` — workspace list with full detail + computed `availability_status`; supports search/filter: `?type=<key>&min_capacity=N&max_price=N&amenity=wifi&duration=hourly&available_on=YYYY-MM-DD&status=available`
- `GET spaces/<key>/` — single workspace page (gallery, capacity, size, amenities, equipment, pricing, availability)
- `GET availability/?space=<key>&date=YYYY-MM-DD` — business hours, taken/blocked slots, and free hourly slots for the booking calendar
- `GET gallery/?category=<name>` — public gallery images (ordered)
- `GET faqs/` — published FAQs (ordered)
- `GET site/` — public site config: hero, services, contact (email/phones/address/maps), business hours
- `POST tours/` — Book-a-Tour submission (`{ first_name, last_name, email, phone, promo_code? }`); emails the owner and links the promo code to its sales rep

### Member (`/api/`, auth required)
- `GET overview/` — plan, usage stats, and upcoming bookings (free hours reset lazily on the 1st)
- `GET bookings/?when=upcoming|past|cancelled` — own bookings
- `POST bookings/` — create a booking (`{ space, date, duration, start_time?, hours?, attendees? }`); rejects overlaps/blocked slots, enforces capacity, deducts free meeting-room hours, emails the client a confirmation, and emails the owner a new-booking notification
- `POST bookings/{id}/cancel/` — cancel an upcoming booking (refunds any free hours used)

### Admin (`/api/admin/`, admin role required)
- `GET dashboard/` — KPIs, bookings chart, occupancy by space, recent activity
- `GET users/?status=pending|approved|members` — list users
- `POST users/{id}/approve/` · `/reject/` · `/set-active/` · `/reset-password/` · `/set-hours/`
- `GET clients/` — active members with package, perks, and remaining meeting-room hours
- `GET reservations/?filter=all|pending|confirmed|cancelled|past` — all bookings
- `POST reservations/{id}/approve/` · `/cancel/` · `/toggle-paid/`
- `PATCH reservations/{id}/` — edit unit/date/status/payment
- `GET/POST/PUT/PATCH/DELETE spaces/` · `POST spaces/{id}/toggle-active/` — full workspace fields (description, capacity, size, amenities, equipment, images, `uses_free_hours`, `admin_status`, `booking_enabled`)
- `GET/POST/PUT/PATCH/DELETE packages/?include_archived=1` · `POST packages/{id}/duplicate/` · `/toggle-archive/` — packages with FK `category`, `badge`, `images`, visibility/booking toggles
- `GET/POST/PUT/PATCH/DELETE categories/` — unlimited package categories
- `GET/POST/PUT/PATCH/DELETE gallery/` · `POST gallery/reorder/` (`[{id, order}, …]`) — gallery images
- `GET/POST/PUT/PATCH/DELETE faqs/` — FAQs
- `GET/POST/PUT/PATCH/DELETE promo-codes/` — referral codes with tour-attribution counts
- `GET/PATCH/DELETE tours/?status=new|contacted|scheduled|closed` — Book-a-Tour submissions
- `GET/POST/PUT/PATCH/DELETE blocked-slots/?space=<key>&upcoming=1` — calendar blocks
- `GET/PUT content/` — public-site hero, gallery, services
- `GET/PUT settings/` — booking rules, center details, structured `business_hours`, tour `notification_email`, and public contact info (`contact_email`, `phones`, `address`, `maps_url`)

Django admin site: `http://localhost:8000/django-admin/` (use the admin account).

## Monthly free hours & tests

Free meeting-room hours reset on the 1st of each month and don't carry over. This
happens lazily (`Membership.sync_period()` on any balance read); wire the sweep
command to Task Scheduler / cron for belt-and-braces:

```powershell
python manage.py reset_monthly_hours
```

Run the test suite on in-memory SQLite (no DB-creation privilege needed):

```powershell
python manage.py test --settings=config.test_settings
```

## Data model

Models live in `bookings/models.py` (plus the custom `accounts.User`).

- **`PackageCategory`** — admin-managed, unlimited package family. `name`, `slug`
  (auto), `description`, `order`, `is_visible`.
- **`MembershipPlan`** — a purchasable package. `category` (FK → `PackageCategory`),
  `description`, `price`/`price_label`/`period`, `room_hours` (monthly free
  meeting-room hours), `guest_passes`, `features` (list), `images` (URLs),
  `video_url`, `badge`, `details` (category-specific JSON — Private Office keeps its
  `offices` list + `common_benefits`), `featured`, `is_active`, `is_visible`,
  `booking_enabled`, `is_archived`, `order`.
- **`Membership`** — links a user to a plan. `room_hours_used`, `monthly_hours`
  (per-client override of the plan's free hours), `hours_period` (`YYYY-MM` stamp
  driving the lazy monthly reset), `custom_components` (line items for a Customized
  Package). Properties: `effective_hours`, `room_hours_left`; method `sync_period()`.
- **`Space`** — a bookable workspace. `key`, `name`, `description`, `capacity`,
  `size`, `amenities`/`equipment`/`images` (lists), `video_url`, `durations`,
  `day_price`, `units`, `rates`, `is_free`, `uses_free_hours`, `is_active`,
  `booking_enabled`, `admin_status`; method `availability_status(day)` →
  `available`/`fully_booked`/`blocked`/`temporarily_unavailable`.
- **`Booking`** — a reservation. `space`, `unit`, `date`, `duration`,
  `start_time`/`end_time`, `attendees`, `status`, `is_pending`, `is_free`,
  `free_hours_used` (for exact refund on cancel), `price`, `is_paid`.
- **`PromoCode`** — referral code. `code` (unique, upper-cased), `campaign`,
  `sales_rep`, `is_active`; `tour_count` property.
- **`TourRequest`** — Book-a-Tour submission. `first_name`/`last_name`, `email`,
  `phone`, `promo_code` (FK, resolved from the submitted text), `promo_code_text`
  (raw), `status` (`new`/`contacted`/`scheduled`/`closed`).
- **`BlockedSlot`** — admin calendar block. `space` (null = all spaces), `date`,
  `start_time`/`end_time` (null = full day), `reason`; `covers()` overlap helper.
- **`GalleryImage`** — public gallery image. `image` (URL), `caption`, `category`,
  `order`, `is_visible`.
- **`FAQ`** — public FAQ. `question`, `answer`, `order`, `is_visible`.
- **`SiteContent`** (singleton) — hero, services (gallery now lives in `GalleryImage`).
- **`AdminSettings`** (singleton) — booking rules, `center_name`, `opening_hours`
  (display string), `business_hours` (structured `{mon: {open, close, closed}, …}`),
  `notification_email` (tour alerts), and public contact info (`contact_email`,
  `phones`, `address`, `maps_url`).

## Changelog — coworking requirements alignment

Backend round aligning the API with the coworking-space requirements. All changes
are additive; migration `bookings/0003_*` covers the schema.

**New features**
- **Packages by type** — `MembershipPlan.category` + `details`; public
  `GET /api/packages/` (filterable by category). Customized packages configured
  per client via `Membership.custom_components`.
- **Free meeting-room hours** — booking a `uses_free_hours` space deducts hours
  (with a balance check); cancelling refunds them; hours reset on the 1st via lazy
  `sync_period()` plus the `reset_monthly_hours` command. Admins can override a
  member's monthly allotment or correct usage (`/users/{id}/set-hours/`).
- **Book a Tour** — `TourRequest` model, public `POST /api/tours/` that emails the
  owner (console backend by default) with the visitor's details + promo code, and
  admin management at `/api/admin/tours/`.
- **Promo codes** — `PromoCode` model, admin CRUD, tour attribution
  (`/api/admin/promo-codes/`, with `tour_count`).
- **Calendar** — double-booking/capacity validation on booking creation,
  `BlockedSlot` model + admin CRUD, structured `business_hours`, and public
  `GET /api/availability/`.
- **Admin member management** — client rows expose remaining hours + status; new
  `/users/{id}/` actions `set-active`, `reset-password`, `set-hours`.

**Files changed**
- `bookings/`: `models.py`, `serializers.py`, `views.py`, `urls.py`, `admin.py`
  (registered all models), `tests.py`, `management/commands/seed_demo.py`, and new
  `management/commands/reset_monthly_hours.py`.
- `adminpanel/`: `serializers.py`, `views.py`, `urls.py`.
- `config/`: `settings.py` (email config), new `test_settings.py` (SQLite for tests).
- `.env.example`: email settings (`EMAIL_BACKEND`, `EMAIL_*`, `DEFAULT_FROM_EMAIL`,
  `OWNER_EMAIL`).

**Not in this round** — the public React frontend still uses hardcoded data and a
mock booking modal; wiring it to these endpoints is the next round.

## Changelog — round 2: dynamic content & API-driven data

Backend round making all content admin-controlled and exposed through the API.
Migrations `bookings/0004_*` (additive fields + `PackageCategory`/`GalleryImage`/`FAQ`)
and `0005_*` (data-preserving `MembershipPlan.category` CharField → FK conversion).

**New features**
- **Dynamic packages** — `MembershipPlan.category` is now an FK to the new,
  unlimited `PackageCategory`; packages gained `description`, `images`, `video_url`,
  `badge`, `booking_enabled`, `is_visible`, `is_archived`. Admin category CRUD
  (`/api/admin/categories/`) plus package `duplicate/` and `toggle-archive/` actions;
  public `GET /api/categories/`.
- **Workspace pages** — `Space` gained `description`, `capacity`, `size`,
  `amenities`, `equipment`, `images`, `video_url`, `admin_status`, `booking_enabled`.
  `/api/spaces/` is now public with per-workspace detail, `availability_status`, and
  search/filter (`type`, `min_capacity`, `max_price`, `amenity`, `duration`,
  `available_on`, `status`).
- **Booking experience** — `Booking.attendees` (validated against space capacity) and
  emails on create: a confirmation to the client **and** a new-booking notification
  to the owner (`AdminSettings.notification_email` → `OWNER_EMAIL` → `DEFAULT_FROM_EMAIL`).
- **Gallery** — `GalleryImage` model, admin CRUD + `reorder/`, public `GET /api/gallery/`.
- **FAQ** — `FAQ` model, admin CRUD, public `GET /api/faqs/`.
- **Contact & site config** — contact fields on `AdminSettings` and a public
  `GET /api/site/` aggregator (hero, services, contact, business hours).

**Files changed** — `bookings/` (`models.py`, `serializers.py`, `views.py`, `urls.py`,
`admin.py`, `tests.py`, `seed_demo.py`, migrations `0004`/`0005`) and `adminpanel/`
(`serializers.py`, `views.py`, `urls.py`).

**Still deferred** — frontend wiring (being redesigned separately).

## Changelog — round 2.1: owner booking notification

- **Owner notified on every booking** — creating a booking now sends a second email
  to the owner ("New booking — {space} by {client}") with the client's name/email,
  space + unit, date, time, attendees, and payment status. The client still receives
  their own confirmation. Recipient resolves `AdminSettings.notification_email` →
  `OWNER_EMAIL` env → `DEFAULT_FROM_EMAIL`; sent `fail_silently` so mail issues never
  block a booking.
- **Files changed** — `bookings/views.py` (new `_notify_owner_of_booking`, called from
  `BookingViewSet.perform_create`) and `bookings/tests.py` (asserts both emails).

## Changelog — round 3: security hardening (httpOnly cookies, rotation, CSRF)

Moves JWT auth off JS-readable `localStorage` and closes the obvious attack surface.

**Auth transport**
- Access + refresh tokens are now set as **httpOnly, SameSite=Lax, Secure-in-prod
  cookies** (`vs_access` / `vs_refresh`) — unreadable from the console/XSS. Login/refresh
  responses no longer include tokens in their JSON body.
- New `accounts.authentication.CookieJWTAuthentication` reads the access cookie and
  enforces **CSRF** (double-submit `X-CSRFToken`) on unsafe methods; it's the sole
  `DEFAULT_AUTHENTICATION_CLASSES` entry. Helpers in `accounts/cookies.py`.
- **Refresh rotation + blacklist** (`ROTATE_REFRESH_TOKENS`, `BLACKLIST_AFTER_ROTATION`,
  `token_blacklist` app): every refresh invalidates the prior refresh token, and
  **logout blacklists it** — a real, revocable logout. Run `manage.py migrate` to create
  the blacklist tables. Optionally purge expired rows with `manage.py flushexpiredtokens`.

**Hardening**
- `DEBUG` now defaults to **False**; the app refuses to start in prod with the throwaway
  `SECRET_KEY`. Security headers/cookie flags (`SECURE_SSL_REDIRECT`, HSTS,
  `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, nosniff, `X_FRAME_OPTIONS=DENY`,
  referrer-policy) engage when `DEBUG` is off. `CSRF_TRUSTED_ORIGINS` + `SECURE_PROXY_SSL_HEADER`
  for the ngrok/prod origin.
- **Throttling** on `login` / `register` / `password-reset` (+ global anon/user rates) to
  blunt brute force and abuse.

**Files changed** — `config/settings.py`, new `accounts/authentication.py` &
`accounts/cookies.py`, `accounts/views.py`, `accounts/urls.py`, `accounts/tests.py`,
`.env.example`; frontend `src/lib/api.js` & `src/context/AuthContext.jsx`.

## Changelog — round 4: pentest remediation

Fixes from the internal penetration test, plus non-sequential user identifiers.

- **User UUIDs** — every `User` now has a unique, non-sequential `uuid`
  (`accounts/models.py`, migration `0002_user_uuid` backfills existing rows) exposed
  in the user/admin payloads as a safe public identifier.
- **Sessions revoked on password change** — `accounts/tokens.blacklist_user_tokens`
  is called on password reset (and admin-triggered reset), so tokens issued before a
  reset stop working.
- **No registration enumeration** — `POST /auth/register/` returns an identical
  generic response whether or not the email exists (the real owner gets an out-of-band
  email); no `UniqueValidator` 400 to probe with.
- **Login brute-force lockout** — per-IP **and** per-account login throttles
  (`accounts/throttling.py`); tune with `THROTTLE_LOGIN` / `THROTTLE_LOGIN_ACCOUNT`.
- **Admin password reset** now emails a one-time reset *link* instead of setting and
  returning a cleartext password.
- **Stored-XSS hardening** — admin URL fields (`maps_url`, `hero_media_url`) are
  validated to http(s)/relative only (`bookings.serializers.validate_safe_url`), with a
  matching `safeUrl()` guard on the frontend before any href/iframe render.
- **CSP header** on all Django responses (`config/middleware.py`,
  `CONTENT_SECURITY_POLICY` setting); **shorter 15-min access token**; **shared-cache**
  support for throttling via `REDIS_URL`; direct admin user-create now returns `405`
  instead of a 500.
