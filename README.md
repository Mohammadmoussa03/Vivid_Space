# Vivid Space

Booking and membership platform for a premium flexible-workspace center — a public
marketing site with member accounts, tour requests, and space booking, plus a full
admin panel to run the business behind it.

Live at **[vividspace.space](https://vividspace.space)**.

## What it does

**For visitors** — browse packages, workspaces, gallery and FAQs; request a tour;
register and verify an email address.

**For members** — sign in, see plan usage and upcoming reservations, book a space by
calendar slot, spend monthly free meeting-room hours, request booking or schedule
changes, and pay online (Whish) or at the center.

**For the owner** — an admin panel covering users and memberships, reservations,
packages and categories, workspaces, gallery, FAQs, promo codes, tour requests,
calendar blocks, site content, and business settings.

## Stack

| Layer    | Tech |
|----------|------|
| Backend  | Django 4.2 + Django REST Framework, SimpleJWT, PostgreSQL |
| Frontend | React 19, Vite, react-router 7, axios |
| Infra    | AWS (EC2 + RDS + S3), nginx, gunicorn, Let's Encrypt — provisioned with OpenTofu/Terraform |
| Email    | SMTP (Resend) in production; console backend in development |

## Layout

```
backend/     Django project — apps: accounts, bookings, adminpanel, config
frontend/    React SPA (Vite)
terraform/   Infrastructure as code for the AWS deployment
loadtest/    Load-testing scripts
deploy.sh    One-command update script for the production server
```

Each of `backend/`, `frontend/` and `terraform/` has its own README with the detail —
full API reference and data model in [`backend/README.md`](backend/README.md).

## Quick start

Requires Python 3.11+, Node 20+, and PostgreSQL.

**Backend**

```powershell
cd backend
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # then fill in the values
python manage.py migrate
python manage.py seed_demo  # demo accounts — see backend/README.md
python manage.py runserver
```

**Frontend** (in a second terminal)

```powershell
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. Vite proxies `/api` and `/media` to the Django server
on port 8000, so the whole app runs through a single origin.

## Tests and checks

```powershell
cd backend  && python manage.py test --settings=config.test_settings
cd frontend && npm run build   # fastest correctness check for the SPA
cd frontend && npm run lint
```

## Security

Auth is JWT delivered in **httpOnly cookies** — no tokens in `localStorage` or in any
JSON body. Refresh tokens rotate and are blacklisted on use and on logout; CSRF is
enforced with a double-submit token on every unsafe request; password changes revoke
existing sessions. Email verification gates member login, login is throttled per-IP
and per-account, and public endpoints are written not to leak whether an email is
registered. A CSP header is sent on every response.

`DEBUG` defaults to `False` and the app refuses to boot in production with the
placeholder `SECRET_KEY`.

## Deployment

Production runs on a single EC2 instance with RDS PostgreSQL and an S3 media bucket,
all defined in [`terraform/`](terraform/). See [`AWS_DEPLOY.md`](AWS_DEPLOY.md) for the
walkthrough and [`DEPLOY_CHECKLIST.md`](DEPLOY_CHECKLIST.md) for the go-live list.

To ship application changes to a running server:

```bash
sudo bash /opt/vivid/app/deploy.sh
```

It pulls, installs, migrates, collects static files, rebuilds the frontend, restarts
gunicorn, reloads nginx, and health-checks the site — aborting loudly on any failure.
