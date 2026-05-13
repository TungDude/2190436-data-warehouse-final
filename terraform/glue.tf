# ---------------------------------------------------------------------------
# Glue Data Catalog databases (bronze + silver zones)
# ---------------------------------------------------------------------------

resource "aws_glue_catalog_database" "bronze" {
  name        = var.glue_database_bronze_name
  description = "Bronze (raw) zone of the Chicago crime data lake."

  tags = local.common_tags
}

resource "aws_glue_catalog_database" "silver" {
  name        = var.glue_database_silver_name
  description = "Silver (standardized) zone of the Chicago crime data lake. Parquet, type-cast and deduped."

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# Glue script + helper-library uploads
#
# `main.py` is uploaded as a standalone object and referenced from the job's
# `command.script_location`. The package's helper modules (registry, common,
# sources/*) are zipped into a single archive and referenced via
# `--extra-py-files`. We use a zip rather than loose .py files because Glue's
# --extra-py-files flattens loose files into one sys.path directory — which
# (a) collides duplicate basenames like __init__.py across the package tree
# and (b) breaks intra-package imports. zipimport handles the package tree
# natively when the archive is added to sys.path as a unit.
# ---------------------------------------------------------------------------

locals {
  glue_job_src_root = "${path.module}/../src/glue_jobs/bronze_to_silver"
}

resource "aws_s3_object" "bronze_to_silver_script" {
  bucket       = aws_s3_bucket.raw.id
  key          = "${var.glue_scripts_prefix}/bronze_to_silver/main.py"
  source       = "${local.glue_job_src_root}/main.py"
  etag         = filemd5("${local.glue_job_src_root}/main.py")
  content_type = "text/x-python"

  tags = local.common_tags
}

# Zip the helper package excluding main.py (the entry script) and any
# Python build artefacts that would churn the zip's MD5 between runs.
data "archive_file" "bronze_to_silver_libs" {
  type        = "zip"
  source_dir  = local.glue_job_src_root
  output_path = "${path.module}/.terraform/bronze_to_silver_libs.zip"
  excludes = [
    "main.py",
    "**/__pycache__",
    "**/__pycache__/**",
    "**/*.pyc",
    "**/*.pyo",
  ]
}

resource "aws_s3_object" "bronze_to_silver_libs" {
  bucket       = aws_s3_bucket.raw.id
  key          = "${var.glue_scripts_prefix}/bronze_to_silver/libs.zip"
  source       = data.archive_file.bronze_to_silver_libs.output_path
  etag         = data.archive_file.bronze_to_silver_libs.output_md5
  content_type = "application/zip"

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# IAM for the Glue job + crawlers (one shared role)
# ---------------------------------------------------------------------------

resource "aws_iam_role" "glue_service" {
  name = "${var.project_name}-glue-service"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "glue.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = local.common_tags
}

# AWSGlueServiceRole is the AWS-managed policy for Glue service roles. It grants
# broad access including read/write on any bucket beginning with `aws-glue-*`,
# which is wider than this project strictly needs. Acceptable for a course
# project; for production, replace with a tighter inline policy that only grants
# the Glue service operations (CreateTable/UpdateTable/GetPartition/etc.) the
# crawlers and job actually need.
resource "aws_iam_role_policy_attachment" "glue_managed" {
  role       = aws_iam_role.glue_service.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

resource "aws_iam_role_policy" "glue_s3_access" {
  name = "${var.project_name}-glue-s3-access"
  role = aws_iam_role.glue_service.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListRawBucket"
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:GetBucketLocation"]
        Resource = aws_s3_bucket.raw.arn
      },
      {
        Sid      = "ReadRawObjects"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:GetObjectVersion"]
        Resource = "${aws_s3_bucket.raw.arn}/${var.raw_prefix}/*"
      },
      {
        Sid    = "WriteSilverObjects"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListMultipartUploadParts",
          "s3:AbortMultipartUpload"
        ]
        Resource = "${aws_s3_bucket.raw.arn}/${var.silver_prefix}/*"
      },
      {
        Sid    = "ReadGlueScripts"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion"
        ]
        Resource = "${aws_s3_bucket.raw.arn}/${var.glue_scripts_prefix}/*"
      },
      {
        Sid    = "ReadWriteGlueTempAndEvents"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "${aws_s3_bucket.raw.arn}/glue/tmp/*",
          "${aws_s3_bucket.raw.arn}/glue/spark-events/*"
        ]
      }
    ]
  })
}

resource "aws_cloudwatch_log_group" "glue_bronze_to_silver" {
  for_each = toset(var.glue_supported_sources)

  name              = "/aws-glue/jobs/${var.project_name}-bronze-to-silver-${each.value}"
  retention_in_days = var.glue_log_retention_days

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# Glue ETL job (bronze -> silver, one job per source)
#
# We provision one Glue Job per `var.glue_supported_sources` entry so the
# `after_silver_jobs` trigger's AND predicate references distinct job_names.
# Glue Trigger conditions evaluate per-job-name: with a single parameterised
# job, multiple identical conditions under an AND collapse to one and the
# silver crawler would fire after the first source completes instead of all
# of them. One job per source makes the predicate unambiguous.
# ---------------------------------------------------------------------------

resource "aws_glue_job" "bronze_to_silver" {
  for_each = toset(var.glue_supported_sources)

  name              = "${var.project_name}-bronze-to-silver-${each.value}"
  description       = "Bronze -> silver PySpark job for source ${each.value}."
  role_arn          = aws_iam_role.glue_service.arn
  glue_version      = var.glue_version
  worker_type       = var.glue_worker_type
  number_of_workers = var.glue_number_of_workers
  timeout           = var.glue_job_timeout_minutes
  max_retries       = var.glue_job_max_retries

  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = "s3://${aws_s3_bucket.raw.bucket}/${aws_s3_object.bronze_to_silver_script.key}"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-job-insights"              = "true"
    "--enable-glue-datacatalog"          = "true"
    "--enable-spark-ui"                  = "true"
    # Explicitly disable Glue job bookmarks. Bronze -> silver re-reads every
    # bronze partition on each run because dedup-by-id-keeping-latest-
    # updated_on only resolves correctly when the full set of duplicates is in
    # scope; a future maintainer enabling bookmarks would silently break the
    # upsert-by-id contract from dimensional-design.md §3.2.1.
    "--job-bookmark-option"   = "job-bookmark-disable"
    "--TempDir"               = "s3://${aws_s3_bucket.raw.bucket}/glue/tmp/"
    "--spark-event-logs-path" = "s3://${aws_s3_bucket.raw.bucket}/glue/spark-events/"
    "--source"                = each.value
    "--raw_bucket"            = aws_s3_bucket.raw.bucket
    "--raw_prefix"            = var.raw_prefix
    "--silver_prefix"         = var.silver_prefix
    "--bronze_database"       = aws_glue_catalog_database.bronze.name
    "--silver_database"       = aws_glue_catalog_database.silver.name
    "--extra-py-files"        = "s3://${aws_s3_bucket.raw.bucket}/${aws_s3_object.bronze_to_silver_libs.key}"
  }

  depends_on = [
    aws_cloudwatch_log_group.glue_bronze_to_silver,
    aws_iam_role_policy.glue_s3_access,
    aws_iam_role_policy_attachment.glue_managed
  ]

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# Glue Crawlers: one per zone
# ---------------------------------------------------------------------------

resource "aws_glue_crawler" "bronze" {
  name          = "${var.project_name}-bronze"
  description   = "Crawls the bronze (raw) zone and registers one table per source under raw/."
  role          = aws_iam_role.glue_service.arn
  database_name = aws_glue_catalog_database.bronze.name

  s3_target {
    path = "s3://${aws_s3_bucket.raw.bucket}/${var.raw_prefix}/"
  }

  # Critical: TableLevelConfiguration = 3 places the table at
  # bucket(1)/raw(2)/<source>(3) — i.e., one logical table per source folder,
  # with ingest_date=YYYY-MM-DD/ as partitions of that table.
  configuration = jsonencode({
    Version = 1.0
    Grouping = {
      TableGroupingPolicy     = "CombineCompatibleSchemas"
      TableLevelConfiguration = 3
    }
    CrawlerOutput = {
      Partitions = {
        AddOrUpdateBehavior = "InheritFromTable"
      }
    }
  })

  schema_change_policy {
    update_behavior = "UPDATE_IN_DATABASE"
    delete_behavior = "LOG"
  }

  # Bronze is append-only: each Lambda run lands one new
  # ingest_date=YYYY-MM-DD/ folder under raw/<source>/. CRAWL_NEW_FOLDERS_ONLY
  # makes each daily crawl a constant-cost operation regardless of historical
  # backfill size. AWS Glue notes this requires schema_change_policy
  # delete_behavior = "LOG" (set above) and treats update_behavior as
  # informational; both are compatible with our config.
  recrawl_policy {
    recrawl_behavior = "CRAWL_NEW_FOLDERS_ONLY"
  }

  lineage_configuration {
    crawler_lineage_settings = "DISABLE"
  }

  tags = local.common_tags
}

resource "aws_glue_crawler" "silver" {
  name          = "${var.project_name}-silver"
  description   = "Crawls the silver (standardized) zone and registers one Parquet table per source."
  role          = aws_iam_role.glue_service.arn
  database_name = aws_glue_catalog_database.silver.name

  s3_target {
    path = "s3://${aws_s3_bucket.raw.bucket}/${var.silver_prefix}/"
  }

  # Same TableLevelConfiguration semantics as bronze: bucket(1)/silver(2)/<source>(3).
  configuration = jsonencode({
    Version = 1.0
    Grouping = {
      TableGroupingPolicy     = "CombineCompatibleSchemas"
      TableLevelConfiguration = 3
    }
    CrawlerOutput = {
      Partitions = {
        AddOrUpdateBehavior = "InheritFromTable"
      }
    }
  })

  schema_change_policy {
    update_behavior = "UPDATE_IN_DATABASE"
    delete_behavior = "LOG"
  }

  recrawl_policy {
    recrawl_behavior = "CRAWL_EVERYTHING"
  }

  lineage_configuration {
    crawler_lineage_settings = "DISABLE"
  }

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# Glue Workflow: bronze crawler -> per-source jobs -> silver crawler
# ---------------------------------------------------------------------------

resource "aws_glue_workflow" "bronze_to_silver" {
  name        = "${var.project_name}-bronze-to-silver"
  description = "Bronze crawler -> bronze->silver Spark job (per source) -> silver crawler."

  tags = local.common_tags
}

# Entry trigger. Type ON_DEMAND so only EventBridge Scheduler (timezone-aware)
# starts the workflow; Glue's built-in cron is UTC-only and we want
# America/Chicago wall-clock semantics.
resource "aws_glue_trigger" "workflow_start" {
  name          = "${var.project_name}-workflow-start"
  description   = "Entry trigger for the bronze->silver workflow. Started by EventBridge Scheduler."
  type          = "ON_DEMAND"
  workflow_name = aws_glue_workflow.bronze_to_silver.name

  actions {
    crawler_name = aws_glue_crawler.bronze.name
  }

  tags = local.common_tags
}

# After bronze crawler succeeds: fan out to one job run per supported source.
resource "aws_glue_trigger" "after_bronze_crawler" {
  name              = "${var.project_name}-after-bronze-crawler"
  description       = "Run bronze->silver job per source after the bronze crawler succeeds."
  type              = "CONDITIONAL"
  workflow_name     = aws_glue_workflow.bronze_to_silver.name
  start_on_creation = true
  enabled           = true

  predicate {
    conditions {
      crawler_name = aws_glue_crawler.bronze.name
      crawl_state  = "SUCCEEDED"
    }
  }

  # Each per-source Glue job already has its `--source` baked into
  # `default_arguments`, so we fan out by job resource (not by argument).
  dynamic "actions" {
    for_each = aws_glue_job.bronze_to_silver

    content {
      job_name = actions.value.name
    }
  }

  tags = local.common_tags
}

# After every per-source job run succeeds: refresh silver catalog.
resource "aws_glue_trigger" "after_silver_jobs" {
  name              = "${var.project_name}-after-silver-jobs"
  description       = "Refresh the silver catalog once every per-source bronze->silver job has succeeded."
  type              = "CONDITIONAL"
  workflow_name     = aws_glue_workflow.bronze_to_silver.name
  start_on_creation = true
  enabled           = true

  predicate {
    logical = "AND"

    # One condition per per-source Glue job, all required (logical = AND).
    # Distinct job_names mean Glue's evaluator treats them as independent
    # checks rather than collapsing duplicates.
    dynamic "conditions" {
      for_each = aws_glue_job.bronze_to_silver

      content {
        job_name = conditions.value.name
        state    = "SUCCEEDED"
      }
    }
  }

  actions {
    crawler_name = aws_glue_crawler.silver.name
  }

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# EventBridge Scheduler -> glue:StartWorkflowRun (timezone-aware entry point)
# ---------------------------------------------------------------------------

resource "aws_iam_role" "glue_workflow_starter" {
  name = "${var.project_name}-glue-workflow-starter"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "scheduler.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "glue_workflow_starter" {
  name = "${var.project_name}-glue-workflow-starter"
  role = aws_iam_role.glue_workflow_starter.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "StartWorkflowRun"
        Effect   = "Allow"
        Action   = "glue:StartWorkflowRun"
        Resource = "arn:aws:glue:${var.aws_region}:${data.aws_caller_identity.current.account_id}:workflow/${aws_glue_workflow.bronze_to_silver.name}"
      }
    ]
  })
}

resource "aws_scheduler_schedule" "daily_glue_workflow" {
  name                         = "${var.project_name}-glue-workflow-daily"
  description                  = "Daily start of the bronze->silver Glue Workflow."
  schedule_expression          = var.glue_workflow_schedule_expression
  schedule_expression_timezone = var.glue_workflow_schedule_timezone
  state                        = var.glue_workflow_schedule_enabled ? "ENABLED" : "DISABLED"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:glue:startWorkflowRun"
    role_arn = aws_iam_role.glue_workflow_starter.arn

    input = jsonencode({
      Name = aws_glue_workflow.bronze_to_silver.name
    })
  }
}
