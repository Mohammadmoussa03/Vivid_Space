# Deploying Vivid Space on AWS

Two paths. **Option A** (single EC2 + RDS + SES) is the recommended launch setup —
cheapest AWS-native option, closest to the ScalaHosting guide. **Option B** (fully
managed/scalable) is where you graduate when traffic demands it; it's summarized at
the bottom. This file expands `DEPLOY_CHECKLIST.md` for AWS.

---

## Option A — Single EC2 + RDS (recommended)

Architecture:
```
Route 53 (DNS) → EC2 (Elastic IP)
                   ├─ nginx :443  (TLS via certbot/Let's Encrypt)
                   │     ├─ /      → React build (static)
                   │     └─ /api   → gunicorn 127.0.0.1:8001 (systemd)
                   └─ Redis :6379 (local, throttling cache)
                 RDS PostgreSQL (managed, private subnet)
                 S3 bucket (uploaded media — served directly to browsers)
                 SES (email — plugs into existing EMAIL_* env vars)
```
> Uploaded media (gallery images) lives in **S3**, not on the EC2 disk — durable,
> and it survives instance replacement. The app already supports this via
> `django-storages` (env-gated on `AWS_STORAGE_BUCKET_NAME`); nginx no longer
> proxies `/media`. Browsers load images straight from the S3 (or CloudFront) URL.
Recommended sizes for a marketing/booking site:
- **EC2**: `t3.small` (2 vCPU / 2 GB) to launch, `t3.medium` (4 GB) for comfort.
- **RDS**: `db.t4g.micro` PostgreSQL, 20 GB gp3, single-AZ (enable Multi-AZ later).

### 1. Network & instance
1. **VPC**: the default VPC is fine to start.
2. **Security groups**:
   - *EC2 SG*: inbound `443` and `80` from anywhere, `22` from **your IP only**.
   - *RDS SG*: inbound `5432` **only from the EC2 SG** (not public).
3. Launch an **EC2** instance (Ubuntu 22.04/24.04), attach the EC2 SG.
4. Allocate an **Elastic IP** and associate it (stable public IP for DNS).
5. **Route 53**: A record `your-domain.com` + `www` → the Elastic IP.

### 2. RDS PostgreSQL
1. Create an **RDS PostgreSQL** instance (`db.t4g.micro`, 20 GB gp3).
   - DB name `vivid_space`, master user `vivid`, a strong password.
   - Place it in the **same VPC**, **not publicly accessible**, attach the RDS SG.
2. Note the **endpoint** hostname — it becomes `POSTGRES_HOST` in `.env`.
   (No manual `CREATE DATABASE` needed; RDS creates it from the console field.)

### 2b. S3 media bucket + IAM (uploaded files)
1. Create an **S3 bucket** (e.g. `vivid-media-prod`) in your region.
2. **Public read** for served images (simplest; or skip and use CloudFront — see note):
   - Uncheck "Block *all* public access" (leave ACLs blocked; we use a bucket policy).
   - Add a bucket policy allowing public `s3:GetObject`:
     ```json
     {
       "Version": "2012-10-17",
       "Statement": [{
         "Sid": "PublicReadMedia",
         "Effect": "Allow",
         "Principal": "*",
         "Action": "s3:GetObject",
         "Resource": "arn:aws:s3:::vivid-media-prod/*"
       }]
     }
     ```
   - Add a **CORS** rule so the browser can load them cross-origin:
     ```json
     [{"AllowedOrigins":["https://your-domain.com"],"AllowedMethods":["GET"],"AllowedHeaders":["*"]}]
     ```
3. **IAM role for the EC2 instance** (preferred over access keys): create a role with
   an inline policy granting `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`,
   `s3:ListBucket` on `arn:aws:s3:::vivid-media-prod` (+ `/*`), and **attach it to the
   EC2 instance**. boto3 picks up the role automatically — no keys in `.env`.
   > No IAM role (e.g. non-AWS host)? Set `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`
   > in `.env` instead. On EC2, the role is the safer choice.
4. **Code support is already in place** — `django-storages[s3]` is in
   `requirements.txt`, and `settings.py` switches `STORAGES['default']` to S3 whenever
   `AWS_STORAGE_BUCKET_NAME` is set (dev stays on the local filesystem).
   > **Optional — CloudFront**: put a CloudFront distribution in front of the bucket
   > (origin access control, bucket stays private) and set `AWS_S3_CUSTOM_DOMAIN` to
   > the CloudFront domain for CDN caching + a custom media hostname.

### 3. SES (email) — replaces the Gmail SMTP
1. In **SES**, verify your **domain** (add the DKIM CNAME records to Route 53) and
   a `no-reply@your-domain.com` sender. DKIM = good deliverability.
2. **Request production access** — new SES accounts are in the **sandbox** and can
   only send to *verified* addresses until AWS approves you. Do this early.
3. Create **SMTP credentials** (SES → SMTP settings). They drop straight into the
   existing env vars — **no code change**:
   ```
   EMAIL_HOST=email-smtp.<region>.amazonaws.com
   EMAIL_PORT=587
   EMAIL_USE_TLS=True
   EMAIL_HOST_USER=<SES_SMTP_USERNAME>
   EMAIL_HOST_PASSWORD=<SES_SMTP_PASSWORD>
   DEFAULT_FROM_EMAIL=Vivid Space <no-reply@your-domain.com>
   ```

### 4. Provision the EC2 box
```bash
ssh -i your-key.pem ubuntu@<ELASTIC_IP>
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-venv python3-pip redis-server git nginx certbot python3-certbot-nginx postgresql-client
# Node to build the frontend (or build locally and upload dist/):
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash - && sudo apt install -y nodejs
sudo systemctl enable --now redis-server
```
> Postgres runs on RDS, so only the **client** is installed here, not the server.

### 5. Code, venv, .env
```bash
sudo adduser --system --group --home /opt/vivid vivid_app
cd /opt/vivid && sudo git clone <YOUR_REPO_URL> app
cd app/backend
sudo python3 -m venv venv
sudo ./venv/bin/pip install -r requirements.txt gunicorn
sudo cp .env.production.template .env && sudo nano .env
```
Fill `.env` (same as `DEPLOY_CHECKLIST.md`), AWS-specific values:
- `POSTGRES_HOST=<RDS endpoint>`, `POSTGRES_PASSWORD=<RDS master pw>`
- `REDIS_URL=redis://127.0.0.1:6379/1`
- `AWS_STORAGE_BUCKET_NAME=vivid-media-prod`, `AWS_S3_REGION_NAME=<region>`
  (credentials come from the instance IAM role — leave the key vars unset)
- `EMAIL_*` = the SES SMTP block above (rotated — never the leaked Gmail pw)
- `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`,
  `FRONTEND_URL` = your real https domain
```bash
sudo chown vivid_app:vivid_app .env && sudo chmod 600 .env
```

### 6. Migrate, static, admin
```bash
cd /opt/vivid/app/backend
sudo ./venv/bin/python manage.py check --deploy      # clean with DEBUG=False
sudo ./venv/bin/python manage.py migrate
sudo ./venv/bin/python manage.py collectstatic --noinput
sudo ./venv/bin/python manage.py createsuperuser     # real admin — NOT seed_demo
sudo chown -R vivid_app:vivid_app /opt/vivid
```

### 7. gunicorn systemd service
`/etc/systemd/system/vivid.service` (identical to the ScalaHosting guide):
```ini
[Unit]
Description=Vivid Space (gunicorn)
After=network.target redis-server.service

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
```bash
sudo systemctl daemon-reload && sudo systemctl enable --now vivid
sudo systemctl status vivid
```

### 8. Frontend build + nginx + TLS
```bash
cd /opt/vivid/app/frontend && sudo npm ci && sudo npm run build   # → dist/
```
`/etc/nginx/sites-available/vivid`:
```nginx
server {
    server_name your-domain.com www.your-domain.com;
    root /opt/vivid/app/frontend/dist;

    location /api   { proxy_pass http://127.0.0.1:8001; proxy_set_header Host $host; proxy_set_header X-Forwarded-Proto $scheme; }
    location /      { try_files $uri /index.html; }   # SPA fallback
    # No /media block — uploaded media is served directly from S3 (see step 2b).
}
```
```bash
sudo ln -s /etc/nginx/sites-available/vivid /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d your-domain.com -d www.your-domain.com   # TLS + auto-redirect
```
> `X-Forwarded-Proto` matters: Django already trusts it (`SECURE_PROXY_SSL_HEADER`)
> so it knows the request is https behind the proxy and sets Secure cookies.
> Same-origin means **no `VITE_API_URL`** — the SPA calls `/api` directly.

### 9. Cron (monthly free hours)
```bash
sudo crontab -u vivid_app -e
5 0 1 * * cd /opt/vivid/app/backend && ./venv/bin/python manage.py reset_monthly_hours
```

### 10. Verify (see DEPLOY_CHECKLIST §5–6)
- [ ] https loads, http→https redirect works.
- [ ] `vs_access`/`vs_refresh` cookies show Secure + HttpOnly + SameSite=Lax.
- [ ] HSTS/CSP/`X-Frame-Options: DENY` present.
- [ ] Real email sends via SES (and you're **out of the SES sandbox**).
- [ ] Upload a gallery image in the admin → it lands in the **S3 bucket** and the
      public URL renders on the site (confirms IAM role + bucket policy + CORS).
- [ ] Login lockout triggers (Redis throttling shared).
- [ ] Admin → Settings `notification_email` = real inbox.

### 11. Ops
- [ ] RDS **automated backups** on (7–14 day retention); test a restore.
- [ ] EBS snapshots or AMI of the EC2 box.
- [ ] CloudWatch alarms (CPU, RDS storage) + an uptime check.
- [ ] Weekly `manage.py flushexpiredtokens`.
- [ ] Keep SSH (`22`) locked to your IP.

### Rough monthly cost (on-demand, us-east-1 ballpark)
`t3.small` ~$15 + `db.t4g.micro` ~$13 + EBS/RDS storage ~$5 + S3 (a few GB) ~$1 +
SES pennies + Route 53 ~$0.50 ≈ **~$35–45/mo**. Reserved/Savings Plans cut EC2/RDS
30–50%. `t3.medium` instead of small adds ~$15.

---

## Option B — Fully managed / scalable (graduate later)

When you outgrow one box:
- **App**: containerize → **ECS Fargate** (or Elastic Beanstalk) behind an **ALB**
  (TLS via **ACM**, no certbot). Auto-scales horizontally; gunicorn stays the same.
- **DB**: **RDS** Multi-AZ (already there if you started with RDS).
- **Cache**: **ElastiCache Redis** instead of local Redis (required once >1 app node,
  so throttling/lockout is shared) — just point `REDIS_URL` at it.
- **Frontend**: **S3 + CloudFront** (CDN) instead of nginx-served static.
- **Media**: already on **S3** from Option A (durable + works across multiple nodes);
  add **CloudFront** (`AWS_S3_CUSTOM_DOMAIN`) for CDN caching if you haven't.
- **Email**: SES (unchanged).
- **Secrets**: **SSM Parameter Store / Secrets Manager** instead of a `.env` file.

The app is already stateless-friendly (cookie JWT, no server-side sessions), so the
main change to scale out is: shared Redis (ElastiCache) + shared media (S3). Nothing
in the auth model blocks horizontal scaling.

---

## Redeploying (Option A)
```bash
cd /opt/vivid/app && sudo git pull
cd backend && sudo ./venv/bin/pip install -r requirements.txt \
  && sudo ./venv/bin/python manage.py migrate \
  && sudo ./venv/bin/python manage.py collectstatic --noinput
cd ../frontend && sudo npm ci && sudo npm run build
sudo systemctl restart vivid
```
