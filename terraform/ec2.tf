# Latest Ubuntu 24.04 LTS AMI (Canonical).
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_key_pair" "this" {
  key_name   = "${var.project_name}-key"
  public_key = var.ssh_public_key
}

# Django SECRET_KEY generated once and injected into .env.
resource "random_password" "secret_key" {
  length  = 64
  special = false
}

# Allocate the Elastic IP FIRST (independent of the instance) so its address is
# known before user_data is rendered — that lets us bake the real public IP into
# ALLOWED_HOSTS / CSRF / CORS for the no-domain HTTP test.
resource "aws_eip" "web" {
  domain = "vpc"
  tags   = { Name = "${var.project_name}-web" }
}

locals {
  # No domain => HTTP test mode on the raw Elastic IP.
  test_mode = var.domain_name == ""

  public_host = local.test_mode ? aws_eip.web.public_ip : var.domain_name
  scheme      = local.test_mode ? "http" : "https"
  base_url    = "${local.scheme}://${local.public_host}"

  allowed_hosts = local.test_mode ? "${aws_eip.web.public_ip},localhost,127.0.0.1" : "${var.domain_name},www.${var.domain_name}"

  web_origins = local.test_mode ? local.base_url : "https://${var.domain_name},https://www.${var.domain_name}"

  # nginx server_name: catch-all in test mode, real names otherwise.
  server_name = local.test_mode ? "_" : "${var.domain_name} www.${var.domain_name}"

  # Only run certbot when we have a real domain + email.
  certbot_email = local.test_mode ? "" : var.certbot_email

  # Console email backend in test mode (no SES/SMTP yet); real SMTP otherwise.
  email_backend = local.test_mode ? "django.core.mail.backends.console.EmailBackend" : "django.core.mail.backends.smtp.EmailBackend"

  from_email = var.default_from_email != "" ? var.default_from_email : (
    local.test_mode ? "Vivid Space <no-reply@example.com>" : "Vivid Space <no-reply@${var.domain_name}>"
  )

  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    repo_url           = var.repo_url
    django_debug       = local.test_mode ? "True" : "False"
    allowed_hosts      = local.allowed_hosts
    web_origins        = local.web_origins
    frontend_url       = local.base_url
    server_name        = local.server_name
    domain_name        = var.domain_name
    certbot_email      = local.certbot_email
    secret_key         = random_password.secret_key.result
    db_host            = aws_db_instance.postgres.address
    db_name            = var.db_name
    db_user            = var.db_username
    db_password        = random_password.db.result
    media_bucket       = var.media_bucket_name
    aws_region         = var.aws_region
    email_backend      = local.email_backend
    email_host         = "email-smtp.${var.aws_region}.amazonaws.com"
    ses_smtp_username  = var.ses_smtp_username
    ses_smtp_password  = var.ses_smtp_password
    default_from_email = local.from_email
  })
}

resource "aws_instance" "web" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = aws_key_pair.this.key_name
  vpc_security_group_ids = [aws_security_group.ec2.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  user_data              = local.user_data

  root_block_device {
    volume_size = var.root_volume_gb
    volume_type = "gp3"
    encrypted   = true
  }

  # Re-provision if the bootstrap script changes.
  user_data_replace_on_change = true

  tags       = { Name = "${var.project_name}-web" }
  depends_on = [aws_db_instance.postgres]
}

resource "aws_eip_association" "web" {
  instance_id   = aws_instance.web.id
  allocation_id = aws_eip.web.id
}
