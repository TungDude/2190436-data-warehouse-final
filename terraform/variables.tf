variable "project_name" {
  description = "Project name used for AWS resource names and tags."
  type        = string
  default     = "data-warehouse-final"
}

variable "environment" {
  description = "Deployment environment tag."
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "ap-southeast-1"
}

variable "aws_profile" {
  description = "Optional AWS CLI profile. Prefer setting AWS_PROFILE from the local agent config."
  type        = string
  default     = null
}

variable "raw_bucket_name" {
  description = "Optional explicit raw data lake bucket name. Must be globally unique."
  type        = string
  default     = null
}

variable "raw_bucket_force_destroy" {
  description = "Whether Terraform may delete the raw bucket even when it contains objects."
  type        = bool
  default     = false
}

variable "raw_chicago_crime_prefix" {
  description = "S3 prefix for raw Chicago crime objects. Keep this aligned with project instructions."
  type        = string
  default     = "raw/chicaho_crime"

  validation {
    condition     = !startswith(var.raw_chicago_crime_prefix, "/") && !endswith(var.raw_chicago_crime_prefix, "/")
    error_message = "raw_chicago_crime_prefix must not start or end with '/'."
  }
}

variable "chicago_crime_api_url" {
  description = "Chicago crime Socrata CSV API endpoint."
  type        = string
  default     = "https://data.cityofchicago.org/resource/ijzp-q8t2.csv"
}

variable "fetch_lookback_days" {
  description = "Days before the run date to fetch. Chicago's official source excludes the most recent 7 days, so 8 is a conservative default."
  type        = number
  default     = 8
}

variable "fetch_limit" {
  description = "Maximum rows to fetch per Lambda run."
  type        = number
  default     = 100000
}

variable "source_timezone" {
  description = "Timezone used to calculate the source data date."
  type        = string
  default     = "America/Chicago"
}

variable "lambda_timeout_seconds" {
  description = "Lambda timeout in seconds."
  type        = number
  default     = 900
}

variable "lambda_memory_size" {
  description = "Lambda memory size in MB."
  type        = number
  default     = 512
}

variable "lambda_log_retention_days" {
  description = "CloudWatch log retention for the fetch Lambda."
  type        = number
  default     = 14
}

variable "fetch_schedule_expression" {
  description = "EventBridge Scheduler expression for daily fetches."
  type        = string
  default     = "cron(0 2 * * ? *)"
}

variable "fetch_schedule_timezone" {
  description = "Timezone for the EventBridge Scheduler expression."
  type        = string
  default     = "America/Chicago"
}

variable "fetch_schedule_enabled" {
  description = "Whether the EventBridge schedule is enabled."
  type        = bool
  default     = true
}

# ---------------------------------------------------------------------------
# Silver / Glue ETL configuration
# ---------------------------------------------------------------------------

variable "raw_prefix" {
  description = "S3 key prefix (no leading or trailing slash) for the bronze / raw zone. The chicago_crime Lambda still owns the source-specific subprefix (`raw_chicago_crime_prefix`) under this root."
  type        = string
  default     = "raw"

  validation {
    condition     = !startswith(var.raw_prefix, "/") && !endswith(var.raw_prefix, "/")
    error_message = "raw_prefix must not start or end with '/'."
  }
}

variable "silver_prefix" {
  description = "S3 key prefix (no leading or trailing slash) for the silver / standardized zone."
  type        = string
  default     = "standardized"

  validation {
    condition     = !startswith(var.silver_prefix, "/") && !endswith(var.silver_prefix, "/")
    error_message = "silver_prefix must not start or end with '/'."
  }
}

variable "glue_scripts_prefix" {
  description = "S3 key prefix (no leading or trailing slash) where Glue PySpark scripts and extra_py modules live in the raw bucket."
  type        = string
  default     = "glue/scripts"

  validation {
    condition     = !startswith(var.glue_scripts_prefix, "/") && !endswith(var.glue_scripts_prefix, "/")
    error_message = "glue_scripts_prefix must not start or end with '/'."
  }
}

variable "glue_database_bronze_name" {
  description = "Glue Data Catalog database name for the bronze zone."
  type        = string
  default     = "data_warehouse_final_bronze"
}

variable "glue_database_silver_name" {
  description = "Glue Data Catalog database name for the silver zone."
  type        = string
  default     = "data_warehouse_final_silver"
}

variable "glue_version" {
  description = "AWS Glue version used by the bronze->silver job."
  type        = string
  default     = "5.0"
}

variable "glue_worker_type" {
  description = "Glue worker type for the bronze->silver job."
  type        = string
  default     = "G.1X"
}

variable "glue_number_of_workers" {
  description = "Number of Glue workers for the bronze->silver job. Minimum 2 for G.1X."
  type        = number
  default     = 2
}

variable "glue_job_timeout_minutes" {
  description = "Glue job timeout in minutes."
  type        = number
  default     = 60
}

variable "glue_job_max_retries" {
  description = "Glue job retry attempts. Workflow-level retry is preferred; default 0 here."
  type        = number
  default     = 0
}

variable "glue_log_retention_days" {
  description = "CloudWatch log retention for the Glue job log group."
  type        = number
  default     = 14
}

variable "glue_workflow_schedule_expression" {
  description = "EventBridge Scheduler cron expression that starts the Glue Workflow."
  type        = string
  default     = "cron(30 3 * * ? *)"
}

variable "glue_workflow_schedule_timezone" {
  description = "Timezone for the EventBridge Scheduler that starts the Glue Workflow."
  type        = string
  default     = "America/Chicago"
}

variable "glue_workflow_schedule_enabled" {
  description = "Whether the EventBridge Scheduler that starts the Glue Workflow is enabled."
  type        = bool
  default     = true
}

variable "glue_supported_sources" {
  description = "Sources the bronze->silver Glue Workflow runs per scheduled execution. Each name must have a matching handler module under src/glue_jobs/bronze_to_silver/sources/."
  type        = list(string)
  default     = ["chicago_crime"]

  validation {
    condition     = length(var.glue_supported_sources) > 0
    error_message = "glue_supported_sources must contain at least one source."
  }
}
