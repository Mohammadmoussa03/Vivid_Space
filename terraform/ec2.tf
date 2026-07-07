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

locals {
  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    repo_url           = var.repo_url
    domain_name        = var.domain_name
    certbot_email      = var.certbot_email
    secret_key         = random_password.secret_key.result
    db_host            = aws_db_instance.postgres.address
    db_name            = var.db_name
    db_user            = var.db_username
    db_password        = random_password.db.result
    media_bucket       = var.media_bucket_name
    aws_region         = var.aws_region
    email_host         = "email-smtp.${var.aws_region}.amazonaws.com"
    ses_smtp_username  = var.ses_smtp_username
    ses_smtp_password  = var.ses_smtp_password
    default_from_email = var.default_from_email != "" ? var.default_from_email : "Vivid Space <no-reply@${var.domain_name}>"
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

# Stable public IP for DNS.
resource "aws_eip" "web" {
  domain   = "vpc"
  instance = aws_instance.web.id
  tags     = { Name = "${var.project_name}-web" }
}
