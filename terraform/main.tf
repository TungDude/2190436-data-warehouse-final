terraform {
  required_version = ">= 1.6.0"

  required_providers {
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile
}

data "aws_caller_identity" "current" {}

data "archive_file" "fetch_chicago_crime" {
  type        = "zip"
  source_file = "${path.module}/../src/lambda/fetch_chicago_crime/handler.py"
  output_path = "${path.module}/.terraform/fetch_chicago_crime.zip"
}

locals {
  raw_bucket_name = coalesce(
    var.raw_bucket_name,
    lower("${var.project_name}-${data.aws_caller_identity.current.account_id}-${var.aws_region}-raw")
  )

  common_tags = {
    Project     = var.project_name
    ManagedBy   = "terraform"
    Environment = var.environment
  }
}

resource "aws_s3_bucket" "raw" {
  bucket        = local.raw_bucket_name
  force_destroy = var.raw_bucket_force_destroy

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-raw-data-lake"
    Tier = "raw"
  })
}

resource "aws_s3_bucket_public_access_block" "raw" {
  bucket = aws_s3_bucket.raw.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "raw" {
  bucket = aws_s3_bucket.raw.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_object" "chicago_crime_prefix" {
  bucket       = aws_s3_bucket.raw.id
  key          = "${var.raw_chicago_crime_prefix}/"
  content      = ""
  content_type = "application/x-directory"
}

resource "aws_cloudwatch_log_group" "fetch_chicago_crime" {
  name              = "/aws/lambda/${var.project_name}-fetch-chicago-crime"
  retention_in_days = var.lambda_log_retention_days

  tags = local.common_tags
}

resource "aws_iam_role" "lambda_execution" {
  name = "${var.project_name}-fetch-chicago-crime-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "lambda_execution" {
  name = "${var.project_name}-fetch-chicago-crime"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "WriteRawChicagoCrimeObjects"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:PutObjectTagging"
        ]
        Resource = "${aws_s3_bucket.raw.arn}/${var.raw_chicago_crime_prefix}/*"
      },
      {
        Sid    = "WriteLambdaLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.fetch_chicago_crime.arn}:*"
      }
    ]
  })
}

resource "aws_lambda_function" "fetch_chicago_crime" {
  function_name = "${var.project_name}-fetch-chicago-crime"
  description   = "Fetches Chicago crime data and writes raw CSV snapshots to S3."
  role          = aws_iam_role.lambda_execution.arn
  handler       = "handler.lambda_handler"
  runtime       = "python3.12"
  timeout       = var.lambda_timeout_seconds
  memory_size   = var.lambda_memory_size

  filename         = data.archive_file.fetch_chicago_crime.output_path
  source_code_hash = data.archive_file.fetch_chicago_crime.output_base64sha256

  environment {
    variables = {
      RAW_BUCKET            = aws_s3_bucket.raw.bucket
      RAW_PREFIX            = var.raw_chicago_crime_prefix
      CHICAGO_CRIME_API_URL = var.chicago_crime_api_url
      FETCH_LOOKBACK_DAYS   = tostring(var.fetch_lookback_days)
      FETCH_LIMIT           = tostring(var.fetch_limit)
      SOURCE_TIMEZONE       = var.source_timezone
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.fetch_chicago_crime,
    aws_iam_role_policy.lambda_execution
  ]

  tags = local.common_tags
}

resource "aws_iam_role" "scheduler_execution" {
  name = "${var.project_name}-fetch-chicago-crime-scheduler"

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

resource "aws_iam_role_policy" "scheduler_execution" {
  name = "${var.project_name}-invoke-fetch-chicago-crime"
  role = aws_iam_role.scheduler_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "InvokeFetchLambda"
        Effect   = "Allow"
        Action   = "lambda:InvokeFunction"
        Resource = aws_lambda_function.fetch_chicago_crime.arn
      }
    ]
  })
}

resource "aws_scheduler_schedule" "daily_fetch_chicago_crime" {
  name                         = "${var.project_name}-fetch-chicago-crime-daily"
  description                  = "Daily 2 AM fetch of Chicago crime data into the raw data lake."
  schedule_expression          = var.fetch_schedule_expression
  schedule_expression_timezone = var.fetch_schedule_timezone
  state                        = var.fetch_schedule_enabled ? "ENABLED" : "DISABLED"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.fetch_chicago_crime.arn
    role_arn = aws_iam_role.scheduler_execution.arn

    input = jsonencode({
      source = "eventbridge-scheduler"
    })
  }
}

resource "aws_lambda_permission" "allow_scheduler" {
  statement_id  = "AllowExecutionFromEventBridgeScheduler"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.fetch_chicago_crime.function_name
  principal     = "scheduler.amazonaws.com"
  source_arn    = aws_scheduler_schedule.daily_fetch_chicago_crime.arn
}
