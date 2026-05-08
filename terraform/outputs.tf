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
  description = "EventBridge Scheduler schedule name."
  value       = aws_scheduler_schedule.daily_fetch_chicago_crime.name
}
