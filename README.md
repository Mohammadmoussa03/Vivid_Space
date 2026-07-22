# Vivid Space

Booking and membership platform for a premium flexible-workspace center  a public
marketing site with member accounts, tour requests, and space booking, plus a full
admin panel to run the business behind it.

Live at **[vividspace.space](https://vividspace.space)**.

## What it does

**For visitors**  browse packages, workspaces, gallery and FAQs; request a tour;
register and verify an email address.

**For members**  sign in, see plan usage and upcoming reservations, book a space by
calendar slot, spend monthly free meeting-room hours, request booking or schedule
changes, and pay online (Whish) or at the center.

**For the owner** an admin panel covering users and memberships, reservations,
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
