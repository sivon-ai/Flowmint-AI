# Flowmint AI — Security Documentation

## Authentication

- **Method**: JWT (JSON Web Tokens) via `python-jose`
- **Password Hashing**: bcrypt via `passlib`
- **Token Types**: Access token (30 min) + Refresh token (7 days)
- **Token Payload**: `{ sub: user_id, merchant_id, role, type, exp }`

## Authorization

- **Role-Based Access Control (RBAC)**: `owner`, `admin`, `viewer`
- **Route Protection**: `get_current_user` dependency extracts user from JWT
- **Role Enforcement**: `require_role("owner", "admin")` dependency

## Tenant Isolation

- Every merchant-owned entity has a `merchant_id` foreign key
- Backend middleware extracts `merchant_id` from JWT
- All service methods filter by `merchant_id` — never trust frontend
- Database constraints: `UNIQUE(merchant_id, sku)`, `UNIQUE(merchant_id, slug)`, etc.

## Webhook Security

- Razorpay webhook endpoint does NOT require JWT authentication
- Authentication: HMAC SHA-256 signature verification using `RAZORPAY_WEBHOOK_SECRET`
- Deduplication: `provider_event_id` unique constraint on `PaymentEvent`
- The webhook is the authoritative payment state — frontend is backup only

## Input Validation

- Pydantic v2 schemas on every API boundary
- SQLAlchemy ORM prevents SQL injection (never raw string formatting)
- Request body size limits via FastAPI
- Path parameter type validation (UUID)

## Secret Management

- All secrets in environment variables (`.env`)
- `.env` is gitignored — `.env.example` has placeholders only
- Razorpay keys, JWT secrets, DB credentials NEVER in source control
- Secrets NEVER exposed in logs or error responses

## CORS

- Explicit origin allowlist via `BACKEND_CORS_ORIGINS`
- Credentials allowed for JWT cookie support (future)

## Rate Limiting

- Foundation in config (`RATE_LIMIT_PER_MINUTE=60`)
- Full Redis-backed implementation in Phase 2

## AI Security (Phase 2A Implemented)

- **Read-Only Enforced**: All Phase 2A tools are strictly read-only (`is_read_only=True`). Mutating tools or action plans are rejected.
- **Tenant Context Injection**: `merchant_id` and database sessions are injected strictly by backend infrastructure via `ToolContext`. The LLM cannot provide or override tenant identity.
- **Typed Parameter Validation**: Every tool parameter is validated against its Pydantic schema before execution; invalid parameters return structured errors.
- **Prompt Injection Defense**:
  - `detect_injection_risk`: Heuristic regex scanner checks for prompt overrides, jailbreaks, and system prompt tampering.
  - Length limits (max 2000 chars) enforced on user messages.
  - Boundary Isolation: Untrusted database strings (product descriptions, customer metadata) are wrapped in `<untrusted_data>` delimiters before LLM exposure.
  - Role Separation: Strict division of System Instructions, User Inputs, and Tool Results.
- **Agent Tool Allowlists**: Buyer Agent and Analytics Agent have separate, restricted tool allowlists enforced at the registry level.
- **Zero Secrets in LLM Prompts**: API keys, database credentials, and internal roles are strictly excluded from prompts and tool signatures.

## Payment Security

- Razorpay TEST MODE only (Phase 1)
- Idempotency keys on all payment operations
- Payment state machine prevents invalid transitions
- Duplicate webhook delivery safely ignored
- Financial credentials never sent to frontend or LLM
