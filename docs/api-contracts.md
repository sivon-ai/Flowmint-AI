# Flowmint AI — API Contracts

## Base URL
```
/api/v1
```

## Response Envelope
```json
{
  "success": true|false,
  "data": T | null,
  "meta": { "page": 1, "per_page": 20, "total": 142, "total_pages": 8 } | null,
  "errors": [{ "code": "ERROR_CODE", "message": "Human message", "field": "field_name" }] | null
}
```

## Phase 1 Endpoints

### Health
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | Liveness check |
| GET | `/health/ready` | No | Readiness check |

### Auth
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/register` | No | Register merchant + owner user |
| POST | `/auth/login` | No | Login, returns JWT tokens |
| POST | `/auth/refresh` | No | Refresh access token |
| GET | `/auth/me` | JWT | Get current user profile |

### Products
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/products` | JWT | List with search, filter, paginate |
| POST | `/products` | JWT | Create product + inventory |
| GET | `/products/:id` | JWT | Get product by ID |
| PATCH | `/products/:id` | JWT | Update product |
| DELETE | `/products/:id` | JWT | Soft delete (archive) |

Query params: `q`, `category_id`, `min_price`, `max_price`, `status`, `sort_by`, `sort_order`, `page`, `per_page`

### Inventory
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/inventory` | JWT | List all inventory |
| GET | `/inventory/:product_id` | JWT | Get stock for product |
| PATCH | `/inventory/:product_id` | JWT | Update quantity/threshold |

### Customers
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/customers` | JWT | List customers |
| POST | `/customers` | JWT | Create customer |
| GET | `/customers/:id` | JWT | Get customer |

### Carts
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/carts` | JWT | Create cart |
| GET | `/carts/:id` | JWT | Get cart with items |
| POST | `/carts/:id/items` | JWT | Add item to cart |
| PATCH | `/carts/:id/items/:item_id` | JWT | Update item quantity |
| DELETE | `/carts/:id/items/:item_id` | JWT | Remove item |

### Orders
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/orders` | JWT | Create order from cart |
| GET | `/orders` | JWT | List orders |
| GET | `/orders/:id` | JWT | Get order detail |

### Payments
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/payments/:order_id/initiate` | JWT | Create Razorpay order |
| POST | `/payments/webhook` | Razorpay Sig | Webhook handler |
| GET | `/payments/:id` | JWT | Get payment status |

## Phase 2A AI Agent Endpoints (Implemented)

### AI Agents
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/agents/chat` | JWT | General conversational entry point with intelligent intent routing |
| POST | `/agents/buyer` | JWT | Directly routes query to Buyer Agent (catalog/inventory search) |
| POST | `/agents/analytics` | JWT | Directly routes query to Analytics Agent (revenue/performance metrics) |
| GET | `/agents/sessions` | JWT | List chat sessions for current merchant |
| GET | `/agents/sessions/:id` | JWT | Get session details with chronological message history |
| GET | `/agents/runs/:id` | JWT | Get run trace details and tool execution breakdown |

### Agent Chat Request Body
```json
{
  "message": "Find me a laptop under ₹70,000",
  "session_id": "optional-uuid-to-continue-conversation"
}
```

### Agent Chat Response Data
```json
{
  "session_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "trace_id": "trc_4a78cb38546a",
  "agent_name": "buyer_agent",
  "response": "I found 1 matching product in our catalog...",
  "structured_data": [...],
  "tool_calls": [
    {
      "tool": "search_products",
      "parameters": { "query": "laptop", "max_price": 70000 },
      "status": "success",
      "latency_ms": 12
    }
  ],
  "latency_ms": 48
}
```

## Phase 2B Endpoints (Active)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/opportunities` | JWT | List detected opportunities for current merchant |
| GET | `/opportunities/:id` | JWT | Get opportunity details and inspectable evidence |
| POST | `/opportunities/:id/investigate` | JWT | AI investigation + ActionPlan formulation |
| GET | `/opportunities/metrics/overview` | JWT | High-level revenue intelligence metrics |
| POST | `/simulations/recovery` | JWT | Deterministic cart recovery financial simulation |
| POST | `/simulations/offer` | JWT | Deterministic promotional offer simulation |
| GET | `/action-plans` | JWT | List formulated action plans (`status: proposed`) |
| GET | `/action-plans/:id` | JWT | Get action plan detail with impact and parameters |
| POST | `/agents/growth` | JWT | Direct Growth Agent recommendation invocation |
| POST | `/agents/recovery` | JWT | Direct Recovery Agent recommendation invocation |

## Phase 3 Endpoints (Active)

### Policy Engine & Simulator
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/policies/evaluate` | JWT | Policy Simulator: dry-run ActionPlan against all rules without side-effects |
| GET | `/policies` | JWT | Get active merchant policy configuration |
| PUT | `/policies` | JWT | Update merchant policy bounds (discount, budget, frequency, etc.) |

### Actions & Execution
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/actions` | JWT | List ActionPlans with governance status |
| GET | `/actions/:id` | JWT | Get ActionPlan detail with risk, policy, and execution records |
| POST | `/actions/:id/validate` | JWT | Validate plan against policy engine and determine approval needs |
| POST | `/actions/:id/execute` | JWT | Central idempotent execution pipeline (enforces policy, approval, uniqueness) |

### Approvals
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/approvals` | JWT | List human approval requests for merchant (`status` filter supported) |
| GET | `/approvals/:id` | JWT | Get approval detail with policy evaluation snapshot |
| POST | `/approvals/:id/approve` | JWT | Approve pending action request |
| POST | `/approvals/:id/reject` | JWT | Reject pending action request with decision reason |

### Audit Trail
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/audit` | JWT | List immutable audit log records for merchant |
| GET | `/audit/:id` | JWT | Get specific audit log entry with execution & policy payload |

