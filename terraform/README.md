# Terraform — Vivid Space on AWS (Option A)

Provisions the **Option A** stack from [`../AWS_DEPLOY.md`](../AWS_DEPLOY.md): a single
EC2 web box (nginx + gunicorn + local Redis) behind an Elastic IP, managed RDS
PostgreSQL, an S3 media bucket, an IAM instance role, and optional SES + Route 53.

```
Route 53 (optional) → EIP → EC2 (nginx :443 → gunicorn :8001, Redis local)
                                  ├─ RDS PostgreSQL (private subnet, EC2-SG only)
                                  ├─ S3 media bucket (public-read + CORS)
                                  └─ IAM role (S3 + SES, no static keys)
```

The EC2 `user_data` script (`user_data.sh.tftpl`) runs steps 4–9 of the guide on first
boot: installs packages, clones the repo, builds the venv, writes `.env` (with the
Terraform-generated `SECRET_KEY`, RDS host/password, S3 bucket, SES SMTP), migrates,
collects static, builds the frontend, and wires up the gunicorn service, nginx, certbot
(best effort), and the monthly-hours cron.

## What it creates
| File | Resources |
|------|-----------|
| `network.tf` | default VPC lookup, EC2 SG (80/443 all, 22 admin-only), RDS SG (5432 from EC2 SG) |
| `rds.tf` | `db.t4g.micro` Postgres, gp3, encrypted, private, 14-day backups, generated password |
| `s3.tf` | media bucket, public-read policy, CORS for your domain |
| `iam.tf` | EC2 role + instance profile (S3 RW on the bucket, SES send) |
| `ec2.tf` | Ubuntu 24.04 instance, key pair, generated `SECRET_KEY`, Elastic IP, user_data |
| `route53.tf` | A records apex + www → EIP (when `manage_dns = true`) |
| `ses.tf` | SES domain identity + DKIM (when `manage_ses = true`) |

## Usage
```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars   # then edit
terraform init
terraform plan
terraform apply
```

Required variables (no defaults): `domain_name`, `admin_cidr`, `ssh_public_key`,
`repo_url`, `media_bucket_name`. See `terraform.tfvars.example`.

## After apply
1. **DNS** — point the apex + `www` A records at the `web_public_ip` output (done for you
   if `manage_dns = true` and you set `route53_zone_id`).
2. **TLS** — certbot runs in `user_data` but only succeeds once DNS resolves. If it was
   skipped: `ssh ubuntu@<ip>` then
   `sudo certbot --nginx -d <domain> -d www.<domain>`.
3. **Superuser** —
   `cd /opt/vivid/app/backend && sudo -u vivid_app ./venv/bin/python manage.py createsuperuser`.
4. **SES** — verify the domain, publish the DKIM records (`ses_dkim_tokens` output),
   create SMTP credentials, and **request production access** (accounts start in the
   sandbox). Put the SMTP creds in `ses_smtp_username`/`ses_smtp_password` or edit `.env`
   on the box.

Watch progress: `ssh ubuntu@<ip> 'sudo tail -f /var/log/vivid-bootstrap.log'`.

## Notes / caveats
- **State has secrets.** `terraform.tfstate` contains the generated DB password and
  `SECRET_KEY`. Use a remote backend with encryption (e.g. S3 + DynamoDB lock) for real
  use; the local state and `*.tfvars` are gitignored.
- RDS has `deletion_protection = true` and takes a final snapshot — to fully tear down,
  flip that off first (or `terraform destroy` will refuse the DB).
- `admin_cidr` must be a single `/32` (your IP). Do **not** open 22 to the world.
- Media is served publicly from S3 (per the guide). To use CloudFront/private bucket
  instead, front the bucket and set `AWS_S3_CUSTOM_DOMAIN` in `.env`.
- The bucket policy makes the media bucket public-read — expected for gallery images.
```
