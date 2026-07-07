########################################
# Core
########################################

variable "aws_region" {
  description = "AWS region to deploy into (must match your S3/SES setup)."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment tag (prod, staging, ...)."
  type        = string
  default     = "prod"
}

variable "project_name" {
  description = "Short name used to prefix resource names."
  type        = string
  default     = "vivid-space"
}

########################################
# DNS / domain
########################################

variable "domain_name" {
  description = "Apex domain, e.g. example.com. Used for ALLOWED_HOSTS, TLS, SES, and Route 53 records."
  type        = string
}

variable "manage_dns" {
  description = "Create Route 53 A records (apex + www) pointing at the Elastic IP. Requires the hosted zone to already exist."
  type        = bool
  default     = false
}

variable "route53_zone_id" {
  description = "Existing Route 53 hosted zone ID for domain_name (required when manage_dns = true)."
  type        = string
  default     = ""
}

variable "certbot_email" {
  description = "Email passed to certbot/Let's Encrypt for the TLS cert (used by the bootstrap script)."
  type        = string
  default     = ""
}

########################################
# Access / SSH
########################################

variable "admin_cidr" {
  description = "CIDR allowed to SSH (port 22). Set this to YOUR.IP/32 — never 0.0.0.0/0."
  type        = string
}

variable "ssh_public_key" {
  description = "SSH public key material (contents of your id_ed25519.pub) for the EC2 key pair."
  type        = string
}

########################################
# EC2
########################################

variable "instance_type" {
  description = "EC2 size. t3.small to launch, t3.medium for comfort."
  type        = string
  default     = "t3.small"
}

variable "root_volume_gb" {
  description = "EC2 root EBS volume size (GB)."
  type        = number
  default     = 30
}

variable "repo_url" {
  description = "Git URL of the application repo cloned onto the box by the bootstrap script."
  type        = string
}

########################################
# RDS
########################################

variable "db_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage" {
  description = "RDS storage in GB."
  type        = number
  default     = 20
}

variable "db_name" {
  description = "Initial PostgreSQL database name."
  type        = string
  default     = "vivid_space"
}

variable "db_username" {
  description = "RDS master username."
  type        = string
  default     = "vivid"
}

variable "db_multi_az" {
  description = "Enable RDS Multi-AZ (turn on later for HA)."
  type        = bool
  default     = false
}

variable "db_engine_version" {
  description = "PostgreSQL major/minor version."
  type        = string
  default     = "16"
}

########################################
# S3 media
########################################

variable "media_bucket_name" {
  description = "Globally-unique S3 bucket name for uploaded media (e.g. vivid-media-prod)."
  type        = string
}

########################################
# Email (SES)
########################################

variable "manage_ses" {
  description = "Create an SES domain identity + DKIM for the domain."
  type        = bool
  default     = false
}

########################################
# App env (non-secret; secrets are generated or come from SES/RDS)
########################################

variable "default_from_email" {
  description = "DEFAULT_FROM_EMAIL header for outgoing mail."
  type        = string
  default     = ""
}

variable "ses_smtp_username" {
  description = "SES SMTP username (create in SES console; leave blank to fill .env by hand later)."
  type        = string
  default     = ""
  sensitive   = true
}

variable "ses_smtp_password" {
  description = "SES SMTP password."
  type        = string
  default     = ""
  sensitive   = true
}
