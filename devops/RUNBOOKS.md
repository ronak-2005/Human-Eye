# HumanEye — On-Call Runbooks

Every alert has a runbook here. Engineers resolve incidents from this doc — no 3am calls.

---

## RB-001 — P95 API Latency > 500ms

**Alert:** `humaneye-backend-p95-latency`
**Severity:** High
**SLA impact:** Breaches <200ms P95 requirement

### Diagnose
```bash
# 1. Check current latency in Grafana
open http://localhost:3001

# 2. Check backend ECS task CPU/memory
aws ecs describe-services \
  --cluster humaneye-cluster-production \
  --services humaneye-backend-production

# 3. Check slow DB queries
make db-shell
# Then run:
SELECT query, calls, total_exec_time/calls AS avg_ms
FROM pg_stat_statements
ORDER BY avg_ms DESC LIMIT 10;

# 4. Check ML engine latency
curl http://localhost:8001/metrics | grep inference_duration

# 5. Check Redis latency
redis-cli --latency -h $REDIS_HOST
```

### Most likely causes + fixes

| Cause | Fix |
|---|---|
| DB slow query | Add index, optimize query. Notify backend engineer. |
| ML engine overloaded | Scale up ECS task count: `aws ecs update-service --desired-count 2` |
| Memory pressure | Check ECS task memory. Scale up task definition memory. |
| Redis cold cache after deploy | Wait 2 min for cache to warm up |
| Traffic spike | ECS auto-scaling should handle — check if scaled out yet |

### Escalate if
Not resolved in 15 min → page backend engineer.

---

## RB-002 — 5xx Error Rate > 1%

**Alert:** `humaneye-backend-5xx-rate`
**Severity:** Critical
**SLA impact:** Customer verifications failing

### Diagnose
```bash
# 1. Check CloudWatch logs immediately
aws logs tail /ecs/humaneye/backend --follow

# 2. Check recent deployments
aws ecs describe-services \
  --cluster humaneye-cluster-production \
  --services humaneye-backend-production \
  --query 'services[0].deployments'

# 3. Check if ML engine is down
curl https://api.humaneye.io/api/v1/health

# 4. Check DB connections
# In backend logs, look for: "connection pool exhausted"
```

### Most likely causes + fixes

| Cause | Fix |
|---|---|
| Bad deploy | Roll back immediately (see rollback procedure below) |
| ML engine down | Restart ECS service: `aws ecs update-service --force-new-deployment` |
| DB connection exhausted | Restart backend ECS tasks to reset pool |
| Unhandled exception in new code | Roll back + notify backend engineer |

### Rollback procedure
```bash
# Get previous task definition revision
aws ecs describe-task-definition \
  --task-definition humaneye-backend-production \
  --query 'taskDefinition.revision'

# Roll back to previous revision (replace N with revision number)
aws ecs update-service \
  --cluster humaneye-cluster-production \
  --service humaneye-backend-production \
  --task-definition humaneye-backend-production:N
```

---

## RB-003 — Redis Memory > 80%

**Alert:** `humaneye-redis-memory`
**Severity:** Medium
**SLA impact:** Rate limiting may fail, sessions may be lost

### Diagnose
```bash
# Connect to Redis
redis-cli -h $REDIS_HOST -a $REDIS_PASSWORD

# Check memory usage
INFO memory

# Check biggest keys
redis-cli -h $REDIS_HOST --bigkeys

# Check key count by prefix
redis-cli -h $REDIS_HOST --scan --pattern "rate_limit:*" | wc -l
redis-cli -h $REDIS_HOST --scan --pattern "session:*" | wc -l
```

### Fixes
1. Check TTLs — are rate limit keys expiring correctly?
2. Check for keys without TTL: `DEBUG SLEEP 0; OBJECT ENCODING key`
3. If legitimate growth → upgrade ElastiCache node type in Terraform

---

## RB-004 — ML Inference Time > 300ms

**Alert:** `humaneye-ml-inference-slow`
**Severity:** Medium
**SLA impact:** Full pipeline exceeds 300ms requirement

### Diagnose
```bash
# Check which model is slow
curl http://ml-engine:8001/metrics | grep model_inference_duration

# Check ECS task CPU
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=humaneye-ml-engine-production \
  --start-time $(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 60 \
  --statistics Average
```

### Fixes
| Cause | Fix |
|---|---|
| Model not loaded into memory (cold start) | Wait 2 min after deploy |
| CPU throttling | Increase ECS task CPU units in Terraform |
| Large batch of requests | Scale out ML engine ECS tasks |
| Phase 2 GPU underutilized | Check CUDA availability in ml_engine container |

---

## RB-005 — ECS Task Crash Loop

**Alert:** ECS service has repeated task failures
**Severity:** Critical

### Diagnose
```bash
# Get recent stopped tasks and their stop reason
aws ecs list-tasks \
  --cluster humaneye-cluster-production \
  --service-name humaneye-backend-production \
  --desired-status STOPPED \
  --query 'taskArns[:5]'

# Get stop reason for a specific task
aws ecs describe-tasks \
  --cluster humaneye-cluster-production \
  --tasks TASK_ARN \
  --query 'tasks[0].{stopCode: stopCode, stoppedReason: stoppedReason}'

# Check CloudWatch logs for crash output
aws logs tail /ecs/humaneye/backend --follow
```

### Most likely causes
- Missing environment variable → check `.env.example` vs ECS task definition
- OOM killed → increase memory in Terraform, redeploy
- DB migration failed → check Alembic output in logs
- Crash on startup → check application logs for import errors

---

## RB-006 — Verification Failure Spike

**Alert:** Unusual spike in verification failures
**Severity:** High — may indicate attack or model regression

### Diagnose
```bash
# This is a custom metric from the backend /metrics endpoint
# Check in Grafana: "verification_failure_rate" panel

# Check if it's one customer or all
# In backend logs, look for: session_id, api_key_hash patterns

# Check if ML engine scores changed (possible model regression after deploy)
curl https://api.humaneye.io/api/v1/health | jq '.ml_engine'
```

### Response
1. If spike coincides with deploy → roll back ML model to previous version
2. If distributed across many IPs → potential coordinated attack, alert security engineer
3. If single customer → check their integration, might be sending malformed signals

---

## General Incident Protocol

1. **Detect** — alert fires (CloudWatch → SNS → your phone)
2. **Assess** — is this affecting customers? Check Grafana dashboard
3. **Communicate** — post in `#incidents` Slack immediately (even if you don't know the cause)
4. **Diagnose** — use runbook above
5. **Fix or Roll back** — prefer rollback over debugging live
6. **Verify** — confirm alert clears in CloudWatch
7. **Post-mortem** — written report within 5 business days:
   - Timeline
   - Root cause
   - Customer impact
   - Fix applied
   - Prevention measure

---

## Useful commands quick reference

```bash
# Tail production backend logs
aws logs tail /ecs/humaneye/backend --follow

# Force new ECS deployment (rolling restart)
aws ecs update-service \
  --cluster humaneye-cluster-production \
  --service humaneye-backend-production \
  --force-new-deployment

# Scale backend up manually
aws ecs update-service \
  --cluster humaneye-cluster-production \
  --service humaneye-backend-production \
  --desired-count 4

# Check all service health
aws ecs describe-services \
  --cluster humaneye-cluster-production \
  --services \
    humaneye-backend-production \
    humaneye-ml-engine-production \
  --query 'services[*].{name:serviceName,running:runningCount,desired:desiredCount,status:status}'

# Connect to production RDS (requires VPN or bastion)
psql $DATABASE_URL

# Check active DB connections
psql $DATABASE_URL -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"
```
