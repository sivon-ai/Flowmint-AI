# Flowmint AI — AI Infrastructure Architecture

## Overview

Flowmint AI adopts a **bounded-autonomy architecture** for artificial intelligence. The LLM acts as an untrusted reasoning engine, whereas the backend application remains the single authoritative source of truth for commerce state, inventory levels, permissions, and database operations.

```
User Query
    │
    ▼
FastAPI API Endpoints (/api/v1/agents/chat, /buyer, /analytics)
    │
    ▼
Agent Orchestrator (Intent Classification & Session Management)
    │
    ├── Intent: Product / Inventory ──► Buyer Agent
    └── Intent: Revenue / Performance ──► Analytics Agent
            │
            ▼
        LLM Provider Abstraction (Mock / OpenAI / Anthropic / Google)
            │
            ├── Emits Structured Tool Call
            ▼
        Tool Registry (Schema Validation & Access Control)
            │
            ├── Injects Tenant Security Context (merchant_id, db session, trace_id)
            ▼
        Safe Read-Only SQL Tool Execution (search_products, get_revenue_summary, etc.)
            │
            ├── Wraps Output in Untrusted Data Boundary (<untrusted_data>)
            ▼
        LLM Response Synthesis & Grounding
            │
            ▼
        Agent Result (response, structured_data, tool_calls, action_plan=None)
            │
            ▼
        Audit Persistence (agent_sessions, agent_messages, agent_runs, tool_call_records)
```

---

## 1. Provider Abstraction Layer

All model interactions are routed through the `LLMProvider` abstract base class defined in [`app.ai.providers.base`](file:///d:/Flowmint%20AI/backend/app/ai/providers/base.py).

### Core Interface
- `generate(messages, tools, temperature, max_tokens) -> LLMResponse`
- Message representations: `LLMMessage(role, content, name, tool_call_id, tool_calls)`
- Tool representations: standard OpenAI JSON Schema format generated dynamically from Pydantic schemas.

### Implemented Providers
1. **`MockLLMProvider`**: Deterministic keyword/pattern matching and preset queueing. Used for unit, integration, and CI testing with zero external API dependencies or costs.
2. **`OpenAIProvider`**: Async HTTP client integrating OpenAI Chat Completions API (`gpt-4o-mini`, `gpt-4o`).
3. **`AnthropicProvider`**: Async HTTP client integrating Anthropic Messages API (`claude-3-5-sonnet`, `claude-3-haiku`).
4. **`GoogleProvider`**: Async HTTP client integrating Google Gemini API (`gemini-1.5-pro`, `gemini-1.5-flash`).

### Provider Factory
Configured via `.env`:
```env
AI_PROVIDER=mock       # mock | openai | anthropic | google
AI_MODEL=mock-model-v1
AI_TEMPERATURE=0.0
AI_MAX_TOKENS=2048
```

---

## 2. Embedding Provider Abstraction

Semantic representations are decoupled through `EmbeddingProvider`:
- `embed_text(text: str) -> list[float]`
- `embed_batch(texts: list[str]) -> list[list[float]]`
- `dimensions: int`

`MockEmbeddingProvider` produces normalized 1536-dimensional deterministic vectors. In Phase 2A, SQL structured filters + `pg_trgm` lexical search remain the authoritative retrieval foundation; pgvector integration can be added seamlessly in future phases.

---

## 3. Structured Tool Framework & Registry

Tools inherit from `BaseTool`:
```python
class BaseTool(ABC):
    name: str
    description: str
    parameters_schema: type[BaseModel]
    risk_level: RiskLevel  # READ_ONLY, LOW, MEDIUM, HIGH, CRITICAL
    is_read_only: bool = True
    requires_merchant_id: bool = True

    async def execute(self, params: BaseModel, context: ToolContext) -> ToolResult:
        ...
```

### Security Context Injection
The LLM is strictly prohibited from providing authorization parameters. Context is injected by the backend:
```python
class ToolContext(BaseModel):
    merchant_id: uuid.UUID
    user_id: uuid.UUID | None
    trace_id: str
    db: AsyncSession | None
    is_read_only: bool = True
```

### Registered Phase 2A Tools (All Read-Only)
| Domain | Tool Name | Description |
|---|---|---|
| Buyer | `search_products` | Filter catalog by keyword, price range, and stock availability |
| Buyer | `get_product` | Authoritative product lookup by ID or SKU |
| Buyer | `compare_products` | Compare specs, stock, and pricing across 2-5 products |
| Buyer | `check_inventory` | Real-time available stock and low-stock verification |
| Buyer | `get_related_products` | Discover related items in same category |
| Analytics | `get_revenue_summary` | Total revenue, paid order count, AOV for time window |
| Analytics | `get_conversion_summary` | Funnel conversion rates across carts and paid orders |
| Analytics | `get_product_performance` | Ranked product sales, volume, and revenue |
| Analytics | `get_payment_summary` | Payment breakdown by status and currency |
| Analytics | `compare_periods` | Period-over-period growth and variance analysis |
| Analytics | `get_order_summary` | Order count by state (pending, paid, cancelled) |

---

## 4. Prompt Injection Defense & Untrusted Data Isolation

External content (product descriptions, customer inputs, merchant notes) is treated as untrusted data:
1. **Pre-execution sanitization**: Input length limits (2000 chars) and detection of known jailbreak patterns (`ignore previous instructions`, `system prompt override`).
2. **Data boundary wrapping**: All SQL query outputs and catalog descriptions are wrapped in `<untrusted_data>` delimiters before passing back to the LLM.
3. **Role separation**: System instructions, user prompts, and tool outputs are strictly segregated in provider messages. Tool output can never expand agent execution authority.

---

## 5. Observability & Persistence

Every agent execution is persisted across four dedicated tables in PostgreSQL:
- **`agent_sessions`**: Tenant-scoped conversational session with chronological message history.
- **`agent_messages`**: Individual messages (user, assistant, tool, system) with token and tool metadata.
- **`agent_runs`**: Execution trace containing trace_id, agent_name, model, token usage, latency_ms, status, and error details.
- **`tool_call_records`**: Detailed invocation log for each tool executed, including parameters, execution status, latency, and returned payload.
