# ============================================================
# HumanEye — ECS Fargate Services
# Backend (port 8000) + ML Engine (port 8001, internal only)
# ============================================================

# ── ECR Repositories ──────────────────────────────────────
resource "aws_ecr_repository" "backend" {
  name                 = "${var.app_name}/backend"
  image_tag_mutability = var.ecr_image_tag_mutability
  image_scanning_configuration { scan_on_push = true }
  tags = { Name = "${var.app_name}-backend-ecr" }
}

resource "aws_ecr_repository" "ml_engine" {
  name                 = "${var.app_name}/ml-engine"
  image_tag_mutability = var.ecr_image_tag_mutability
  image_scanning_configuration { scan_on_push = true }
  tags = { Name = "${var.app_name}-ml-engine-ecr" }
}

resource "aws_ecr_repository" "dashboard" {
  name                 = "${var.app_name}/dashboard"
  image_tag_mutability = var.ecr_image_tag_mutability
  image_scanning_configuration { scan_on_push = true }
  tags = { Name = "${var.app_name}-dashboard-ecr" }
}

# ── ECS Cluster ───────────────────────────────────────────
resource "aws_ecs_cluster" "main" {
  name = "${var.app_name}-cluster-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name       = aws_ecs_cluster.main.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    base              = 1
    weight            = 100
    capacity_provider = "FARGATE"
  }
}

# ── IAM Role for ECS tasks ────────────────────────────────
resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.app_name}-ecs-task-execution-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Allow reading secrets from SSM/Secrets Manager
resource "aws_iam_role_policy" "ecs_secrets" {
  name = "${var.app_name}-ecs-secrets-${var.environment}"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue", "ssm:GetParameters"]
        Resource = [
          "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.app_name}/*"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject"]
        Resource = ["${aws_s3_bucket.models.arn}/*", "${aws_s3_bucket.logs.arn}/*"]
      }
    ]
  })
}

# ── CloudWatch Log Groups ─────────────────────────────────
resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${var.app_name}/backend"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "ml_engine" {
  name              = "/ecs/${var.app_name}/ml-engine"
  retention_in_days = 30
}

# ── Backend Task Definition ───────────────────────────────
resource "aws_ecs_task_definition" "backend" {
  family                   = "${var.app_name}-backend-${var.environment}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.backend_cpu
  memory                   = var.backend_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task_execution.arn

  container_definitions = jsonencode([{
    name      = "backend"
    image     = "${aws_ecr_repository.backend.repository_url}:latest"
    essential = true

    portMappings = [{
      containerPort = 8000
      hostPort      = 8000
      protocol      = "tcp"
    }]

    environment = [
      { name = "ENV",            value = var.environment },
      { name = "ML_ENGINE_URL",  value = "http://${aws_service_discovery_service.ml_engine.name}.${var.app_name}.local:8001" }
    ]

    secrets = [
      { name = "DATABASE_URL",   valueFrom = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.app_name}/database-url" },
      { name = "REDIS_URL",      valueFrom = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.app_name}/redis-url" },
      { name = "SECRET_KEY",     valueFrom = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.app_name}/secret-key" }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.backend.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "backend"
      }
    }

    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:8000/api/v1/health || exit 1"]
      interval    = 10
      timeout     = 5
      retries     = 3
      startPeriod = 30
    }
  }])
}

# ── Backend ECS Service ───────────────────────────────────
resource "aws_ecs_service" "backend" {
  name                               = "${var.app_name}-backend-${var.environment}"
  cluster                            = aws_ecs_cluster.main.id
  task_definition                    = aws_ecs_task_definition.backend.arn
  desired_count                      = var.backend_desired_count
  launch_type                        = "FARGATE"
  health_check_grace_period_seconds  = 30

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.backend.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "backend"
    container_port   = 8000
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  deployment_controller { type = "ECS" }

  depends_on = [aws_lb_listener.https]
}

# ── ML Engine Task Definition ─────────────────────────────
# Resource limits per ML engineer specification:
#   Phase 1 CPU: 2 vCPU request / 4 vCPU limit  → ECS: cpu=4096 (Fargate bills on reservation)
#   Memory      : 4 GB request  / 8 GB limit     → ECS: memory=8192
#   HuggingFace models are memory-hungry — 8 GB is non-negotiable
# ─────────────────────────────────────────────────────────
resource "aws_ecs_task_definition" "ml_engine" {
  family                   = "${var.app_name}-ml-engine-${var.environment}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 4096   # 4 vCPU  (ML spec: 2 req / 4 limit → reserve max)
  memory                   = 8192   # 8 GB    (ML spec: 4 req / 8 limit → reserve max)
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task_execution.arn

  # EFS volume for persistent model storage
  # Models must survive container restarts — not wiped on task replacement
  volume {
    name = "ml-model-store"
    efs_volume_configuration {
      file_system_id          = aws_efs_file_system.ml_models.id
      root_directory          = "/models"
      transit_encryption      = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.ml_models.id
        iam             = "ENABLED"
      }
    }
  }

  container_definitions = jsonencode([{
    name      = "ml-engine"
    image     = "${aws_ecr_repository.ml_engine.repository_url}:latest"
    essential = true

    # Port 8001: INTERNAL ONLY — security group blocks all external access
    portMappings = [{
      containerPort = 8001
      hostPort      = 8001
      protocol      = "tcp"
    }]

    # All env vars specified by ML engineer
    environment = [
      { name = "ML_ENGINE_PORT",       value = "8001" },
      { name = "ML_ENGINE_WORKERS",    value = "2" },
      { name = "ML_TRACKING_URI",      value = "http://mlflow.${var.app_name}.local:5000" },
      { name = "TRANSFORMERS_CACHE",   value = "/app/.cache/huggingface" },
      { name = "MODEL_DIR",            value = "/app/ml_engine/saved_models" },
      { name = "LOG_LEVEL",            value = "INFO" },
      { name = "ENVIRONMENT",          value = var.environment },
      { name = "S3_BUCKET",            value = aws_s3_bucket.models.bucket },
      { name = "TORCH_HOME",           value = "/app/ml_engine/saved_models/.torch_cache" }
    ]

    secrets = [
      { name = "TIMESCALE_URL",   valueFrom = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.app_name}/timescale-url" },
      { name = "REDIS_URL",       valueFrom = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.app_name}/redis-url" },
      { name = "PINECONE_API_KEY",valueFrom = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.app_name}/pinecone-api-key" }
    ]

    # Persistent volume mount — models survive container restarts
    mountPoints = [{
      sourceVolume  = "ml-model-store"
      containerPath = "/app/ml_engine/saved_models"
      readOnly      = false
    }]

    # ML logs to stdout as structured JSON — CloudWatch ships it
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.ml_engine.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "ml-engine"
      }
    }

    # ML engineer spec:
    #   liveness:  GET /health, timeout 10s, period 30s
    #   readiness: GET /health, check phase1_ready=true
    #   startup delay: ~30s model loading → startPeriod=45s
    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:8001/health || exit 1"]
      interval    = 30       # ML spec: period 30s
      timeout     = 10       # ML spec: timeout 10s
      retries     = 3
      startPeriod = 45       # ML spec: ~30s startup → 45s grace period
    }
  }])
}

# ── EFS for persistent ML model storage ──────────────────
# Models must not be wiped on container restart
resource "aws_efs_file_system" "ml_models" {
  creation_token   = "${var.app_name}-ml-models-${var.environment}"
  encrypted        = true
  performance_mode = "generalPurpose"
  throughput_mode  = "bursting"

  tags = { Name = "${var.app_name}-ml-models-efs-${var.environment}" }
}

resource "aws_efs_access_point" "ml_models" {
  file_system_id = aws_efs_file_system.ml_models.id

  posix_user {
    gid = 1000
    uid = 1000
  }

  root_directory {
    path = "/models"
    creation_info {
      owner_gid   = 1000
      owner_uid   = 1000
      permissions = "755"
    }
  }

  tags = { Name = "${var.app_name}-ml-models-ap" }
}

resource "aws_efs_mount_target" "ml_models" {
  count           = length(aws_subnet.private)
  file_system_id  = aws_efs_file_system.ml_models.id
  subnet_id       = aws_subnet.private[count.index].id
  security_groups = [aws_security_group.efs.id]
}

resource "aws_security_group" "efs" {
  name        = "${var.app_name}-efs-sg-${var.environment}"
  description = "EFS — allow NFS from ML engine only"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [aws_security_group.ml_engine.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ── ML Engine Service (internal only — no ALB) ────────────
resource "aws_ecs_service" "ml_engine" {
  name            = "${var.app_name}-ml-engine-${var.environment}"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.ml_engine.arn
  desired_count   = var.ml_engine_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ml_engine.id]
    assign_public_ip = false
  }

  service_registries {
    registry_arn = aws_service_discovery_service.ml_engine.arn
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
}

# ── Service Discovery (backend → ml_engine via DNS) ───────
resource "aws_service_discovery_private_dns_namespace" "main" {
  name        = "${var.app_name}.local"
  description = "HumanEye internal service mesh"
  vpc         = aws_vpc.main.id
}

resource "aws_service_discovery_service" "ml_engine" {
  name = "ml-engine"
  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.main.id
    dns_records {
      ttl  = 10
      type = "A"
    }
    routing_policy = "MULTIVALUE"
  }
  health_check_custom_config { failure_threshold = 1 }
}

# ── Auto-scaling — Backend ─────────────────────────────────
resource "aws_appautoscaling_target" "backend" {
  max_capacity       = 10
  min_capacity       = 2
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.backend.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "backend_cpu" {
  name               = "${var.app_name}-backend-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.backend.resource_id
  scalable_dimension = aws_appautoscaling_target.backend.scalable_dimension
  service_namespace  = aws_appautoscaling_target.backend.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value = 70.0
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}
