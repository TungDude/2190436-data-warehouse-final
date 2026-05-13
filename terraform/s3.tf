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

resource "aws_s3_object" "silver_prefix" {
  bucket       = aws_s3_bucket.raw.id
  key          = "${var.silver_prefix}/"
  content      = ""
  content_type = "application/x-directory"
}

resource "aws_s3_object" "glue_scripts_prefix" {
  bucket       = aws_s3_bucket.raw.id
  key          = "${var.glue_scripts_prefix}/"
  content      = ""
  content_type = "application/x-directory"
}
