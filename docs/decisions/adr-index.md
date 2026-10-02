# Flowmint AI — Architecture Decision Records

## ADR-001: Monorepo Structure

**Status:** Accepted  
**Date:** 2026-10-01

**Decision:** Use a monorepo with `frontend/` and `backend/` at the top level.

**Rationale:** Simpler dependency management, atomic commits across stack, shared documentation. Small team does not benefit from the coordination overhead of separate repositories.

---

## ADR-002: Hybrid Search Architecture

**Status:** Accepted

**Decision:** SQL structured filters + `pg_trgm` lexical search (Phase 1), add `pgvector` semantic search in Phase 2.

**Rationale:** Commerce search requires exact price/attribute filtering that vector-only search handles poorly. Hybrid architecture gives precision (structured) + recall (semantic). Starting with SQL + pg_trgm avoids additional infrastructure while covering 90% of use cases.

---

## ADR-003: Bounded Autonomy Model

**Status:** Accepted

**Decision:** All agent actions pass through: Schema Validation → Agent Permission → Policy Check → Risk Classification → Optional Human Approval → Idempotent Execution → Audit.

**Rationale:** Financial/commerce system cannot tolerate uncontrolled AI actions. The LLM reasons and proposes; the application layer enforces rules and executes.

---

## ADR-004: Provider-Agnostic AI Abstraction

**Status:** Accepted

**Decision:** Create `LLMProvider` and `EmbeddingProvider` interfaces with swappable implementations.

**Rationale:** LLM landscape is volatile. Avoids vendor lock-in. Enables cost optimization by model tiering.

---

## ADR-005: Payment State Machine

**Status:** Accepted

**Decision:** Explicit state machine for payments: `PENDING → AUTHORIZED → CAPTURED` (or `→ FAILED`), with `CAPTURED → REFUNDED`. Transitions are validated server-side. Idempotency keys prevent duplicate payments.

**Rationale:** Payment is the highest-risk domain. State machine prevents impossible transitions (e.g., refunding a failed payment). Razorpay webhook is the authoritative state source — frontend verification is backup only.

**Transition Table:**

| From | Allowed To |
|---|---|
| pending | authorized, captured, failed |
| authorized | captured, failed |
| captured | refunded |
| failed | (terminal) |
| refunded | (terminal) |

---

## ADR-006: In-Process Event Bus with Outbox

**Status:** Accepted

**Decision:** Phase 1 uses an in-process async pub/sub event bus. Domain events are first written to an `outbox_events` table within the same database transaction as the business update, then dispatched.

**Rationale:** Prevents lost events when the business transaction commits but event dispatch fails. Same producer/consumer interface allows migration to Redis Streams in Phase 2 without changing domain contracts.

---

## ADR-007: Tenant Isolation via Backend Middleware

**Status:** Accepted

**Decision:** `merchant_id` is extracted from JWT and injected into every query via service methods. All merchant-owned entities have `merchant_id` foreign key. Uniqueness constraints are scoped per-merchant (e.g., `UNIQUE(merchant_id, sku)`).

**Rationale:** Defense in depth — tenant isolation at the data layer, not just the API layer. Frontend filtering is cosmetic; backend enforces isolation.

**Multi-tenant constraints:**

| Table | Constraint |
|---|---|
| Product | `UNIQUE(merchant_id, slug)`, `UNIQUE(merchant_id, sku)` |
| Category | `UNIQUE(merchant_id, slug)` |
| Customer | `UNIQUE(merchant_id, email)` |
| User | `UNIQUE(merchant_id, email)` |
| Order | `UNIQUE(merchant_id, order_number)` |
| Payment | `UNIQUE(merchant_id, idempotency_key)` |
| CartItem | `UNIQUE(cart_id, product_id)` |

---

## ADR-008: Transactional Outbox Pattern

**Status:** Accepted

**Decision:** Business updates and their domain events are committed in the same database transaction via an `outbox_events` table. A dispatcher reads pending events and publishes to the in-process EventBus.

**Rationale:** Guarantees that committed transactions always have their events delivered. Prevents the "write succeeded but event was lost" failure mode that occurs with fire-and-forget event publishing.

---

## ADR-009: Razorpay Webhook Security

**Status:** Accepted

**Decision:** The webhook endpoint (`POST /api/v1/payments/webhook`) does NOT require JWT authentication. Authentication is via Razorpay HMAC SHA-256 signature verification. Duplicate webhooks are safely ignored via unique `provider_event_id` constraint on `PaymentEvent`.

**Rationale:** Razorpay cannot provide JWT tokens. The webhook secret + HMAC signature is the standard authentication mechanism for payment webhooks. Deduplication prevents double-processing of retried webhooks.

**Webhook Flow:**
1. Verify Razorpay HMAC signature
2. Parse event payload
3. Check `provider_event_id` uniqueness (deduplicate)
4. Find internal Payment by `provider_order_id`
5. Validate state transition
6. Update Payment + Order transactionally
7. Write OutboxEvent
8. Return 200

**Security Rules:**
- Never trust frontend payment confirmation as authoritative
- Always verify webhook signature before processing
- Never process the same `provider_event_id` twice
- Log but don't expose internal payment details

---

## ADR-010: AI Provider Abstraction

**Status:** Accepted  
**Date:** 2026-10-02

**Decision:** Create a decoupled `LLMProvider` interface with unified message and tool call representations. Implement `OpenAIProvider`, `AnthropicProvider`, `GoogleProvider`, and `MockLLMProvider`. Provider selection is driven by environment configuration (`AI_PROVIDER`, `AI_MODEL`, etc.) via a centralized factory.

**Rationale:** Enables zero-cost, deterministic, and network-independent automated unit testing through `MockLLMProvider`. Prevents vendor lock-in and allows seamless model tiering without coupling business agents to proprietary SDK signatures or APIs.

---

## ADR-011: Typed Tool Execution and Security Context Injection

**Status:** Accepted  
**Date:** 2026-10-02

**Decision:** Every agent tool extends `BaseTool`, defining explicit Pydantic parameter schemas, risk levels, and read-only flags. Execution parameters are strictly validated by Pydantic before invocation. Security context (`merchant_id`, `db`, `trace_id`) is strictly injected by backend infrastructure through `ToolContext` and cannot be supplied or modified by the LLM. All tool outputs are wrapped in untrusted data delimiters.

**Rationale:** Guarantees strong multi-tenant isolation, protects against prompt injection attempts aimed at overriding authorization contexts, and ensures deterministic error handling across tool execution boundaries.

---

## ADR-012: Read-Only Phase 2A Agents

**Status:** Accepted  
**Date:** 2026-10-02

**Decision:** In Phase 2A, Buyer Agent and Analytics Agent operate strictly in read-only mode (`action_plan: None`, `is_read_only: True`). No mutating actions (updating inventory, modifying prices, applying discounts, creating campaigns, or issuing refunds) are registered or executable.

**Rationale:** Establishes the bounded-autonomy AI infrastructure, intent routing, and observability traces safely before introducing write capabilities or autonomous business actions in Phase 2B. Prevents unintended state side-effects during early platform verification.

---

## ADR-013: Deterministic Revenue Opportunity Detection & Inspectable Evidence

**Status:** Accepted  
**Date:** 2026-10-02

**Decision:** Revenue opportunities (`abandoned_cart`, `payment_failure`, `conversion_drop`, `cross_sell`, `low_inventory`) are detected using deterministic database-backed SQL queries and business heuristics rather than generative LLM inference. Every detected opportunity must persist structured, inspectable evidence (`evidence_json`) recording the exact metric, observed value, baseline, period, and affected entity IDs.

**Rationale:** Prevents hallucinated financial figures and phantom business anomalies. Merchants can inspect exactly "WHY" an opportunity was flagged. The LLM acts solely as an investigative reasoning and action-formulation agent over ground-truth SQL telemetry.

---

## ADR-014: What-If Simulation Engine & ActionPlan Proposal Lifecycle (Bounded Recommendation-Only)

**Status:** Accepted  
**Date:** 2026-10-02

**Decision:** In Phase 2B, Growth Agent and Recovery Agent are recommendation-only decision engines. They formulate structured `ActionPlan` objects with initial status `PROPOSED` and `requires_approval = True`. No write tools or autonomous campaign/discount executors exist. Financial projections are calculated deterministically by the What-If Simulation Engine with transparent formulas and explicit disclaimers.

**Rationale:** Enforces strict bounded autonomy. ActionPlans represent structured proposals for human merchant review and policy evaluation (to be implemented in Phase 3) without risking unauthorized price cuts, unintended customer messaging, or financial losses.

---

## ADR-015: Agent Permission Matrix & Non-Wildcard Capabilities

**Status:** Accepted  
**Date:** 2026-10-02

**Decision:** Define explicit, non-wildcard permission boundaries for every agent role (`BUYER_AGENT`, `ANALYTICS_AGENT`, `GROWTH_AGENT`, `RECOVERY_AGENT`). Disallow wildcard permissions (`*`). Write tools (`create_campaign_draft`, `create_offer`, `launch_recovery_campaign`) are restricted strictly to authorized agents and can NEVER be called directly by agents or the LLM.

**Rationale:** Prevents privilege escalation and prompt injection attacks from granting an agent mutating capabilities. The agent can only formulate an `ActionPlan` proposal. Mutating actions require traversal through the full security pipeline.

---

## ADR-016: Centralized Action Execution Pipeline, Deterministic Policy/Risk Engines, and Immutable Audit Trail

**Status:** Accepted  
**Date:** 2026-10-02

**Decision:** Transform recommendations into safe execution via a centralized `ActionExecutionService`. Every consequential action must pass through the pipeline: `Agent -> ActionPlan -> Agent Permission -> Schema Validation -> Policy Engine (9 deterministic rules) -> Risk Engine (deterministic 4-tier) -> Approval Requirement (HITL) -> Central Executor -> Controlled Write Tool -> Outcome -> Immutable Audit Log`. All executions enforce database-level uniqueness on `action_id` and `idempotency_key`. Direct invocation of `/execute` re-evaluates all policy, risk, and approval requirements. Autonomous price mutations and refunds remain strictly forbidden in Phase 3.

**Rationale:** Protects the merchant against financial runaway, unauthorized discounts, cross-tenant leaks, and replay attacks. Establishes an immutable, tamper-evident audit record of every business transition.

