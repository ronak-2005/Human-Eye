# ============================================================
# HumanEye — Terraform Root
# AWS Provider + S3 Remote State Backend
# ============================================================

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
    }
  }

  # Remote state — create this S3 bucket + DynamoDB table manually once
  backend "s3" {
    bucket         = "humaneye-terraform-state"
    key            = "humaneye/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "humaneye-terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "HumanEye"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# ── Data sources ──────────────────────────────────────────
data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}
