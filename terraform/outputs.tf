output "web_public_ip" {
  description = "Elastic IP — create/point your DNS A records here (apex + www)."
  value       = aws_eip.web.public_ip
}

output "site_url" {
  description = "Where to open the site once cloud-init finishes."
  value       = local.base_url
}

output "mode" {
  description = "Deployment mode."
  value       = local.test_mode ? "TEST (HTTP, DEBUG=True, no TLS/SES) — do not use for real launch" : "PRODUCTION"
}

output "ssh_command" {
  description = "SSH into the box."
  value       = "ssh ubuntu@${aws_eip.web.public_ip}"
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint (POSTGRES_HOST)."
  value       = aws_db_instance.postgres.address
}

output "db_password" {
  description = "Generated RDS master password."
  value       = random_password.db.result
  sensitive   = true
}

output "media_bucket" {
  description = "S3 media bucket name (AWS_STORAGE_BUCKET_NAME)."
  value       = aws_s3_bucket.media.bucket
}

output "ses_dkim_tokens" {
  description = "DKIM CNAME tokens to add to DNS (empty unless manage_ses = true)."
  value       = var.manage_ses ? aws_ses_domain_dkim.this[0].dkim_tokens : []
}

locals {
  steps_test = <<-EOT
    TEST MODE (HTTP, no domain):
    1. Wait ~3-6 min for cloud-init. Watch it:
         ssh ubuntu@${aws_eip.web.public_ip} 'sudo tail -f /var/log/vivid-bootstrap.log'
    2. Open ${local.base_url}  (plain HTTP — cookies are non-Secure in this mode).
    3. Create an admin:  cd /opt/vivid/app/backend && sudo -u vivid_app ./venv/bin/python manage.py createsuperuser
    4. Throwaway test box: DEBUG=True and no TLS. Tear down with `terraform destroy`
       (disable RDS deletion_protection first) and redeploy with a real domain for launch.
  EOT

  steps_prod = <<-EOT
    PRODUCTION:
    1. Point DNS A records for ${var.domain_name} and www at ${aws_eip.web.public_ip}
       (skipped automatically if manage_dns = true).
    2. Wait for cloud-init, then SSH in and run certbot if it did not run automatically:
         sudo certbot --nginx -d ${var.domain_name} -d www.${var.domain_name}
    3. Create a real superuser:  cd /opt/vivid/app/backend && sudo -u vivid_app ./venv/bin/python manage.py createsuperuser
    4. If using SES: verify the domain, add DKIM records, request production access.
  EOT
}

output "next_steps" {
  description = "What to do after apply."
  value       = local.test_mode ? local.steps_test : local.steps_prod
}
