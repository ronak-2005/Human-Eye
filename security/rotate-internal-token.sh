#!/bin/bash
"""
security/scripts/rotate-internal-token.sh

Monthly internal service token rotation.
Rotates the Backend → ML Engine authentication token.

Run by: DevOps Engineer (first Monday of every month)
Notify: Security Engineer after rotation complete

Usage:
  ./security/scripts/rotate-internal-token.sh [production|staging]
"""

set -e

ENVIRONMENT=${1:-"production"}

if [ "$ENVIRONMENT" != "production" ] && [ "$ENVIRONMENT" != "staging" ]; then
  echo "Usage: $0 [production|staging]"
  exit 1
fi

echo "═══════════════════════════════════════════════"
echo "HumanEye Internal Token Rotation — $ENVIRONMENT"
echo "Date: $(date -u)"
echo "═══════════════════════════════════════════════"
echo ""

# Step 1: Verify Vault access
echo "Step 1: Verifying Vault access..."
vault kv get "secret/humaneye/$ENVIRONMENT/internal-token" > /dev/null 2>&1 || {
  echo "ERROR: Cannot read from Vault. Check your credentials."
  exit 1
}
echo "  ✅ Vault access confirmed"

# Step 2: Generate new token
echo ""
echo "Step 2: Generating new token..."
NEW_TOKEN=$(openssl rand -base64 32)
CREATED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
ROTATE_BY=$(date -u -d '+30 days' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v+30d +%Y-%m-%dT%H:%M:%SZ)
echo "  ✅ New token generated (not displayed for security)"

# Step 3: Write new token to Vault
echo ""
echo "Step 3: Writing new token to Vault..."
vault kv put "secret/humaneye/$ENVIRONMENT/internal-token" \
  token="$NEW_TOKEN" \
  created_at="$CREATED_AT" \
  rotate_by="$ROTATE_BY" \
  rotated_by="${USER:-unknown}"
echo "  ✅ New token stored in Vault"
echo "  Created at: $CREATED_AT"
echo "  Rotate by:  $ROTATE_BY"

# Step 4: Restart services to pick up new token
echo ""
echo "Step 4: Restarting services to pick up new token..."

CLUSTER="humaneye-$ENVIRONMENT"

# Force new deployment (ECS Fargate will pull new Vault token via agent sidecar)
aws ecs update-service \
  --cluster "$CLUSTER" \
  --service "backend" \
  --force-new-deployment \
  --query "service.serviceName" \
  --output text
echo "  Backend: restart initiated"

aws ecs update-service \
  --cluster "$CLUSTER" \
  --service "ml-engine" \
  --force-new-deployment \
  --query "service.serviceName" \
  --output text
echo "  ML Engine: restart initiated"

# Step 5: Wait for services to stabilize
echo ""
echo "Step 5: Waiting for services to stabilize (this takes 2-3 minutes)..."
aws ecs wait services-stable \
  --cluster "$CLUSTER" \
  --services backend ml-engine

echo "  ✅ Both services stable"

# Step 6: Health check
echo ""
echo "Step 6: Health check..."
HEALTH=$(curl -sf "https://api.humaneye.io/api/v1/health" \
  --max-time 10 \
  -o /dev/null \
  -w "%{http_code}" 2>/dev/null || echo "000")

if [ "$HEALTH" = "200" ]; then
  echo "  ✅ Health check passed (HTTP 200)"
else
  echo "  ⚠️  Health check returned HTTP $HEALTH"
  echo "  Check ECS service logs before declaring rotation complete."
fi

# Step 7: Log rotation event
echo ""
echo "Step 7: Logging rotation event..."
# This log entry is SOC 2 evidence of regular credential rotation
logger -t "humaneye-security" \
  "event_type=token_rotation environment=$ENVIRONMENT rotated_by=${USER:-unknown} created_at=$CREATED_AT" \
  2>/dev/null || true
echo "  ✅ Rotation logged"

echo ""
echo "═══════════════════════════════════════════════"
echo "✅ TOKEN ROTATION COMPLETE"
echo ""
echo "REQUIRED ACTION: Notify Security Engineer"
echo "  Message: 'Internal token rotated for $ENVIRONMENT'"
echo "  Date: $CREATED_AT"
echo "  Next rotation due: $ROTATE_BY"
echo "═══════════════════════════════════════════════"
