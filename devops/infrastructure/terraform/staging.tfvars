# ============================================================
# HumanEye — Staging Environment Values
# Usage: terraform apply -var-file=staging.tfvars
# ============================================================

environment             = "staging"
aws_region              = "us-east-1"
app_name                = "humaneye"

# Networking
vpc_cidr                = "10.0.0.0/16"
public_subnet_cidrs     = ["10.0.1.0/24", "10.0.2.0/24"]
private_subnet_cidrs    = ["10.0.10.0/24", "10.0.11.0/24"]

# ECS — smaller than prod
backend_cpu             = 256
backend_memory          = 512
backend_desired_count   = 1

ml_engine_cpu           = 512
ml_engine_memory        = 1024
ml_engine_desired_count = 1

# RDS — small for staging
db_instance_class       = "db.t3.micro"
db_allocated_storage    = 10

# Redis — minimal
redis_node_type         = "cache.t3.micro"

# Domain
domain_name             = "humaneye.io"
