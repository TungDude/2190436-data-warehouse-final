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
# Glue script + extra-py-files uploads (S3-hosted, re-uploaded on file change)
# ---------------------------------------------------------------------------

locals {
  glue_job_src_root = "${path.module}/../src/glue_jobs/bronze_to_silver"

  # Every .py inside the bronze_to_silver package, relative to glue_job_src_root.
  glue_job_all_py = fileset(local.glue_job_src_root, "**/*.py")

  # Everything except main.py is shipped via --extra-py-files.
  glue_job_extra_py_files = toset([
    for f in local.glue_job_all_py : f if f != "main.py"
  ])
}

resource "aws_s3_object" "bronze_to_silver_script" {
  bucket       = aws_s3_bucket.raw.id
  key          = "${var.glue_scripts_prefix}/bronze_to_silver/main.py"
  source       = "${local.glue_job_src_root}/main.py"
  etag         = filemd5("${local.glue_job_src_root}/main.py")
  content_type = "text/x-python"

  tags = local.common_tags
}

resource "aws_s3_object" "bronze_to_silver_extra_py" {
  for_each = local.glue_job_extra_py_files

  bucket       = aws_s3_bucket.raw.id
  key          = "${var.glue_scripts_prefix}/bronze_to_silver/${each.value}"
  source       = "${local.glue_job_src_root}/${each.value}"
  etag         = filemd5("${local.glue_job_src_root}/${each.value}")
  content_type = "text/x-python"

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
        Resource = "${aws_s3_bucket.raw.arn}/raw/*"
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
        Sid    = "ReadWriteGlueTemp"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = "${aws_s3_bucket.raw.arn}/glue/*"
      }
    ]
  })
}

resource "aws_cloudwatch_log_group" "glue_bronze_to_silver" {
  name              = "/aws-glue/jobs/${var.project_name}-bronze-to-silver"
  retention_in_days = var.glue_log_retention_days

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# Glue ETL job (bronze -> silver, source-parameterised)
# ---------------------------------------------------------------------------

resource "aws_glue_job" "bronze_to_silver" {
  name              = "${var.project_name}-bronze-to-silver"
  description       = "Bronze -> silver source-parameterised PySpark job. Run via Glue Workflow with --source set per source."
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
    "--TempDir"                          = "s3://${aws_s3_bucket.raw.bucket}/glue/tmp/"
    "--spark-event-logs-path"            = "s3://${aws_s3_bucket.raw.bucket}/glue/spark-events/"
    "--source"                           = var.glue_supported_sources[0]
    "--raw_bucket"                       = aws_s3_bucket.raw.bucket
    "--raw_prefix"                       = "raw"
    "--silver_prefix"                    = var.silver_prefix
    "--bronze_database"                  = aws_glue_catalog_database.bronze.name
    "--silver_database"                  = aws_glue_catalog_database.silver.name
    "--extra-py-files" = join(
      ",",
      [for o in aws_s3_object.bronze_to_silver_extra_py : "s3://${aws_s3_bucket.raw.bucket}/${o.key}"]
    )
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
    path = "s3://${aws_s3_bucket.raw.bucket}/raw/"
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

  recrawl_policy {
    recrawl_behavior = "CRAWL_EVERYTHING"
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

  dynamic "actions" {
    for_each = toset(var.glue_supported_sources)

    content {
      job_name = aws_glue_job.bronze_to_silver.name
      arguments = {
        "--source" = actions.value
      }
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

    dynamic "conditions" {
      for_each = toset(var.glue_supported_sources)

      content {
        job_name = aws_glue_job.bronze_to_silver.name
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
