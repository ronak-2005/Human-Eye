# ============================================================
# HumanEye — RDS PostgreSQL 15 + ElastiCache Redis
# ============================================================

# ── RDS Subnet Group ──────────────────────────────────────
resource "aws_db_subnet_group" "main" {
  name       = "${var.app_name}-db-subnet-${var.environment}"
  subnet_ids = aws_subnet.private[*].id
  tags       = { Name = "${var.app_name}-db-subnet-group" }
}

# ── RDS Parameter Group ───────────────────────────────────
resource "aws_db_parameter_group" "postgres15" {
  family = "postgres15"
  name   = "${var.app_name}-pg15-${var.environment}"

  parameter {
    name  = "log_connections"
    value = "1"
  }
  parameter {
    name  = "log_disconnections"
    value = "1"
  }
  parameter {
    name  = "log_duration"
    value = "1"
  }
  parameter {
    name  = "log_min_duration_statement"
    value = "1000"  # Log queries taking > 1s
  }
}

# ── RDS PostgreSQL 15 (primary + replica) ────────────────
resource "aws_db_instance" "postgres" {
  identifier        = "${var.app_name}-postgres-${var.environment}"
  engine            = "postgres"
  engine_version    = "15.4"
  instance_class    = var.db_instance_class
  allocated_storage = var.db_allocated_storage
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = "humaneye"
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  parameter_group_name   = aws_db_parameter_group.postgres15.name

  # Backups
  backup_retention_period   = 7
  backup_window             = "03:00-04:00"
  maintenance_window        = "Mon:04:00-Mon:05:00"
  delete_automated_backups  = false
  deletion_protection       = var.environment == "production"
  skip_final_snapshot       = var.environment != "production"
  final_snapshot_identifier = "${var.app_name}-final-${var.environment}"

  # Monitoring
  enabled_cloudwatch_logs_exports       = ["postgresql", "upgrade"]
  performance_insights_enabled          = true
  performance_insights_retention_period = 7
  monitoring_interval                   = 60
  monitoring_role_arn                   = aws_iam_role.rds_monitoring.arn

  # Multi-AZ for production
  multi_az = var.environment == "production"

  tags = { Name = "${var.app_name}-postgres-${var.environment}" }
}

# Read replica for analytics/ML reads (production only)
resource "aws_db_instance" "postgres_replica" {
  count               = var.environment == "production" ? 1 : 0
  identifier          = "${var.app_name}-postgres-replica-${var.environment}"
  replicate_source_db = aws_db_instance.postgres.identifier
  instance_class      = var.db_instance_class
  storage_encrypted   = true
  skip_final_snapshot = true
  deletion_protection = false

  tags = { Name = "${var.app_name}-postgres-replica" }
}

# RDS monitoring role
resource "aws_iam_role" "rds_monitoring" {
  name = "${var.app_name}-rds-monitoring-${var.environment}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "monitoring.rds.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# ── ElastiCache Redis ─────────────────────────────────────
resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.app_name}-redis-subnet-${var.environment}"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "${var.app_name}-redis-${var.environment}"
  description          = "HumanEye Redis — rate limiting, sessions, cache"

  node_type            = var.redis_node_type
  num_cache_clusters   = var.environment == "production" ? 2 : 1
  port                 = 6379

  subnet_group_name          = aws_elasticache_subnet_group.main.name
  security_group_ids         = [aws_security_group.redis.id]

  at_rest_encryption_enabled  = true
  transit_encryption_enabled  = true

  # Auto failover for production
  automatic_failover_enabled = var.environment == "production"
  multi_az_enabled           = var.environment == "production"

  # Maintenance
  maintenance_window          = "sun:05:00-sun:06:00"
  snapshot_retention_limit    = 3
  snapshot_window             = "04:00-05:00"

  tags = { Name = "${var.app_name}-redis-${var.environment}" }
}
