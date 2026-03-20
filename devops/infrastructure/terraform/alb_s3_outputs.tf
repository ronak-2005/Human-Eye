# ============================================================
# HumanEye — ALB, S3, CloudWatch Alarms, Outputs
# ============================================================

# ── Application Load Balancer ─────────────────────────────
resource "aws_lb" "main" {
  name               = "${var.app_name}-alb-${var.environment}"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  enable_deletion_protection = var.environment == "production"

  access_logs {
    bucket  = aws_s3_bucket.logs.id
    prefix  = "alb-logs"
    enabled = true
  }
}

# ── Target Group — Backend ────────────────────────────────
resource "aws_lb_target_group" "backend" {
  name        = "${var.app_name}-backend-tg-${var.environment}"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    enabled             = true
    path                = "/api/v1/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 10
    matcher             = "200"
  }

  deregistration_delay = 30
}

# ── ACM Certificate ───────────────────────────────────────
resource "aws_acm_certificate" "main" {
  domain_name               = var.domain_name
  subject_alternative_names = ["*.${var.domain_name}"]
  validation_method         = "DNS"

  lifecycle { create_before_destroy = true }
}

# ── ALB Listeners ─────────────────────────────────────────
resource "aws_lb_listener" "http_redirect" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate.main.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }
}

# ── ALB Listener Rules ────────────────────────────────────
resource "aws_lb_listener_rule" "api" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }

  condition {
    path_pattern { values = ["/api/*"] }
  }
}

# ── S3 Buckets ────────────────────────────────────────────
resource "aws_s3_bucket" "models" {
  bucket = "${var.app_name}-models-${var.environment}-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_versioning" "models" {
  bucket = aws_s3_bucket.models.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "models" {
  bucket = aws_s3_bucket.models.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_s3_bucket" "sdk_cdn" {
  bucket = "${var.app_name}-sdk-${var.environment}-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket" "logs" {
  bucket        = "${var.app_name}-logs-${var.environment}-${data.aws_caller_identity.current.account_id}"
  force_destroy = var.environment != "production"
}

resource "aws_s3_bucket_lifecycle_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id
  rule {
    id     = "expire-old-logs"
    status = "Enabled"
    expiration { days = 90 }
  }
}

# ── CloudWatch Alarms ─────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "backend_p95_latency" {
  alarm_name          = "${var.app_name}-backend-p95-latency-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = "60"
  statistic           = "p95"
  threshold           = "0.5"
  alarm_description   = "P95 latency > 500ms — investigate backend"
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
    TargetGroup  = aws_lb_target_group.backend.arn_suffix
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "backend_5xx_rate" {
  alarm_name          = "${var.app_name}-backend-5xx-rate-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = "60"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "5xx errors > 10 in 1 minute"

  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
    TargetGroup  = aws_lb_target_group.backend.arn_suffix
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "redis_memory" {
  alarm_name          = "${var.app_name}-redis-memory-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DatabaseMemoryUsagePercentage"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "Redis memory > 80%"

  dimensions = {
    ReplicationGroupId = aws_elasticache_replication_group.redis.id
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
}

# ── SNS Alert Topic ───────────────────────────────────────
resource "aws_sns_topic" "alerts" {
  name = "${var.app_name}-alerts-${var.environment}"
}

# ── Outputs ───────────────────────────────────────────────
output "alb_dns_name" {
  description = "ALB DNS — point Cloudflare CNAME here"
  value       = aws_lb.main.dns_name
}

output "ecr_backend_url" {
  description = "ECR URL for backend image pushes"
  value       = aws_ecr_repository.backend.repository_url
}

output "ecr_ml_engine_url" {
  description = "ECR URL for ML engine image pushes"
  value       = aws_ecr_repository.ml_engine.repository_url
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint (give to backend engineer)"
  value       = aws_db_instance.postgres.endpoint
  sensitive   = true
}

output "redis_endpoint" {
  description = "ElastiCache Redis endpoint (give to backend engineer)"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
  sensitive   = true
}

output "s3_models_bucket" {
  description = "S3 bucket for ML model files (give to ML engineer)"
  value       = aws_s3_bucket.models.id
}

output "s3_sdk_cdn_bucket" {
  description = "S3 bucket for browser SDK CDN distribution"
  value       = aws_s3_bucket.sdk_cdn.id
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}
