# Flowmint AI — System Architecture

**Product:** Flowmint AI  
**Tagline:** Turn every signal into a revenue action.  
**Definition:** A bounded-autonomy revenue operating system for AI-ready merchants.

---

## 1. System Topology

```
+------------------------------------------------------------------------+
|                             BUYER COMMERCE                             |
|  - Storefront Catalog Search (Lexical pg_trgm / Hybrid)                |
|  - Real-time Cart Management & Validation                              |
|  - Order Checkout with Razorpay Test Mode                              |
+------------------------------------------------------------------------+
                                    |
                                    v
+------------------------------------------------------------------------+
|                      FLOWMINT FASTAPI BACKEND (v1)                     |
|                                                                        |
|  +--------------------+  +--------------------+  +------------------+  |
|  |   Tenant Security  |  |  Payment State     |  |  Transactional   |  |
|  |   & JWT Auth       |  |  Machine           |  |  Outbox Pattern  |  |
|  |   (Owner/Admin/    |  |  (Pending->        |  |  (Atomic with    |  |
|  |    Viewer RBAC)    |  |   Captured/Failed) |  |   DB commit)     |  |
|  +--------------------+  +--------------------+  +------------------+  |
|                                    |                                   |
|                                    v                                   |
|  +------------------------------------------------------------------+  |
|  |                       In-Process Event Bus                       |  |
|  |   (order.created, payment.captured, inventory.updated, etc.)     |  |
|  +------------------------------------------------------------------+  |
+------------------------------------------------------------------------+
            |                                           |
            v                                           v
+-----------------------+                   +------------------------+
|   PostgreSQL 16 DB    |                   |       Redis 7          |
|  - 14 Phase 1 Tables  |                   |  - Cache & Lock state  |
|  - Tenant Constraints |                   |  - Migration target    |
|  - Check Constraints  |                   |    for Event Streams   |
+-----------------------+                   +------------------------+
```

---

## 2. Core Subsystems (Phase 1 Baseline)

### Multi-Tenant Data Layer
All merchant data is strictly isolated via `merchant_id` foreign keys and composite unique constraints:
- `Product`: `UNIQUE(merchant_id, slug)`, `UNIQUE(merchant_id, sku)`
- `Category`: `UNIQUE(merchant_id, slug)`
- `Customer`: `UNIQUE(merchant_id, email)`
- `User`: `UNIQUE(merchant_id, email)`
- `Order`: `UNIQUE(merchant_id, order_number)`
- `Payment`: `UNIQUE(merchant_id, idempotency_key)`
- `CartItem`: `UNIQUE(cart_id, product_id)`

### Inventory & Concurrency Protection
- Inventory reservation utilizes `SELECT FOR UPDATE` inside transactional session scopes.
- Database check constraints enforce invariants:
  - `ck_inventory_quantity_positive`: `quantity >= 0`
  - `ck_inventory_reserved_positive`: `reserved >= 0`
  - `ck_inventory_reserved_lte_quantity`: `reserved <= quantity`
- Prevents overselling under concurrent checkouts.

### Payment State Machine & Webhooks
- State transitions are rigorously validated:
  - `pending` -> `authorized`, `captured`, `failed`
  - `authorized` -> `captured`, `failed`
  - `captured` -> `refunded`
  - `failed` & `refunded` -> terminal states (empty transition sets)
- Razorpay webhook endpoint (`POST /api/v1/payments/webhook`) requires no JWT; authentication is enforced via HMAC SHA-256 signature verification.
- Deduplication is guaranteed by `uq_payment_event_provider_id` on `PaymentEvent`.

### Transactional Outbox Pattern
- When business changes occur (orders created, payments captured, inventory reserved), an `OutboxEvent` record is inserted in the exact same database transaction.
- The `OutboxDispatcher` reads unhandled events and publishes them to the `EventBus` only after transaction commit.

---

## 3. AI Infrastructure Subsystem (Phase 2A Baseline)

```
+------------------------------------------------------------------------+
|                          AGENT ORCHESTRATOR                            |
|  - Deterministic Intent Routing (Buyer vs Analytics vs Clarification)  |
|  - Session Lifecycle & Audit Trail Management                          |
+------------------------------------------------------------------------+
              |                                          |
              v                                          v
+-----------------------------+            +-----------------------------+
|         BUYER AGENT         |            |       ANALYTICS AGENT       |
|  - Grounded Product Search  |            |  - Financial Aggregations   |
|  - Real-time Stock Check    |            |  - Funnel & AOV Calculation |
|  - Spec Comparison          |            |  - Performance Breakdown    |
+-----------------------------+            +-----------------------------+
              \                                          /
               \                                        /
                v                                      v
+------------------------------------------------------------------------+
|                   STRUCTURED TOOL FRAMEWORK & REGISTRY                 |
|  - Strongly-typed Pydantic Validation                                  |
|  - Injected ToolContext (merchant_id, db session, trace_id)             |
|  - Strictly Read-Only Execution (action_plan = None)                   |
|  - Latency & Error Auditing in tool_call_records                       |
+------------------------------------------------------------------------+
                                    |
                                    v
+------------------------------------------------------------------------+
|                      PROVIDER ABSTRACTION LAYER                        |
|  - MockLLMProvider (zero-cost deterministic CI tests)                  |
|  - OpenAIProvider, AnthropicProvider, GoogleProvider                   |
|  - EmbeddingProvider (1536-dim normalized vector interface)            |
+------------------------------------------------------------------------+
```

### Persistence Models (Phase 2A)
- `agent_sessions`: Tenant-scoped conversation sessions.
- `agent_messages`: Chronological conversation turns with role, content, and tool call metadata.
- `agent_runs`: Audit trace recording latency, token usage, agent name, model, and status.
- `tool_call_records`: Detailed record of every tool executed with input parameters, output payload, and latency.

