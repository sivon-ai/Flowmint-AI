# Flowmint AI — Agent Architecture

## Overview

Flowmint AI's agent layer orchestrates specialized AI agents operating under **bounded autonomy**. In Phase 2A, two primary agents are established:
1. **Buyer Agent**: Handles product search, spec comparison, inventory validation, and customer-facing commerce recommendations.
2. **Analytics Agent**: Handles merchant revenue intelligence, order breakdowns, sales funnels, and performance analysis.

Both agents are **strictly read-only** in Phase 2A (`action_plan = None`).

---

## 1. Agent Base Interface

Defined in [`app.ai.agents.base`](file:///d:/Flowmint%20AI/backend/app/ai/agents/base.py):

```python
class BaseAgent(ABC):
    name: str
    description: str
    system_prompt: str
    allowed_tools: list[str]
    maximum_risk_level: RiskLevel = RiskLevel.READ_ONLY

    async def execute(self, user_message: str, context: ToolContext, history: list[dict] | None = None) -> AgentResult:
        ...
```

### `AgentResult` Contract
```python
class AgentResult(BaseModel):
    response: str
    structured_data: Any | None = None
    action_plan: None = None  # Strictly None for Phase 2A
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    trace_id: str
    agent_name: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
```

---

## 2. Buyer Agent

- **System Prompt**: Enforces strict grounding in catalog truth. The agent is explicitly prohibited from hallucinating prices, inventory counts, or product specifications. If an item is missing from search results, it must state so clearly.
- **Allowed Tools**:
  - `search_products`
  - `get_product`
  - `compare_products`
  - `check_inventory`
  - `get_related_products`
- **Workflow**:
  1. Extract buyer constraints (keywords, budget caps, categories).
  2. Invoke `search_products` via Tool Registry.
  3. Verify stock availability via `check_inventory`.
  4. Synthesize clear, grounded recommendation with price and stock status.

---

## 3. Analytics Agent

- **System Prompt**: Enforces factual financial reporting. Distinguishes explicitly between:
  1. *Observed Facts* (authoritative SQL numbers returned by tools).
  2. *Derived Calculations* (AOV, growth percentage, conversion rate).
  3. *Interpretations* (business commentary on performance trends).
- **Allowed Tools**:
  - `get_revenue_summary`
  - `get_conversion_summary`
  - `get_product_performance`
  - `get_payment_summary`
  - `compare_periods`
  - `get_order_summary`
- **Workflow**:
  1. Parse merchant intent and time horizon (today, this week, custom date ranges).
  2. Execute analytical aggregation tools across verified orders and payments.
  3. Return grounded structured metrics alongside executive commentary.

---

## 4. Agent Orchestrator

Located in [`app.ai.agents.orchestrator`](file:///d:/Flowmint%20AI/backend/app/ai/agents/orchestrator.py), the Orchestrator provides:
1. **Deterministic Intent Routing**:
   - `cross sell`, `bundle`, `upsell`, `bought together` ➔ **Growth Agent**
   - `recover`, `recovery`, `retry payment`, `recovery offer` ➔ **Recovery Agent**
   - `revenue`, `sales`, `conversion`, `orders`, `payment`, `performance` ➔ **Analytics Agent**
   - `search`, `find`, `laptop`, `price`, `stock`, `inventory` ➔ **Buyer Agent**
   - Ambiguous queries ➔ Clarification request with suggested prompts
2. **Session & Message Management**:
   - Retrieves or creates tenant-isolated `AgentSession`.
   - Records incoming user message in `agent_messages`.
   - Injects chronological chat history into agent context.
3. **Execution & Run Auditing**:
   - Creates an `AgentRun` with unique `trace_id`.
   - Records all invoked `ToolCallRecord` entries with latency and status.
   - Updates `AgentSession.updated_at` and persists assistant response message.

---

## 5. Growth Agent (Phase 2B)

- **Role**: Recommends catalog expansion, companion bundles, and upsell packages.
- **Allowed Tools**:
  - `get_frequently_bought_together`
  - `get_customer_purchase_history`
  - `get_inventory_health`
- **Output**: Formulates structured `ActionPlan` (`action_type: "cross_sell_bundle"`, `status: "proposed"`, `requires_approval: True`).
- **Safety Invariant**: Strict recommendation-only. Zero price or discount write mutations allowed.

---

## 6. Recovery Agent (Phase 2B)

- **Role**: Formulates targeted recovery nudges for abandoned checkouts and retries for failed payment transactions.
- **Allowed Tools**:
  - `get_abandoned_carts`
  - `get_failed_payments`
  - `get_recovery_candidates`
- **Output**: Formulates structured `ActionPlan` (`action_type: "abandoned_cart_recovery"` or `"payment_retry_nudge"`, `status: "proposed"`, `requires_approval: True`).
- **Safety Invariant**: Strictly non-mutating. No emails or WhatsApp messages are sent; no customer records are modified.

