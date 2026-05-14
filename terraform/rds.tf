# ---------------------------------------------------------------------------
# Gold tier — Amazon RDS for PostgreSQL 16
#
# Provisions the warehouse database, a Secrets Manager record holding the
# master credentials, and an AWS Glue JDBC Connection so the silver->gold
# PySpark job can reach the database from inside the VPC.
#
# Default-VPC strategy: per docs/architecture.md §12 Q4, V1 reuses the
# account's default VPC instead of standing up a dedicated one. The RDS
# instance lives in that VPC's default subnets behind a tight security-group
# allow-list (only the Glue JDBC SG can reach 5432).
#
# Glue Connection AZ trap: aws_glue_connection.physical_connection_requirements
# accepts a SINGLE subnet_id (unlike aws_lambda_function.vpc_config which
# accepts a list). If the chosen subnet lives in a different AZ than the RDS
# instance, the connection's "Test Connection" succeeds but real Glue job
# runs fail with cross-AZ ENI errors. We pin both the RDS availability zone
# and the Glue Connection subnet to the same AZ (the alphabetically-first
# default subnet's AZ) to avoid that trap.
# ---------------------------------------------------------------------------

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

locals {
  # sort() gives deterministic ordering across plans; tolist()[0] picks the
  # first default subnet ID. The RDS instance and the Glue Connection both
  # bind to this subnet's AZ so they are guaranteed co-located.
  glue_connection_subnet_id = sort(data.aws_subnets.default.ids)[0]
}

data "aws_subnet" "glue_connection" {
  id = local.glue_connection_subnet_id
}

# ---------------------------------------------------------------------------
# Security groups
# ---------------------------------------------------------------------------

resource "aws_security_group" "glue_jdbc" {
  name        = "${var.project_name}-glue-jdbc"
  description = "Source security group for Glue jobs and the DDL bootstrap Lambda to reach RDS."
  vpc_id      = data.aws_vpc.default.id

  # No ingress — this SG only serves as a source identifier for the RDS SG.
  egress {
    description = "Allow all egress so the Glue job can reach RDS, Secrets Manager, S3 VPC endpoints, and the public AWS APIs."
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

resource "aws_security_group" "rds" {
  name        = "${var.project_name}-rds"
  description = "RDS PostgreSQL — accepts traffic from the Glue JDBC SG only."
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "PostgreSQL from Glue / DDL Lambda."
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.glue_jdbc.id]
  }

  # No egress rules — Postgres is the responder, not a caller.

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# DB subnet group
# ---------------------------------------------------------------------------

resource "aws_db_subnet_group" "dw" {
  name        = "${var.project_name}-dw"
  description = "Subnet group for the warehouse RDS instance, spans the default VPC's default subnets."
  subnet_ids  = data.aws_subnets.default.ids

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# Master credentials — random password + Secrets Manager
# ---------------------------------------------------------------------------

resource "random_password" "rds_master" {
  length  = 32
  special = true
  # Exclude characters that confuse JDBC URLs (`/`, `@`, `:`) and psql
  # connection strings (` `, `"`).
  override_special = "!#$%&*()-_=+[]{}<>?"
}

resource "aws_secretsmanager_secret" "rds_master" {
  name        = "${var.project_name}-rds-master"
  description = "Master credentials for the ${var.project_name} warehouse RDS instance."

  # 0 lets terraform destroy + re-apply during dev recycle the secret name
  # without hitting the "scheduled for deletion" guard.
  recovery_window_in_days = 0

  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "rds_master" {
  secret_id = aws_secretsmanager_secret.rds_master.id

  # RDS-standard secret schema so a single GetSecretValue call gives consumers
  # everything they need to build a JDBC URL.
  secret_string = jsonencode({
    username = aws_db_instance.dw.username
    password = random_password.rds_master.result
    engine   = "postgres"
    host     = aws_db_instance.dw.address
    port     = aws_db_instance.dw.port
    dbname   = aws_db_instance.dw.db_name
  })
}

# ---------------------------------------------------------------------------
# RDS instance
# ---------------------------------------------------------------------------

resource "aws_db_instance" "dw" {
  identifier     = "${var.project_name}-dw"
  engine         = "postgres"
  engine_version = var.rds_engine_version
  instance_class = var.rds_instance_class

  allocated_storage = var.rds_allocated_storage
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.rds_database_name
  username = "dw_admin"
  password = random_password.rds_master.result

  db_subnet_group_name   = aws_db_subnet_group.dw.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  availability_zone      = data.aws_subnet.glue_connection.availability_zone

  publicly_accessible     = false
  multi_az                = false
  backup_retention_period = var.rds_backup_retention_days
  deletion_protection     = var.rds_deletion_protection
  skip_final_snapshot     = true
  apply_immediately       = true

  performance_insights_enabled = false
  copy_tags_to_snapshot        = true

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# Glue JDBC Connection
# ---------------------------------------------------------------------------

resource "aws_glue_connection" "dw" {
  name        = "${var.project_name}-dw"
  description = "JDBC connection from Glue jobs to the warehouse RDS instance."

  connection_type = "JDBC"

  connection_properties = {
    JDBC_CONNECTION_URL = "jdbc:postgresql://${aws_db_instance.dw.address}:${aws_db_instance.dw.port}/${aws_db_instance.dw.db_name}"
    USERNAME            = aws_db_instance.dw.username
    PASSWORD            = random_password.rds_master.result
    JDBC_ENFORCE_SSL    = "false"
  }

  physical_connection_requirements {
    availability_zone      = data.aws_subnet.glue_connection.availability_zone
    security_group_id_list = [aws_security_group.glue_jdbc.id]
    subnet_id              = data.aws_subnet.glue_connection.id
  }

  tags = local.common_tags
}
