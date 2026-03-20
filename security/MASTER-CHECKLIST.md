# HumanEye — Master Security Checklist
**Owner: Security Engineer | Run at: Month 1 launch gate, then quarterly**

---

## Purpose

This is the single combined checklist that verifies every security control is live.
It is run before any production customer traffic is accepted (Month 1 launch gate)
and then every quarter as part of the SOC 2 observation period.

Mark each item: ✅ LIVE | ❌ NOT DONE | ⚠️ PARTIAL

---

## Section 1: Infrastructure (DevOps)

### Secrets Management
- [ ] HashiCorp Vault deployed in private subnet
- [ ] Vault auto-unseal configured (AWS KMS)
- [ ] All secrets migrated from env vars to Vault
- [ ] Vault audit logging to S3 immutable bucket
- [ ] Vault access policies set (backend, ml-engine, security roles)
- [ ] No secrets in GitHub (run: `git log -p | grep -i "password\|secret\|key"`)

### Network Security
- [ ] ML engine port 8001: inbound from Backend SG only (verify in AWS console)
- [ ] PostgreSQL port 5432: inbound from Backend SG only
- [ ] Redis port 6379: inbound from Backend SG only
- [ ] No security group with `0.0.0.0/0` on any non-web port
- [ ] ALB: HTTP (80) redirects to HTTPS (443) only
- [ ] TLS 1.3 on ALB (verify: SSL Labs test)

### Encryption at Rest
- [ ] RDS: `storage_encrypted = true` (verify: AWS console)
- [ ] EBS volumes: encrypted (verify: AWS Config rule `encrypted-volumes`)
- [ ] S3 models bucket: server-side encryption enabled
- [ ] S3 audit bucket: server-side encryption + object lock enabled
- [ ] Redis: note — not encrypted at rest, no sensitive data stored

### IAM
- [ ] No wildcard `*` in any IAM Action or Resource
- [ ] Each service has dedicated role (no shared roles)
- [ ] Root account MFA enabled
- [ ] No active root account access keys
- [ ] Developers cannot access production DB directly

### Audit Logging
- [ ] CloudTrail enabled on all regions
- [ ] CloudTrail logs delivered to immutable S3 bucket (separate account)
- [ ] CloudTrail log file validation enabled
- [ ] Vault audit logs shipping to same immutable bucket

---

## Section 2: Backend API

### Authentication
- [ ] API keys generated with `secrets.token_bytes(32)` (not `random`, not `uuid4`)
- [ ] API keys stored as bcrypt hash, cost factor 12 (run: check `backend/core/security.py`)
- [ ] Plaintext key never stored in database (verify: DB schema review)
- [ ] API key never appears in any log (run: `security/scripts/api-key-audit.py backend/`)
- [ ] SHA256 hash used in logs instead

### Rate Limiting
- [ ] Redis sliding window rate limiting on all endpoints
- [ ] Limit: 100 req/min per API key
- [ ] Rate limit response includes `Retry-After` header
- [ ] Rate limit tested: send 101 requests, verify 429 on 101st

### Input Validation
- [ ] All Pydantic schemas have `extra = "forbid"`
- [ ] Payload size middleware: rejects >10MB
- [ ] All string fields have `max_length`
- [ ] All array fields have `max_items`

### Database Security
- [ ] Zero raw SQL strings in backend code (run: `grep -rn "db.execute" backend/`)
- [ ] All queries include `customer_id` scoping (manually review verify + scores endpoints)
- [ ] Cross-tenant access test: Customer A cannot read Customer B's verifications
- [ ] Verification IDs are UUIDs (not sequential integers)

### Error Handling
- [ ] 5xx responses return generic message (no stack traces)
- [ ] Error responses include request ID (not internal paths)
- [ ] Tested: trigger a 500, verify response contains no file paths

### CORS
- [ ] CORS whitelist is explicit (not `*`)
- [ ] Only `app.humaneye.io` and `staging.humaneye.io` in allowed origins

---

## Section 3: ML Engine

### Model Integrity
- [ ] Every production model has hash in Vault (`vault kv list secret/humaneye/models/`)
- [ ] Models loaded via `load_model_verified()` — no direct `torch.load()`
- [ ] Integrity check on startup tested: corrupt a model file, verify service refuses to start
- [ ] Every production model has MLflow run record

### Data Privacy
- [ ] 90-day signal deletion job exists (Celery task)
- [ ] Deletion job tested: verify signals >90 days are actually deleted
- [ ] No raw signal values in inference logs (check ml_engine log output)
- [ ] Scores logged as buckets, not exact floats

### Adversarial Testing
- [ ] Adversarial test suite exists and runs (`ml_engine/evaluation/adversarial_runner.py`)
- [ ] At least one adversarial test run completed with results logged
- [ ] Pass threshold 85% documented and enforced

### Internal API
- [ ] ML engine requires `X-Internal-Token` header
- [ ] ML engine returns 401 without valid token (test: call port 8001 without header)
- [ ] Port 8001 not reachable from outside VPC (test from external: connection refused)

---

## Section 4: Browser SDK

### Privacy — Non-Negotiable
- [ ] Grep scan: zero results for `event\.key[^C]` in `sdk/browser/src/`
- [ ] Grep scan: zero results for `\.keyCode` in `sdk/browser/src/`
- [ ] Grep scan: zero results for `\.which\b` in `sdk/browser/src/`
- [ ] Grep scan: zero results for `charCode` in `sdk/browser/src/`
- [ ] Browser DevTools test: outbound payload contains `code` not `key`
- [ ] SDK tested on HTTP page: refuses to initialize with console error

### Technical
- [ ] Bundle size: under 50KB gzipped
- [ ] `npm audit`: 0 high, 0 critical
- [ ] Signal processing in Web Worker (check: `new Worker(` in capture code)
- [ ] SDK only calls `api.humaneye.io` (no other domains)

---

## Section 5: Dashboard

### Session Security
- [ ] Auth tokens in httpOnly, Secure, SameSite=Strict cookies
- [ ] No auth tokens in localStorage (test: check localStorage after login)
- [ ] Session expires after 24h (test: wait 24h, verify redirect to login)

### XSS Prevention
- [ ] CSP headers present on all pages (test: check response headers in DevTools)
- [ ] `X-Frame-Options: DENY` present
- [ ] `X-Content-Type-Options: nosniff` present
- [ ] User-generated content sanitized before rendering

### API Key Display
- [ ] API key shown in full once at creation
- [ ] Subsequent views show masked version: `he_live_xxxx...xxxx`
- [ ] Full key cannot be retrieved via any API call (test: `GET /api/v1/keys/{id}`)

---

## Section 6: Compliance and Process

### SOC 2 Foundation
- [ ] Security awareness training completed by all engineers (signatures in `docs/security-onboarding.md`)
- [ ] Incident response plan written, reviewed, and distributed
- [ ] Access review process defined and first review completed
- [ ] Change management: all production deployments require PR + approval

### GDPR
- [ ] Record of Processing Activities (ROPA) complete
- [ ] Privacy policy published describing behavioral data collection
- [ ] Deletion API endpoint implemented and tested
- [ ] Data Processing Addendum (DPA) template ready for customer contracts

### Pen Testing
- [ ] External pen test scoped (Month 6 target)
- [ ] Pen test firm selected and NDA signed

---

## Launch Gate Decision

```
Section 1 (Infrastructure):     ___ / 23 items ✅
Section 2 (Backend):             ___ / 20 items ✅
Section 3 (ML Engine):           ___ / 12 items ✅
Section 4 (SDK):                 ___ / 10 items ✅
Section 5 (Dashboard):           ___ / 10 items ✅
Section 6 (Compliance):          ___ / 7  items ✅

Total: ___ / 82 items ✅

LAUNCH GATE: All 82 items must be ✅ before first customer traffic.
Any ❌ = Security Engineer blocks launch until resolved.
```

**Reviewed by:** Security Engineer
**Date:** _______________
**Decision:** APPROVED / BLOCKED

---

*This checklist is reviewed by the SOC 2 auditor as evidence of pre-launch security review.*
*Every item with a test procedure must be tested — not just verified by reading code.*
