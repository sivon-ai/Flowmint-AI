# Flowmint AI — Database Design

## Design Principles
- UUID primary keys on all tables
- `created_at` / `updated_at` timestamps where appropriate
- Multi-tenant: `merchant_id` FK on all merchant-owned entities
- Uniqueness constraints scoped per-merchant
- CHECK constraints for business invariants
- Indexes on foreign keys and frequently queried columns

## Phase 1 Schema

### Identity
- **merchants** — Tenant entity. `slug` globally unique, `email` globally unique.
- **users** — Auth identity. `UNIQUE(merchant_id, email)`. Roles: owner, admin, viewer.

### Catalog
- **categories** — Product categories with self-referencing tree. `UNIQUE(merchant_id, slug)`.
- **products** — Product catalog. `UNIQUE(merchant_id, slug)`, `UNIQUE(merchant_id, sku)`.
- **product_attributes** — Key-value pairs per product. `UNIQUE(product_id, key)`.
- **inventory** — Stock tracking. `UNIQUE(product_id)`. CHECK constraints: `quantity >= 0`, `reserved >= 0`, `reserved <= quantity`.

### Customers
- **customers** — Buyer identity per merchant. `UNIQUE(merchant_id, email)`.

### Commerce
- **carts** — Shopping cart. Status: active → checkout → converted | abandoned | expired.
- **cart_items** — Items in cart with unit_price snapshot. `UNIQUE(cart_id, product_id)`.
- **orders** — `UNIQUE(merchant_id, order_number)`. Status: pending → confirmed → processing → shipped → delivered → completed | cancelled.
- **order_items** — Snapshot of product at time of order (name, SKU, price).

### Payments
- **payments** — `UNIQUE(merchant_id, idempotency_key)`. State machine: pending → authorized | captured | failed; authorized → captured | failed; captured → refunded; failed, refunded (terminal).
- **payment_events** — `UNIQUE(provider_event_id)`. Immutable webhook event log.

### Events
- **outbox_events** — Transactional outbox. Status: pending → published | failed.

## Future Schema (Phase 2+)
- campaigns, offers, opportunities, recovery_actions
- agent_sessions, agent_messages, agent_runs, tool_calls, action_plans
- policies, approvals, approval_decisions, audit_logs, action_executions
- revenue_metrics, funnel_events, customer_preferences, customer_events
