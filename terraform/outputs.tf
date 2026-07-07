output "web_public_ip" {
  description = "Elastic IP — create/point your DNS A records here (apex + www)."
  value       = aws_eip.web.public_ip
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

output "next_steps" {
  description = "What to do after apply."
  value       = <<-EOT
    1. Point DNS A records for ${var.domain_name} and www at ${aws_eip.web.public_ip}
       (skipped automatically if manage_dns = true).
    2. Wait for cloud-init to finish, then SSH in and run certbot if it did not run
       automatically: sudo certbot --nginx -d ${var.domain_name} -d www.${var.domain_name}
    3. Create a real superuser:  cd /opt/vivid/app/backend && sudo -u vivid_app ./venv/bin/python manage.py createsuperuser
    4. If using SES: verify the domain, add DKIM records, request production access.
  EOT
}
