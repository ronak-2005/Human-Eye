# ============================================================
# HumanEye — Production Environment Values
# Usage: terraform apply -var-file=production.tfvars
# ============================================================

environment             = "production"
aws_region              = "us-east-1"
app_name                = "humaneye"

# Networking
vpc_cidr                = "10.1.0.0/16"
public_subnet_cidrs     = ["10.1.1.0/24", "10.1.2.0/24"]
private_subnet_cidrs    = ["10.1.10.0/24", "10.1.11.0/24"]

# ECS — production sizing
backend_cpu             = 512
backend_memory          = 1024
backend_desired_count   = 2

ml_engine_cpu           = 1024
ml_engine_memory        = 2048
ml_engine_desired_count = 1

# RDS — multi-AZ, larger storage
db_instance_class       = "db.t3.medium"
db_allocated_storage    = 20

# Redis — replicated
redis_node_type         = "cache.t3.small"

# Domain
domain_name             = "humaneye.io"
