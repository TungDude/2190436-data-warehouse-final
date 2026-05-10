output "raw_bucket_name" {
  description = "Raw data lake S3 bucket name."
  value       = aws_s3_bucket.raw.bucket
}

output "raw_chicago_crime_prefix" {
  description = "Raw Chicago crime S3 prefix."
  value       = var.raw_chicago_crime_prefix
}

output "fetch_lambda_name" {
  description = "Chicago crime fetch Lambda function name."
  value       = aws_lambda_function.fetch_chicago_crime.function_name
}

output "daily_fetch_schedule_name" {
  description = "EventBridge Scheduler schedule name for the daily Chicago crime fetch."
  value       = aws_scheduler_schedule.daily_fetch_chicago_crime.name
}

# ---------------------------------------------------------------------------
# Silver / Glue ETL outputs
# ---------------------------------------------------------------------------

output "silver_prefix" {
  description = "S3 key prefix (no trailing slash) for the silver / standardized zone."
  value       = var.silver_prefix
}

output "silver_s3_uri" {
  description = "Fully qualified S3 URI of the silver zone."
  value       = "s3://${aws_s3_bucket.raw.bucket}/${var.silver_prefix}/"
}

output "glue_bronze_database_name" {
  description = "Glue Data Catalog database for the bronze zone."
  value       = aws_glue_catalog_database.bronze.name
}

output "glue_silver_database_name" {
  description = "Glue Data Catalog database for the silver zone."
  value       = aws_glue_catalog_database.silver.name
}

output "glue_bronze_to_silver_job_name" {
  description = "Glue job name for the bronze->silver source-parameterised PySpark job."
  value       = aws_glue_job.bronze_to_silver.name
}

output "glue_workflow_name" {
  description = "Glue Workflow name that chains bronze crawler -> silver job(s) -> silver crawler."
  value       = aws_glue_workflow.bronze_to_silver.name
}

output "glue_bronze_crawler_name" {
  description = "Glue Crawler name for the bronze zone."
  value       = aws_glue_crawler.bronze.name
}

output "glue_silver_crawler_name" {
  description = "Glue Crawler name for the silver zone."
  value       = aws_glue_crawler.silver.name
}

output "glue_workflow_schedule_name" {
  description = "EventBridge Scheduler schedule name that starts the Glue Workflow."
  value       = aws_scheduler_schedule.daily_glue_workflow.name
}
