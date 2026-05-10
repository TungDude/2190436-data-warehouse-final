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
