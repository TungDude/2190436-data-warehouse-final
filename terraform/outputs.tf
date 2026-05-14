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

output "glue_bronze_to_silver_job_names" {
  description = "Map of source name -> Glue job name for the per-source bronze->silver jobs."
  value       = { for k, j in aws_glue_job.bronze_to_silver : k => j.name }
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

# ---------------------------------------------------------------------------
# Gold (RDS PostgreSQL) outputs
# ---------------------------------------------------------------------------

output "rds_endpoint" {
  description = "DNS endpoint of the warehouse RDS instance."
  value       = aws_db_instance.dw.address
}

output "rds_port" {
  description = "TCP port of the warehouse RDS instance."
  value       = aws_db_instance.dw.port
}

output "rds_database_name" {
  description = "PostgreSQL database name created on the warehouse RDS instance."
  value       = aws_db_instance.dw.db_name
}

output "rds_secret_arn" {
  description = "ARN of the Secrets Manager record holding master credentials for the warehouse RDS instance."
  value       = aws_secretsmanager_secret.rds_master.arn
}

output "glue_jdbc_connection_name" {
  description = "Name of the AWS Glue JDBC Connection that targets the warehouse RDS instance."
  value       = aws_glue_connection.dw.name
}
