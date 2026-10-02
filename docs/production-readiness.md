# Flowmint AI — Production Readiness & Deployment Guide

## Overview

Flowmint AI is built as a production-grade, secure, bounded-autonomy revenue operating system. This document outlines production readiness guarantees, failure recovery mechanisms, environment validation, and deployment procedures.

---

## Production Security & Resilience Controls

1. **Multi-Tenant Isolation**: Every database table enforces a composite `(merchant_id, ...)` foreign key or check constraint. All API routes enforce tenant-scoped filtering via `CurrentUser` dependencies. Cross-tenant reads and executions are rejected with 403 Forbidden.
2. **Fail-Closed Architecture**: Any failure in policy evaluation, risk classification, or authorization fails closed. If an approval is expired or missing, execution is blocked.
3. **Idempotent Mutations**: Database unique constraint on `(merchant_id, idempotency_key)` prevents duplicate financial side effects across tested scenarios. Replay attacks receive cached successful results without triggering secondary tool calls.
4. **No Secrets in Logs or Traces**: Credentials, Razorpay webhook secrets, database connection strings, and JWT keys are strictly excluded from AI prompts, agent messages, traces, and audit logs.
5. **Prompt Injection Defense**: Untrusted user inputs are wrapped with XML boundary tags and validated by the security classifier before agent reasoning.

---

## Health & Readiness Endpoints

Flowmint AI exposes standard Kubernetes/Docker health and readiness probes:

- **`GET /health`**: Shallow liveness check verifying HTTP server uptime.
- **`GET /api/v1/health`**: Deep readiness probe verifying active PostgreSQL connection, Redis connection, and Alembic migration status.

Example readiness response:
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "migration_head": "005_phase4_attribution",
  "version": "1.0.0"
}
```

---

## Failure Recovery Specifications

| Failure Mode | Failure Behavior | Recovery Mechanism |
|---|---|---|
| **LLM Timeout (>15s)** | Fails closed. Turn marked failed. Zero side effects. | Safe retry with backoff. Circuit breaker opens if failure rate >50%. |
| **Tool Execution Error** | Transaction rollbacks cleanly. Tool result recorded as failed. | ActionPlan remains in `failed` state. Requires manual retry or re-plan. |
| **Expired Approval** | Execution rejected with `ValidationError`. | ActionPlan reverts to `expired`. New approval must be requested. |
| **Duplicate Execution Attempt** | Idempotency lock detects existing key. | Returns prior cached execution result. Second mutation is prevented. |
| **Redis Cache Down** | Degrades gracefully to direct PostgreSQL read queries. | SafeReadCache handles redis connection errors transparently. |

---

## Production Deployment Checklist

- [x] Docker Compose configured with PostgreSQL 16 (pgvector enabled) and Redis 7.
- [x] Alembic migrations run cleanly up to revision `005_phase4_attribution`.
- [x] JWT access token expiry set to 15 minutes, refresh token set to 7 days.
- [x] Secure CORS origin whitelist configured via `CORS_ORIGINS`.
- [x] Rate limiting middleware enabled.
- [x] Full test suite (126 backend tests + frontend test suite) passing.
- [x] Production frontend build compiled without type errors.
