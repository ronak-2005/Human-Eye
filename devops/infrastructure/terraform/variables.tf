# ============================================================
# HumanEye — Terraform Variables
# ============================================================

variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment: staging | production"
  type        = string
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "Environment must be staging or production."
  }
}

variable "app_name" {
  description = "Application name prefix for all resources"
  type        = string
  default     = "humaneye"
}

# ── Networking ────────────────────────────────────────────
variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "Public subnets (ALB, NAT gateways)"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "Private subnets (ECS tasks, RDS, ElastiCache)"
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.11.0/24"]
}

# ── ECS ───────────────────────────────────────────────────
variable "backend_cpu" {
  description = "ECS Fargate CPU units for backend (1024 = 1 vCPU)"
  type        = number
  default     = 512
}

variable "backend_memory" {
  description = "ECS Fargate memory (MB) for backend"
  type        = number
  default     = 1024
}

variable "backend_desired_count" {
  description = "Number of backend ECS tasks"
  type        = number
  default     = 2
}

variable "ml_engine_cpu" {
  description = "ECS Fargate CPU for ML engine"
  type        = number
  default     = 1024
}

variable "ml_engine_memory" {
  description = "ECS Fargate memory (MB) for ML engine"
  type        = number
  default     = 2048
}

variable "ml_engine_desired_count" {
  description = "Number of ML engine ECS tasks"
  type        = number
  default     = 1
}

# ── RDS ───────────────────────────────────────────────────
variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.medium"
}

variable "db_allocated_storage" {
  description = "RDS storage in GB"
  type        = number
  default     = 20
}

variable "db_username" {
  description = "RDS master username"
  type        = string
  default     = "humaneye"
  sensitive   = true
}

variable "db_password" {
  description = "RDS master password — set via TF_VAR_db_password env var or Vault"
  type        = string
  sensitive   = true
}

# ── ElastiCache ───────────────────────────────────────────
variable "redis_node_type" {
  description = "ElastiCache Redis node type"
  type        = string
  default     = "cache.t3.micro"
}

# ── Cloudflare ────────────────────────────────────────────
variable "domain_name" {
  description = "Primary domain (e.g. humaneye.io)"
  type        = string
  default     = "humaneye.io"
}

# ── ECR ───────────────────────────────────────────────────
variable "ecr_image_tag_mutability" {
  type    = string
  default = "MUTABLE"
}
