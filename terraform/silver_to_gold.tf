# ---------------------------------------------------------------------------
# Silver -> Gold Glue stack
#
# Two Glue Jobs back the same PySpark script binary:
#   - silver-to-gold-dims  (--target dims, runs the four dim loaders)
#   - silver-to-gold-facts (--target facts, runs fact_crime)
#
# Distinct job resources make the workflow's CONDITIONAL predicate
# unambiguous: "dims SUCCEEDED -> facts" cannot collapse the way a
# single parameterised job's repeated job_name conditions would
# (see terraform/glue.tf header comments on the bronze->silver split).
#
# Both jobs run inside the default VPC via aws_glue_connection.dw so
# they can reach RDS for the SCD merges. psycopg[binary] is pulled in
# via --additional-python-modules (Glue 5.0 feature) — Glue's stock
# image does not ship psycopg.
# ---------------------------------------------------------------------------

locals {
  silver_to_gold_src_root = "${path.module}/../src/glue_jobs/silver_to_gold"
}

# ---------------------------------------------------------------------------
# Script + helper-library uploads (mirror bronze->silver pattern)
# ---------------------------------------------------------------------------

resource "aws_s3_object" "glue_scripts_silver_to_gold_prefix" {
  bucket       = aws_s3_bucket.raw.id
  key          = "${var.glue_scripts_prefix}/silver_to_gold/"
  content      = ""
  content_type = "application/x-directory"
}

resource "aws_s3_object" "silver_to_gold_script" {
  bucket       = aws_s3_bucket.raw.id
  key          = "${var.glue_scripts_prefix}/silver_to_gold/main.py"
  source       = "${local.silver_to_gold_src_root}/main.py"
  etag         = filemd5("${local.silver_to_gold_src_root}/main.py")
  content_type = "text/x-python"

  tags = local.common_tags
}

data "archive_file" "silver_to_gold_libs" {
  type        = "zip"
  source_dir  = local.silver_to_gold_src_root
  output_path = "${path.module}/.terraform/silver_to_gold_libs.zip"
  excludes = [
    "main.py",
    "**/__pycache__",
    "**/__pycache__/**",
    "**/*.pyc",
    "**/*.pyo",
  ]
}

resource "aws_s3_object" "silver_to_gold_libs" {
  bucket       = aws_s3_bucket.raw.id
  key          = "${var.glue_scripts_prefix}/silver_to_gold/libs.zip"
  source       = data.archive_file.silver_to_gold_libs.output_path
  etag         = data.archive_file.silver_to_gold_libs.output_md5
  content_type = "application/zip"

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# IAM — extend the existing glue_service role with Secrets Manager access
# ---------------------------------------------------------------------------

resource "aws_iam_role_policy" "glue_silver_to_gold_secrets" {
  name = "${var.project_name}-glue-silver-to-gold-secrets"
  role = aws_iam_role.glue_service.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadRDSCredentials"
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_secretsmanager_secret.rds_master.arn
      },
    ]
  })
}

# ---------------------------------------------------------------------------
# CloudWatch log groups (one per gold job)
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "glue_silver_to_gold_dims" {
  name              = "/aws-glue/jobs/${var.project_name}-silver-to-gold-dims"
  retention_in_days = var.glue_log_retention_days

  tags = local.common_tags
}

resource "aws_cloudwatch_log_group" "glue_silver_to_gold_facts" {
  name              = "/aws-glue/jobs/${var.project_name}-silver-to-gold-facts"
  retention_in_days = var.glue_log_retention_days

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# Glue Jobs
#
# Shared default_arguments via a local; per-job differences are just the
# --target value and the depends_on log-group reference.
# ---------------------------------------------------------------------------

locals {
  silver_to_gold_common_args = {
    "--job-language"                     = "python"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-job-insights"              = "true"
    "--enable-glue-datacatalog"          = "true"
    "--enable-spark-ui"                  = "true"
    # Bookmarks are disabled for the same reason as bronze->silver: the
    # merge logic re-reads the full silver partition set each run; a
    # bookmark would silently skip rows and break SCD2 + fact upserts.
    "--job-bookmark-option"   = "job-bookmark-disable"
    "--TempDir"               = "s3://${aws_s3_bucket.raw.bucket}/glue/tmp/"
    "--spark-event-logs-path" = "s3://${aws_s3_bucket.raw.bucket}/glue/spark-events/"
    "--silver_database"       = aws_glue_catalog_database.silver.name
    "--secret_arn"            = aws_secretsmanager_secret.rds_master.arn
    "--region"                = var.aws_region
    "--extra-py-files"        = "s3://${aws_s3_bucket.raw.bucket}/${aws_s3_object.silver_to_gold_libs.key}"
    # Glue 5.0 pulls these from PyPI into the job's Python env at runtime.
    # Pinning to the same version range as the DDL Lambda's requirements
    # keeps driver behaviour consistent across the stack.
    "--additional-python-modules" = "psycopg[binary]==3.2.*"
  }
}

resource "aws_glue_job" "silver_to_gold_dims" {
  name              = "${var.project_name}-silver-to-gold-dims"
  description       = "Silver -> gold dim loaders (--target dims). One row per dim module in registry.TARGETS['dims']."
  role_arn          = aws_iam_role.glue_service.arn
  glue_version      = var.glue_version
  worker_type       = var.glue_silver_to_gold_worker_type
  number_of_workers = var.glue_silver_to_gold_number_of_workers
  timeout           = var.glue_job_timeout_minutes
  max_retries       = var.glue_job_max_retries

  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = "s3://${aws_s3_bucket.raw.bucket}/${aws_s3_object.silver_to_gold_script.key}"
  }

  default_arguments = merge(local.silver_to_gold_common_args, {
    "--target" = "dims"
  })

  # connections puts the job inside the VPC so it can reach RDS via the
  # private path established by aws_glue_connection.dw.
  connections = [aws_glue_connection.dw.name]

  depends_on = [
    aws_cloudwatch_log_group.glue_silver_to_gold_dims,
    aws_iam_role_policy.glue_s3_access,
    aws_iam_role_policy.glue_silver_to_gold_secrets,
    aws_iam_role_policy_attachment.glue_managed,
    aws_vpc_endpoint.s3,
    aws_vpc_endpoint.secretsmanager,
  ]

  tags = local.common_tags
}

resource "aws_glue_job" "silver_to_gold_facts" {
  name              = "${var.project_name}-silver-to-gold-facts"
  description       = "Silver -> gold fact loaders (--target facts). Runs after the dims job so SCD2 FK resolution finds the current dim versions."
  role_arn          = aws_iam_role.glue_service.arn
  glue_version      = var.glue_version
  worker_type       = var.glue_silver_to_gold_worker_type
  number_of_workers = var.glue_silver_to_gold_number_of_workers
  timeout           = var.glue_job_timeout_minutes
  max_retries       = var.glue_job_max_retries

  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = "s3://${aws_s3_bucket.raw.bucket}/${aws_s3_object.silver_to_gold_script.key}"
  }

  default_arguments = merge(local.silver_to_gold_common_args, {
    "--target" = "facts"
  })

  connections = [aws_glue_connection.dw.name]

  depends_on = [
    aws_cloudwatch_log_group.glue_silver_to_gold_facts,
    aws_iam_role_policy.glue_s3_access,
    aws_iam_role_policy.glue_silver_to_gold_secrets,
    aws_iam_role_policy_attachment.glue_managed,
    aws_vpc_endpoint.s3,
    aws_vpc_endpoint.secretsmanager,
  ]

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# Workflow triggers — extend the existing bronze_to_silver workflow
#
# Chain after the silver crawler completes:
#   silver crawler SUCCEEDED -> silver_to_gold_dims
#   silver_to_gold_dims SUCCEEDED -> silver_to_gold_facts
#
# Reusing the same workflow keeps EventBridge Scheduler targeting one
# entry point (no schedule changes); the workflow shape grows in place.
# ---------------------------------------------------------------------------

resource "aws_glue_trigger" "after_silver_crawler" {
  name              = "${var.project_name}-after-silver-crawler"
  description       = "Run the silver->gold dims job after the silver crawler succeeds."
  type              = "CONDITIONAL"
  workflow_name     = aws_glue_workflow.bronze_to_silver.name
  start_on_creation = true
  enabled           = true

  predicate {
    conditions {
      crawler_name = aws_glue_crawler.silver.name
      crawl_state  = "SUCCEEDED"
    }
  }

  actions {
    job_name = aws_glue_job.silver_to_gold_dims.name
  }

  tags = local.common_tags
}

resource "aws_glue_trigger" "after_silver_to_gold_dims" {
  name              = "${var.project_name}-after-silver-to-gold-dims"
  description       = "Run the silver->gold facts job after the dims job succeeds."
  type              = "CONDITIONAL"
  workflow_name     = aws_glue_workflow.bronze_to_silver.name
  start_on_creation = true
  enabled           = true

  predicate {
    conditions {
      job_name = aws_glue_job.silver_to_gold_dims.name
      state    = "SUCCEEDED"
    }
  }

  actions {
    job_name = aws_glue_job.silver_to_gold_facts.name
  }

  tags = local.common_tags
}
