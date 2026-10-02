# Flowmint AI — Roadmap

## Phase 1: Foundation + Commerce (Weeks 1–4)

- [x] Monorepo structure
- [x] Docker Compose (PostgreSQL + Redis)
- [x] FastAPI application with config management
- [x] SQLAlchemy 2.0 async models
- [x] Alembic migrations
- [x] JWT authentication
- [x] Tenant isolation (middleware + model constraints)
- [x] Merchant + User models
- [x] Category model
- [x] Product CRUD with search (ILIKE + filters)
- [x] ProductAttribute (key-value)
- [x] Inventory with reservation support
- [x] Customer CRUD
- [x] Cart lifecycle (create, add, update, remove items)
- [x] Order creation from cart (with inventory reservation)
- [x] Payment state machine (PENDING → AUTHORIZED → CAPTURED)
- [x] Razorpay TEST integration (order creation)
- [x] Razorpay webhook handler (signature verification + deduplication)
- [x] OutboxEvent (transactional outbox pattern)
- [x] In-process EventBus
- [x] Domain event types
- [x] Seed data script
- [x] Backend tests (63 tests)
- [x] Frontend: Merchant dashboard shell
- [x] Frontend: Product management
- [x] Frontend: Buyer storefront skeleton
- [x] Frontend: Live end-to-end integration

## Phase 2A: AI Infrastructure & Read-Only Agents (COMPLETE)

- [x] LLM provider abstraction (OpenAI, Anthropic, Google, Mock)
- [x] Embedding provider abstraction (MockEmbeddingProvider, OpenAIEmbeddingProvider)
- [x] Structured tool framework (`BaseTool`, `ToolContext`, `ToolResult`, Pydantic schemas)
- [x] Tool registry with typed parameter validation, tenant context injection & latency recording
- [x] Agent base interface (`BaseAgent`, `AgentResult` with `action_plan: None`)
- [x] Agent Orchestrator with deterministic intent routing and fallback
- [x] Buyer Agent (search_products, get_product, compare_products, check_inventory, get_related_products)
- [x] Analytics Agent (get_revenue_summary, get_conversion_summary, get_product_performance, get_payment_summary, compare_periods, get_order_summary)
- [x] AI session/message persistence (`agent_sessions`, `agent_messages`)
- [x] Agent run/trace persistence (`agent_runs`, `tool_call_records`)
- [x] 11 safe read-only commerce tools
- [x] AI API endpoints (`/chat`, `/buyer`, `/analytics`, `/sessions`, `/runs`)
- [x] Prompt injection defense and untrusted data wrapping
- [x] AI evaluation test suite (30 tests: tool selection, anti-hallucination, tenant isolation, prompt injection)
- [x] Frontend AI Copilot page for merchant dashboard
- [x] Frontend Buyer AI natural-language product discovery on storefront

## Phase 2B: Revenue Intelligence & Decision Engine (COMPLETE)

- [x] Revenue Intelligence Engine (database-backed deterministic metrics: revenue, AOV, conversion, abandonment, payment failure rate, inventory pressure)
- [x] Opportunity Engine with deterministic detectors (`abandoned_cart`, `payment_failure`, `conversion_drop`, `cross_sell`, `low_inventory`)
- [x] Inspectable evidence model (`evidence_json`, affected entities, rationale)
- [x] Growth Agent (recommendation-only: cross-sell, bundles, upsell)
- [x] Recovery Agent (recommendation-only: abandoned carts, payment retries)
- [x] What-If Simulation Engine (deterministic financial modelling: recovery discounts, promo offers, margin impact, assumptions)
- [x] ActionPlan domain model and lifecycle (`PROPOSED`, `requires_approval=True`)
- [x] Zero-write-tools safety invariant strictly enforced
- [x] Phase 2B API endpoints (`/opportunities`, `/opportunities/{id}/investigate`, `/simulations/recovery`, `/simulations/offer`, `/action-plans`, `/agents/growth`, `/agents/recovery`)
- [x] Alembic migration `003_phase2b_revenue_engine` applied to live PostgreSQL
- [x] Frontend: Revenue Command Center dashboard
- [x] Frontend: Opportunities page with Master-Detail inspector, evidence view & AI investigation
- [x] Frontend: What-If Simulator with interactive sliders, financial projections, and clear disclaimers
- [x] Frontend: Growth and Recovery Agent modes in AI Copilot
- [x] Evaluation & Tests: 104/104 backend tests passing, frontend tests/build passing

## Phase 3: Safety, Governance & Controlled Execution (COMPLETE)

- [x] Agent Permission Matrix & Non-Wildcard Capabilities (`BUYER_AGENT`, `ANALYTICS_AGENT`, `GROWTH_AGENT`, `RECOVERY_AGENT`)
- [x] Deterministic 4-tier Risk Classification Engine (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`)
- [x] Policy Rule Framework with 9 configurable deterministic rules
- [x] Human-in-the-Loop (HITL) Approval Workflow with expiration windows & multi-tenant isolation
- [x] Centralized Action Execution Service (`ActionExecutionService`)
- [x] Database-level idempotency protection (`action_id`, `idempotency_key`) preventing replay attacks
- [x] Controlled write tools registry (`create_campaign_draft`, `create_offer`, `launch_recovery_campaign`)
- [x] Strict prohibition of refunds and direct price mutations
- [x] Immutable, tamper-evident Audit Trail (`audit_logs`)
- [x] Policy Simulator API (`POST /api/v1/policies/evaluate`)
- [x] Governance APIs (`/policies`, `/actions`, `/approvals`, `/audit`)
- [x] Alembic migration `004_phase3_safety_governance` applied to live PostgreSQL
- [x] Frontend: Approval Center page (`/approvals`)
- [x] Frontend: Policy Engine & Simulator page (`/policies`)
- [x] Frontend: Audit Trail & Trace Inspector page (`/audit`)
- [x] 114/114 backend tests passing, frontend tests/typecheck/build passing

## Phase 4: Evaluation, Revenue Attribution, Observability & Production Launch (COMPLETE)

- [x] Fixed 900-case evaluation dataset (500 Buyer, 100 Analytics, 100 Growth, 50 Recovery, 50 Adversarial Bypass, 50 Prompt Injection, 50 Failure Scenarios)
- [x] AI Evaluation Runner with strict MockLLM vs Real LLM separation
- [x] Empirical metrics: Intent accuracy (100%), Tool selection accuracy (100%), Safety pass rate (100%), Injection resistance (100%)
- [x] Revenue Attribution Engine linking ActionPlan → Execution → Observed Outcome → Attribution
- [x] Strict metric label hierarchy (`SIMULATED`, `ESTIMATED`, `OBSERVED`, `ATTRIBUTED`)
- [x] Merchant Before vs After reporting (Eligible carts, recoveries, gross recovered, discount costs, net impact)
- [x] End-to-End Causal Trace DAG reconstruction (`/traces/{trace_id}`)
- [x] Fail-closed failure recovery suite (LLM timeout, tool failure, expired approval, duplicate request, circuit breaking)
- [x] Security Red-Team suite passing 10/10 adversarial scenarios
- [x] Performance & Cost control (SafeReadCache, token budgets, max tool calls, latency telemetry)
- [x] Deterministic seed dataset with canonical ₹1,42,000 checkout abandonment opportunity
- [x] Canonical 5-minute success path demo & mandatory 25% discount policy-blocked failure demo
- [x] Frontend: Revenue Attribution page (`/attribution`)
- [x] Frontend: End-to-End Trace Viewer page (`/traces`)
- [x] Frontend: AI Evaluation Lab page (`/evaluation`)
- [x] Alembic migration `005_phase4_attribution` applied to live PostgreSQL
- [x] 124/124 backend tests passing, frontend tests passing, TypeScript clean, production build passing

