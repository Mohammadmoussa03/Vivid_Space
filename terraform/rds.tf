resource "random_password" "db" {
  length  = 28
  special = true
  # keep to shell/URL-safe chars so it drops cleanly into POSTGRES_PASSWORD in .env
  override_special = "!#%*-_=+"
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.project_name}-db"
  subnet_ids = data.aws_subnets.default.ids
  tags       = { Name = "${var.project_name}-db" }
}

resource "aws_db_instance" "postgres" {
  identifier     = "${var.project_name}-pg"
  engine         = "postgres"
  engine_version = var.db_engine_version
  instance_class = var.db_instance_class

  allocated_storage = var.db_allocated_storage
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.db_name
  username = var.db_username
  password = random_password.db.result
  port     = 5432

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false
  multi_az               = var.db_multi_az

  backup_retention_period = 14
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:30-Mon:05:30"

  auto_minor_version_upgrade = true
  deletion_protection        = true
  skip_final_snapshot        = false
  final_snapshot_identifier  = "${var.project_name}-pg-final"

  tags = { Name = "${var.project_name}-pg" }
}
