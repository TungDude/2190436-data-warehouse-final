# ---------------------------------------------------------------------------
# DDL bootstrap Lambda
#
# One-shot function that applies dw_schema.sql followed by dw_seed.sql to the
# warehouse RDS instance. Invoked by aws_lambda_invocation at apply-time so
# `terraform apply` is the full provisioning command — no operator-laptop
# psql step required. Re-runs are idempotent because both SQL files use
# CREATE TABLE IF NOT EXISTS + INSERT ... ON CONFLICT DO NOTHING.
#
# Driver: psycopg[binary] v3 (per user decision and the plan's Track 3 step
# 1). Bundled via a Lambda Layer built by `pip install --platform
# manylinux2014_x86_64 --only-binary=:all:` so the wheel is Lambda-compatible
# even when the operator's host is a different OS (e.g. macOS, NixOS).
# ---------------------------------------------------------------------------

locals {
  dw_bootstrap_src_root   = "${path.module}/../src/lambda/dw_bootstrap"
  dw_bootstrap_layer_root = "${path.module}/.terraform/dw_bootstrap_layer"
  schema_sql_path         = "${path.module}/../sql/dw_schema.sql"
  seed_sql_path           = "${path.module}/../sql/dw_seed.sql"
}

# ---------------------------------------------------------------------------
# SQL file uploads — Lambda reads them out of S3 at runtime
# ---------------------------------------------------------------------------

resource "aws_s3_object" "dw_schema_sql" {
  bucket       = aws_s3_bucket.raw.id
  key          = "sql/dw_schema.sql"
  source       = local.schema_sql_path
  etag         = filemd5(local.schema_sql_path)
  content_type = "application/sql"

  tags = local.common_tags
}

resource "aws_s3_object" "dw_seed_sql" {
  bucket       = aws_s3_bucket.raw.id
  key          = "sql/dw_seed.sql"
  source       = local.seed_sql_path
  etag         = filemd5(local.seed_sql_path)
  content_type = "application/sql"

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# Lambda layer with psycopg[binary]
#
# The local-exec wheel build only runs when requirements.txt changes (its
# md5 is the trigger). The resulting build/python/ directory is what
# archive_file zips up; the dest is .terraform/dw_bootstrap_layer/ which we
# treat as ephemeral (gitignored).
# ---------------------------------------------------------------------------

resource "null_resource" "build_dw_bootstrap_layer" {
  triggers = {
    requirements_md5 = filemd5("${local.dw_bootstrap_src_root}/requirements.txt")
  }

  provisioner "local-exec" {
    interpreter = ["python", "-c"]
    command     = <<-EOT
import shutil
import subprocess
import sys
from pathlib import Path

layer_root = Path(${jsonencode(local.dw_bootstrap_layer_root)})
target = layer_root / "python"
requirements = Path(${jsonencode("${local.dw_bootstrap_src_root}/requirements.txt")})

shutil.rmtree(layer_root, ignore_errors=True)
target.mkdir(parents=True, exist_ok=True)

subprocess.check_call([
    sys.executable, "-m", "pip", "install",
    "--target", str(target),
    "--platform", "manylinux2014_x86_64",
    "--python-version", "3.12",
    "--only-binary=:all:",
    "--no-compile",
    "--upgrade",
    "-r", str(requirements),
])
    EOT
  }
}

data "archive_file" "dw_bootstrap_layer" {
  depends_on = [null_resource.build_dw_bootstrap_layer]

  type        = "zip"
  source_dir  = local.dw_bootstrap_layer_root
  output_path = "${path.module}/.terraform/dw_bootstrap_layer.zip"
  excludes = [
    "**/__pycache__",
    "**/__pycache__/**",
    "**/*.pyc",
    "**/*.pyo",
    "**/*.dist-info/RECORD",
  ]
}

resource "aws_lambda_layer_version" "dw_bootstrap_deps" {
  layer_name          = "${var.project_name}-dw-bootstrap-deps"
  description         = "psycopg[binary] v3 wheel for the warehouse DDL bootstrap Lambda."
  filename            = data.archive_file.dw_bootstrap_layer.output_path
  source_code_hash    = data.archive_file.dw_bootstrap_layer.output_base64sha256
  compatible_runtimes = ["python3.12"]
}

# ---------------------------------------------------------------------------
# Handler archive
# ---------------------------------------------------------------------------

data "archive_file" "dw_bootstrap" {
  type        = "zip"
  source_file = "${local.dw_bootstrap_src_root}/handler.py"
  output_path = "${path.module}/.terraform/dw_bootstrap.zip"
}

# ---------------------------------------------------------------------------
# IAM
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "dw_bootstrap" {
  name              = "/aws/lambda/${var.project_name}-dw-bootstrap"
  retention_in_days = var.lambda_log_retention_days

  tags = local.common_tags
}

resource "aws_iam_role" "dw_bootstrap" {
  name = "${var.project_name}-dw-bootstrap-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "lambda.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })

  tags = local.common_tags
}

# Lambda needs the VPCAccessExecutionRole to manage ENIs in private subnets.
resource "aws_iam_role_policy_attachment" "dw_bootstrap_vpc" {
  role       = aws_iam_role.dw_bootstrap.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy" "dw_bootstrap" {
  name = "${var.project_name}-dw-bootstrap"
  role = aws_iam_role.dw_bootstrap.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadDDLObjects"
        Effect = "Allow"
        Action = ["s3:GetObject"]
        Resource = [
          "${aws_s3_bucket.raw.arn}/${aws_s3_object.dw_schema_sql.key}",
          "${aws_s3_bucket.raw.arn}/${aws_s3_object.dw_seed_sql.key}",
        ]
      },
      {
        Sid      = "ReadRDSCredentials"
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_secretsmanager_secret.rds_master.arn
      },
      {
        Sid    = "WriteLambdaLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "${aws_cloudwatch_log_group.dw_bootstrap.arn}:*"
      },
    ]
  })
}

# ---------------------------------------------------------------------------
# Lambda function
# ---------------------------------------------------------------------------

resource "aws_lambda_function" "dw_bootstrap" {
  function_name = "${var.project_name}-dw-bootstrap"
  description   = "One-shot: applies dw_schema.sql then dw_seed.sql to the warehouse RDS."

  role        = aws_iam_role.dw_bootstrap.arn
  handler     = "handler.lambda_handler"
  runtime     = "python3.12"
  timeout     = 300
  memory_size = 512

  filename         = data.archive_file.dw_bootstrap.output_path
  source_code_hash = data.archive_file.dw_bootstrap.output_base64sha256
  layers           = [aws_lambda_layer_version.dw_bootstrap_deps.arn]

  # Same SG as the Glue job will use — single allow-list entry on the RDS SG.
  vpc_config {
    subnet_ids         = data.aws_subnets.default.ids
    security_group_ids = [aws_security_group.glue_jdbc.id]
  }

  environment {
    variables = {
      SECRET_ARN = aws_secretsmanager_secret.rds_master.arn
      BUCKET     = aws_s3_bucket.raw.bucket
      SCHEMA_KEY = aws_s3_object.dw_schema_sql.key
      SEED_KEY   = aws_s3_object.dw_seed_sql.key
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.dw_bootstrap,
    aws_iam_role_policy.dw_bootstrap,
    aws_iam_role_policy_attachment.dw_bootstrap_vpc,
    # The Lambda has no AWS API egress without these endpoints — see
    # terraform/vpc_endpoints.tf for the network rationale.
    aws_vpc_endpoint.s3,
    aws_vpc_endpoint.secretsmanager,
    aws_vpc_endpoint.logs,
  ]

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# One-shot invocation at apply-time
#
# Re-runs whenever the schema or seed file content changes (filemd5 triggers)
# or when the RDS instance is replaced. The Lambda's idempotency contract
# (CREATE IF NOT EXISTS + ON CONFLICT DO NOTHING) makes repeat invocations
# safe. The aws_db_instance.dw dependency forces this to run AFTER the DB is
# available and Secrets Manager has the populated host/port.
# ---------------------------------------------------------------------------

resource "aws_lambda_invocation" "dw_bootstrap" {
  function_name = aws_lambda_function.dw_bootstrap.function_name

  input = jsonencode({
    action = "apply"
  })

  triggers = {
    schema_md5 = filemd5(local.schema_sql_path)
    seed_md5   = filemd5(local.seed_sql_path)
    db_arn     = aws_db_instance.dw.arn
  }

  depends_on = [
    aws_db_instance.dw,
    aws_secretsmanager_secret_version.rds_master,
    aws_lambda_function.dw_bootstrap,
  ]
}
