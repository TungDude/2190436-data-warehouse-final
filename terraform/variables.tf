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
