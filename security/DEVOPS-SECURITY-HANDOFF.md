# Security Engineer → DevOps Handoff
**Owner: Security Engineer | For: DevOps Engineer**
**Status: Complete — implement these before any service is deployed**

---

## What This Document Contains

1. Every Vault secret path you need to bootstrap
2. The exact SOC 2 controls that require CloudTrail + VPC Flow Log configuration
3. AWS Config rules to enable from day one
4. The automated security verification script to run before every deploy

Read this once. Set it up once. It runs itself after that.

---

## PART 1: VAULT SECRET PATHS — BOOTSTRAP THESE FIRST

Before any service starts, these paths must exist in Vault.
Services will fail to start if Vault paths are missing.

### Path Structure

```
secret/humaneye/
├── production/
│   ├── database          ← PostgreSQL connection string
│   ├── redis             ← Redis connection
│   ├── jwt-secret        ← Dashboard session signing key
│   ├── internal-token    ← Backend → ML Engine auth token (rotate monthly)
│   └── aws-webhook-key   ← Optional: HMAC key for webhook signing
├── staging/
│   ├── database          ← Staging PostgreSQL (separate DB)
│   ├── redis
│   ├── jwt-secret
│   └── internal-token
└── models/               ← ML Engineer writes here; Security Engineer reads here
    ├── keystroke_v1      ← { sha256, signed_at, signed_by, mlflow_run_id }
    ├── mouse_v1
    ├── text_classifier_v1
    └── (phase 2+)
```

### Bootstrap Commands

Run these once during initial Vault setup. Use strong random values.

```bash
# ─── PRODUCTION SECRETS ───────────────────────────────────────────────────

# Database (update with actual RDS endpoint after Terraform creates it)
vault kv put secret/humaneye/production/database \
  url="postgresql://humaneye_app:CHANGE_ME@YOUR_RDS_ENDPOINT:5432/humaneye" \
  username="humaneye_app" \
  password="CHANGE_ME_USE_OPENSSL_RAND"

# Redis (update with actual ElastiCache endpoint)
vault kv put secret/humaneye/production/redis \
  url="redis://:CHANGE_ME@YOUR_ELASTICACHE_ENDPOINT:6379" \
  password="CHANGE_ME_USE_OPENSSL_RAND"

# JWT signing secret (64-byte random)
vault kv put secret/humaneye/production/jwt-secret \
  secret="$(openssl rand -base64 64)"

# Internal service token (backend → ML engine) — rotate monthly
vault kv put secret/humaneye/production/internal-token \
  token="$(openssl rand -base64 32)" \
  created_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  rotate_by="$(date -u -d '+30 days' +%Y-%m-%dT%H:%M:%SZ)"

# Webhook HMAC signing key
vault kv put secret/humaneye/production/aws-webhook-key \
  key="$(openssl rand -base64 32)"

# ─── STAGING SECRETS (same structure, different values) ──────────────────

vault kv put secret/humaneye/staging/database \
  url="postgresql://humaneye_app:CHANGE_ME@YOUR_STAGING_RDS:5432/humaneye_staging" \
  username="humaneye_app" \
  password="$(openssl rand -base64 32)"

vault kv put secret/humaneye/staging/redis \
  url="redis://:CHANGE_ME@YOUR_STAGING_REDIS:6379" \
  password="$(openssl rand -base64 24)"

vault kv put secret/humaneye/staging/jwt-secret \
  secret="$(openssl rand -base64 64)"

vault kv put secret/humaneye/staging/internal-token \
  token="$(openssl rand -base64 32)"

# ─── VERIFY ALL PATHS EXIST ──────────────────────────────────────────────

echo "=== Verifying Vault paths ==="
for path in \
  "secret/humaneye/production/database" \
  "secret/humaneye/production/redis" \
  "secret/humaneye/production/jwt-secret" \
  "secret/humaneye/production/internal-token" \
  "secret/humaneye/staging/database" \
  "secret/humaneye/staging/redis" \
  "secret/humaneye/staging/jwt-secret" \
  "secret/humaneye/staging/internal-token"; do
  
  if vault kv get "$path" > /dev/null 2>&1; then
    echo "  ✅ $path"
  else
    echo "  ❌ MISSING: $path"
  fi
done
```

### Vault Access Policies to Create

```hcl
# policies/humaneye-backend.hcl
path "secret/humaneye/production/database" { capabilities = ["read"] }
path "secret/humaneye/production/redis" { capabilities = ["read"] }
path "secret/humaneye/production/jwt-secret" { capabilities = ["read"] }
path "secret/humaneye/production/internal-token" { capabilities = ["read"] }
path "secret/humaneye/production/aws-webhook-key" { capabilities = ["read"] }

# policies/humaneye-ml-engine.hcl
path "secret/humaneye/production/internal-token" { capabilities = ["read"] }
path "secret/humaneye/models/*" { capabilities = ["read", "create", "update", "list"] }

# policies/humaneye-security-engineer.hcl
# Read-only access to all paths for audit
path "secret/humaneye/*" { capabilities = ["read", "list"] }
path "auth/*" { capabilities = ["read", "list"] }
path "sys/audit" { capabilities = ["read"] }
```

### Monthly Internal Token Rotation Reminder

The `internal-token` must be rotated every 30 days. Set a calendar reminder.

```bash
# Rotation procedure (takes 5 minutes):
# 1. Generate new token
NEW_TOKEN=$(openssl rand -base64 32)

# 2. Update Vault
vault kv put secret/humaneye/production/internal-token \
  token="$NEW_TOKEN" \
  created_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  rotate_by="$(date -u -d '+30 days' +%Y-%m-%dT%H:%M:%SZ)"

# 3. Force ECS task restart to pick up new token
aws ecs update-service --cluster humaneye-production --service backend --force-new-deployment
aws ecs update-service --cluster humaneye-production --service ml-engine --force-new-deployment

# 4. Verify both services healthy after restart
aws ecs wait services-stable --cluster humaneye-production --services backend ml-engine
echo "Token rotation complete"
```

---

## PART 2: SOC 2 CONTROLS — CLOUDTRAIL + VPC FLOW LOGS

### What SOC 2 Requires from Infrastructure

| SOC 2 Control | What It Requires | How to Implement |
|---|---|---|
| CC7.1 — Vulnerability detection | Continuous monitoring | CloudTrail + AWS Inspector |
| CC7.2 — Anomaly monitoring | Network anomaly detection | VPC Flow Logs + CloudWatch |
| CC6.1 — Logical access protection | All access logged | CloudTrail (all regions, all events) |
| CC8.1 — Change management | All infra changes logged | CloudTrail (management events) |
| CC6.3 — Access removal | Access revocation logged | CloudTrail IAM events |

### CloudTrail Configuration (Terraform)

```hcl
# terraform/cloudtrail.tf

# ─── AUDIT LOG BUCKET (Separate AWS account — immutable) ─────────────────
# This bucket is in a DIFFERENT AWS account from production.
# Even root in the production account cannot delete these logs.
resource "aws_s3_bucket" "audit_logs" {
  provider = aws.audit_account   # Separate account provider
  bucket   = "humaneye-audit-logs-${var.audit_account_id}"

  tags = {
    Purpose     = "SOC2-audit-evidence"
    Immutable   = "true"
    ManagedBy   = "security-engineer"
  }
}

resource "aws_s3_bucket_object_lock_configuration" "audit_logs" {
  provider = aws.audit_account
  bucket   = aws_s3_bucket.audit_logs.id

  rule {
    default_retention {
      mode = "COMPLIANCE"   # Cannot be overridden even by root
      days = 365            # 1 year minimum (SOC 2 requires 6 months observation + buffer)
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit_logs" {
  provider = aws.audit_account
  bucket   = aws_s3_bucket.audit_logs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

# ─── CLOUDTRAIL ───────────────────────────────────────────────────────────
resource "aws_cloudtrail" "humaneye_audit" {
  name                          = "humaneye-security-audit"
  s3_bucket_name                = aws_s3_bucket.audit_logs.id
  s3_key_prefix                 = "cloudtrail"
  include_global_service_events = true    # IAM, STS, etc.
  is_multi_region_trail         = true    # ALL regions — prevent blind spots
  enable_log_file_validation    = true    # Detect log tampering (SOC 2 evidence of log integrity)
  
  # CloudWatch Logs delivery (for real-time alerting)
  cloud_watch_logs_group_arn = "${aws_cloudwatch_log_group.cloudtrail.arn}:*"
  cloud_watch_logs_role_arn  = aws_iam_role.cloudtrail_cloudwatch.arn

  # ─ DATA EVENTS: Log specific S3 object access ──────────────────────────
  # SOC 2 CC7.2: Detect unauthorized model file access
  event_selector {
    read_write_type           = "All"
    include_management_events = true

    data_resource {
      type   = "AWS::S3::Object"
      values = ["arn:aws:s3:::humaneye-models/"]  # Every model file access logged
    }
  }

  # ─ INSIGHT EVENTS: Detect unusual API activity ─────────────────────────
  # Automatically detects spikes in API call rates (potential breach indicator)
  insight_selector {
    insight_type = "ApiCallRateInsight"
  }

  tags = {
    Purpose = "SOC2-CC6-CC7-CC8-evidence"
  }
}

# CloudWatch Log Group for real-time CloudTrail analysis
resource "aws_cloudwatch_log_group" "cloudtrail" {
  name              = "/aws/cloudtrail/humaneye"
  retention_in_days = 90    # CloudWatch: 90 days; S3: 365 days (cheaper long-term)
}
```

### VPC Flow Logs Configuration (Terraform)

```hcl
# terraform/vpc_flow_logs.tf

# ─── VPC FLOW LOGS ────────────────────────────────────────────────────────
# SOC 2 CC7.2: Network anomaly detection
# Captures all network traffic metadata for security analysis
# REQUIRED for: detecting ML engine making external calls, detecting data exfiltration

resource "aws_flow_log" "humaneye_vpc" {
  vpc_id          = aws_vpc.humaneye.id
  traffic_type    = "ALL"   # ACCEPTED + REJECTED — need both for security analysis
  iam_role_arn    = aws_iam_role.vpc_flow_logs.arn
  log_destination = aws_cloudwatch_log_group.vpc_flow_logs.arn
  log_format      = "$${version} $${account-id} $${interface-id} $${srcaddr} $${dstaddr} $${srcport} $${dstport} $${protocol} $${packets} $${bytes} $${start} $${end} $${action} $${log-status} $${vpc-id} $${subnet-id} $${instance-id} $${tcp-flags} $${type} $${pkt-srcaddr} $${pkt-dstaddr}"
}

resource "aws_cloudwatch_log_group" "vpc_flow_logs" {
  name              = "/aws/vpc/humaneye-flow-logs"
  retention_in_days = 90
}
```

### CloudWatch Metric Filters (Security Alerts)

These turn CloudTrail + VPC Flow Log events into alertable metrics.
**Security Engineer receives ALL of these alerts — configure SNS to Security Engineer's contact.**

```hcl
# terraform/security_alerts.tf

locals {
  # Change this to actual Security Engineer contact
  security_engineer_email = "security@humaneye.io"
}

resource "aws_sns_topic" "security_alerts" {
  name = "humaneye-security-alerts"
}

resource "aws_sns_topic_subscription" "security_engineer" {
  topic_arn = aws_sns_topic.security_alerts.arn
  protocol  = "email"
  endpoint  = local.security_engineer_email
}

# ─── ALERT 1: Root account login ─────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "root_login" {
  alarm_name          = "SECURITY-root-account-login"
  alarm_description   = "P0: Root account was used to log in"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "RootAccountLogin"
  namespace           = "HumanEye/Security"
  period              = 60
  statistic           = "Sum"
  threshold           = 1
  alarm_actions       = [aws_sns_topic.security_alerts.arn]
}

resource "aws_cloudwatch_log_metric_filter" "root_login" {
  name           = "root-account-login"
  log_group_name = aws_cloudwatch_log_group.cloudtrail.name
  pattern        = "{ $.userIdentity.type = \"Root\" && $.userIdentity.invokedBy NOT EXISTS && $.eventType != \"AwsServiceEvent\" }"

  metric_transformation {
    name      = "RootAccountLogin"
    namespace = "HumanEye/Security"
    value     = "1"
  }
}

# ─── ALERT 2: CloudTrail disabled ────────────────────────────────────────
resource "aws_cloudwatch_log_metric_filter" "cloudtrail_disabled" {
  name           = "cloudtrail-disabled"
  log_group_name = aws_cloudwatch_log_group.cloudtrail.name
  pattern        = "{ ($.eventName = StopLogging) || ($.eventName = DeleteTrail) || ($.eventName = UpdateTrail) }"

  metric_transformation {
    name      = "CloudTrailDisabled"
    namespace = "HumanEye/Security"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "cloudtrail_disabled" {
  alarm_name          = "SECURITY-cloudtrail-disabled"
  alarm_description   = "P0: CloudTrail logging was disabled or modified"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "CloudTrailDisabled"
  namespace           = "HumanEye/Security"
  period              = 60
  statistic           = "Sum"
  threshold           = 1
  alarm_actions       = [aws_sns_topic.security_alerts.arn]
}

# ─── ALERT 3: Security group change ──────────────────────────────────────
resource "aws_cloudwatch_log_metric_filter" "sg_change" {
  name           = "security-group-change"
  log_group_name = aws_cloudwatch_log_group.cloudtrail.name
  pattern        = "{ ($.eventName = AuthorizeSecurityGroupIngress) || ($.eventName = AuthorizeSecurityGroupEgress) || ($.eventName = RevokeSecurityGroupIngress) || ($.eventName = CreateSecurityGroup) || ($.eventName = DeleteSecurityGroup) }"

  metric_transformation {
    name      = "SecurityGroupChange"
    namespace = "HumanEye/Security"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "sg_change" {
  alarm_name          = "SECURITY-security-group-changed"
  alarm_description   = "P1: Security group was modified — verify ML engine port 8001 not exposed"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "SecurityGroupChange"
  namespace           = "HumanEye/Security"
  period              = 60
  statistic           = "Sum"
  threshold           = 1
  alarm_actions       = [aws_sns_topic.security_alerts.arn]
}

# ─── ALERT 4: IAM policy change ──────────────────────────────────────────
resource "aws_cloudwatch_log_metric_filter" "iam_change" {
  name           = "iam-policy-change"
  log_group_name = aws_cloudwatch_log_group.cloudtrail.name
  pattern        = "{ ($.eventName=DeleteGroupPolicy) || ($.eventName=DeleteRolePolicy) || ($.eventName=DeleteUserPolicy) || ($.eventName=PutGroupPolicy) || ($.eventName=PutRolePolicy) || ($.eventName=PutUserPolicy) || ($.eventName=CreatePolicy) || ($.eventName=DeletePolicy) || ($.eventName=AttachRolePolicy) || ($.eventName=DetachRolePolicy) }"

  metric_transformation {
    name      = "IAMPolicyChange"
    namespace = "HumanEye/Security"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "iam_change" {
  alarm_name          = "SECURITY-iam-policy-changed"
  alarm_description   = "P1: IAM policy was created or modified"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "IAMPolicyChange"
  namespace           = "HumanEye/Security"
  period              = 60
  statistic           = "Sum"
  threshold           = 1
  alarm_actions       = [aws_sns_topic.security_alerts.arn]
}

# ─── ALERT 5: ML engine outbound internet traffic (VPC Flow Logs) ────────
# This catches if ML engine makes any external HTTP call (violates security contract)
resource "aws_cloudwatch_log_metric_filter" "ml_outbound_internet" {
  name           = "ml-engine-outbound-internet"
  log_group_name = aws_cloudwatch_log_group.vpc_flow_logs.name
  # Source: ML engine subnet, Destination: NOT internal, Action: ACCEPT
  # Adjust subnet CIDR to match actual ML engine subnet
  pattern        = "[version, accountid, interfaceid, srcaddr=10.0.10.*, dstaddr!=10.0.*, dstaddr!=192.168.*, dstaddr!=172.16.*, srcport, dstport, protocol, packets, bytes, start, end, action=ACCEPT, logstatus]"

  metric_transformation {
    name      = "MLEngineOutboundInternet"
    namespace = "HumanEye/Security"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "ml_outbound_internet" {
  alarm_name          = "SECURITY-ml-engine-external-call"
  alarm_description   = "P1: ML engine made outbound internet connection — violates no-external-calls policy"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "MLEngineOutboundInternet"
  namespace           = "HumanEye/Security"
  period              = 60
  statistic           = "Sum"
  threshold           = 1
  alarm_actions       = [aws_sns_topic.security_alerts.arn]
}

# ─── ALERT 6: S3 model bucket unauthorized access ────────────────────────
resource "aws_cloudwatch_log_metric_filter" "model_bucket_access" {
  name           = "model-bucket-access"
  log_group_name = aws_cloudwatch_log_group.cloudtrail.name
  # Any access to model files outside of the ML engine task role
  pattern        = "{ ($.eventSource = s3.amazonaws.com) && ($.requestParameters.bucketName = humaneye-models) && ($.userIdentity.arn != \"*humaneye-ml-engine-role*\") && ($.userIdentity.arn != \"*humaneye-devops-deploy-role*\") }"

  metric_transformation {
    name      = "ModelBucketUnauthorizedAccess"
    namespace = "HumanEye/Security"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "model_bucket_access" {
  alarm_name          = "SECURITY-model-bucket-unexpected-access"
  alarm_description   = "P1: Model files accessed by unexpected identity"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "ModelBucketUnauthorizedAccess"
  namespace           = "HumanEye/Security"
  period              = 300   # 5-minute window
  statistic           = "Sum"
  threshold           = 1
  alarm_actions       = [aws_sns_topic.security_alerts.arn]
}
```

---

## PART 3: AWS CONFIG RULES

Enable these rules on Day 1. They provide continuous compliance checking.
Each maps to a SOC 2 control. Security Engineer reviews compliance status monthly.

```hcl
# terraform/aws_config.tf

resource "aws_config_config_rule" "encrypted_volumes" {
  name        = "encrypted-volumes"
  description = "SOC2 CC6.7: All EBS volumes encrypted at rest"
  source {
    owner             = "AWS"
    source_identifier = "ENCRYPTED_VOLUMES"
  }
}

resource "aws_config_config_rule" "rds_encrypted" {
  name        = "rds-storage-encrypted"
  description = "SOC2 CC6.7: All RDS instances encrypted at rest"
  source {
    owner             = "AWS"
    source_identifier = "RDS_STORAGE_ENCRYPTED"
  }
}

resource "aws_config_config_rule" "s3_no_public_access" {
  name        = "s3-bucket-level-public-access-prohibited"
  description = "SOC2 CC6.1: No S3 buckets publicly accessible"
  source {
    owner             = "AWS"
    source_identifier = "S3_BUCKET_LEVEL_PUBLIC_ACCESS_PROHIBITED"
  }
}

resource "aws_config_config_rule" "mfa_enabled_root" {
  name        = "root-account-mfa-enabled"
  description = "SOC2 CC6.1: Root account MFA required"
  source {
    owner             = "AWS"
    source_identifier = "ROOT_ACCOUNT_MFA_ENABLED"
  }
}

resource "aws_config_config_rule" "iam_no_wildcard" {
  name        = "iam-no-inline-policy-check"
  description = "SOC2 CC6.6: No inline IAM policies (all policies must be managed)"
  source {
    owner             = "AWS"
    source_identifier = "IAM_NO_INLINE_POLICY_CHECK"
  }
}

resource "aws_config_config_rule" "cloudtrail_enabled" {
  name        = "cloud-trail-enabled"
  description = "SOC2 CC7.2: CloudTrail must be enabled"
  source {
    owner             = "AWS"
    source_identifier = "CLOUD_TRAIL_ENABLED"
  }
}

resource "aws_config_config_rule" "vpc_flow_logs_enabled" {
  name        = "vpc-flow-logs-enabled"
  description = "SOC2 CC7.2: VPC flow logs must be enabled"
  source {
    owner             = "AWS"
    source_identifier = "VPC_FLOW_LOGS_ENABLED"
  }
}

resource "aws_config_config_rule" "restricted_ssh" {
  name        = "restricted-ssh"
  description = "SOC2 CC6.1: No security groups allow unrestricted SSH"
  source {
    owner             = "AWS"
    source_identifier = "INCOMING_SSH_DISABLED"
  }
}
```

---

## PART 4: PRE-DEPLOY SECURITY VERIFICATION SCRIPT

Run this before every production deployment. It's the gate check.

```bash
# security/scripts/pre-deploy-verify.sh
#!/bin/bash
set -e

echo "═══════════════════════════════════════════════"
echo "HumanEye Pre-Deploy Security Verification"
echo "═══════════════════════════════════════════════"

PASS=0
FAIL=0

check() {
  local name="$1"
  local result="$2"
  if [ "$result" = "pass" ]; then
    echo "  ✅ $name"
    PASS=$((PASS+1))
  else
    echo "  ❌ FAIL: $name"
    FAIL=$((FAIL+1))
  fi
}

# 1. ML Engine not publicly accessible
ML_PUBLIC=$(aws ec2 describe-security-groups --group-ids $ML_ENGINE_SG_ID \
  --query "SecurityGroups[0].IpPermissions[?FromPort==\`8001\`].IpRanges[?CidrIp==\`0.0.0.0/0\`]" \
  --output text 2>/dev/null)
[ -z "$ML_PUBLIC" ] && check "ML Engine port 8001 not public" "pass" || check "ML Engine port 8001 not public" "FAIL"

# 2. Database not publicly accessible
DB_PUBLIC=$(aws ec2 describe-security-groups --group-ids $DATABASE_SG_ID \
  --query "SecurityGroups[0].IpPermissions[?FromPort==\`5432\`].IpRanges[?CidrIp==\`0.0.0.0/0\`]" \
  --output text 2>/dev/null)
[ -z "$DB_PUBLIC" ] && check "Database port 5432 not public" "pass" || check "Database port 5432 not public" "FAIL"

# 3. All Vault paths exist
for path in "production/database" "production/redis" "production/jwt-secret" "production/internal-token"; do
  vault kv get "secret/humaneye/$path" > /dev/null 2>&1 \
    && check "Vault: $path" "pass" \
    || check "Vault: $path" "FAIL"
done

# 4. CloudTrail is active
TRAIL_STATUS=$(aws cloudtrail get-trail-status --name humaneye-security-audit \
  --query 'IsLogging' --output text 2>/dev/null)
[ "$TRAIL_STATUS" = "True" ] && check "CloudTrail active" "pass" || check "CloudTrail active" "FAIL"

# 5. RDS encryption
RDS_ENCRYPTED=$(aws rds describe-db-instances --db-instance-identifier humaneye-postgres \
  --query 'DBInstances[0].StorageEncrypted' --output text 2>/dev/null)
[ "$RDS_ENCRYPTED" = "True" ] && check "RDS encrypted at rest" "pass" || check "RDS encrypted at rest" "FAIL"

# 6. Model integrity (if deploying ML engine)
if [ "$DEPLOY_ML_ENGINE" = "true" ]; then
  python security/scripts/model-verify.py verify-all ml_engine/saved_models/ \
    && check "All model integrity verified" "pass" \
    || check "All model integrity verified" "FAIL"
fi

# 7. Security scanner clean
python security/scripts/api-key-audit.py backend/ ml_engine/ sdk/ \
  && check "Security scanner clean" "pass" \
  || check "Security scanner clean" "FAIL"

echo ""
echo "═══════════════════════════════════════════════"
echo "Results: $PASS pass, $FAIL fail"

if [ "$FAIL" -gt 0 ]; then
  echo "❌ DEPLOYMENT BLOCKED — $FAIL security checks failed"
  echo "Notify Security Engineer before proceeding."
  exit 1
else
  echo "✅ ALL CHECKS PASSED — deployment may proceed"
  exit 0
fi
```

---

## SOC 2 Evidence You Produce (Security Engineer Collects Monthly)

| What You Configure | SOC 2 Control | Evidence Type |
|---|---|---|
| CloudTrail to immutable S3 | CC8.1 (change mgmt) + CC6.1 (access) | Log delivery records |
| VPC Flow Logs | CC7.2 (anomaly monitoring) | Flow log records |
| AWS Config rules | CC7.1 (vulnerability detection) | Compliance reports |
| CloudWatch security alerts | CC7.3 (alert evaluation) | Alert history |
| Multi-AZ RDS + automated backups | CC2 (availability) | RDS backup records |

**How to give Security Engineer access to this evidence:**
```bash
# Security Engineer's IAM role (humaneye-security-engineer-role) has read access to:
# - CloudTrail logs in audit S3 bucket
# - CloudWatch metrics and alarms
# - AWS Config compliance reports
# - VPC Flow Log groups

# Security Engineer does NOT need console access —
# they query via CLI using their role
```

---

*Questions on any of these configurations: contact Security Engineer before implementing.*
*Do not skip CloudTrail or VPC Flow Logs — they are the foundation of SOC 2 evidence collection.*
