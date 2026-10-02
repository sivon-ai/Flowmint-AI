# Flowmint AI — Observability & End-to-End Tracing

## Overview

Flowmint AI provides end-to-end causal trace reconstruction for all commercial decisions. Unlike generic distributed tracing, Flowmint traces connect the semantic reasoning of AI agents directly to deterministic business policies, human approvals, controlled mutations, and financial outcomes.

---

## Causal DAG Architecture

Every commercial event generates or inherits a unique `trace_id` that correlates the entire journey:

```
[Opportunity Signal]
        |
        v
   [Agent Run] -------> [Tool Calls (1..N)]
        |
        v
  [ActionPlan]
        |
        v
  [Policy Check] -----> [Risk Engine]
        |                     |
        +----------+----------+
                   |
                   v
             [HITL Approval]
                   |
                   v
          [Action Execution]
                   |
                   v
           [Observed Outcome]
                   |
                   v
          [Immutable Audit Log]
```

---

## Timeline Nodes & Metadata

| Step | Node Type | Captured Metadata |
|---|---|---|
| **1** | `opportunity_detected` | `type`, `title`, `priority`, `potential_revenue`, `evidence_json` |
| **2** | `agent_run` | `agent_name`, `model`, `prompt_tokens`, `completion_tokens`, `latency_ms` |
| **3** | `tool_call` | `tool_name`, `parameters`, `result`, `status`, `latency_ms` |
| **4** | `action_plan` | `action_type`, `risk_level`, `requires_approval`, `parameters`, `estimated_impact` |
| **5** | `policy_check` | 9 deterministic rules evaluated, blocking reasons, evidence snapshots |
| **6** | `approval` | `status`, `requested_by`, `decided_by`, `decision_reason`, `expires_at` |
| **7** | `execution` | `tool_name`, `idempotency_key`, `tool_result`, `started_at`, `status` |
| **8** | `outcome` | `label` (OBSERVED), `orders_attributed`, `gross_revenue`, `net_revenue_impact`, `confidence` |
| **9** | `audit_log` | Immutable append-only log record with hash and actor ID |

---

## Trace Reconstruction API

```http
GET /api/v1/traces/{trace_id}
Authorization: Bearer <MERCHANT_TOKEN>
```

Response payload:
```json
{
  "success": true,
  "data": {
    "trace_id": "trc_canonical_88e01",
    "merchant_id": "e0970ecd-070c-440a-b964-94d71639a508",
    "total_nodes": 8,
    "timeline": [
      {
        "step": 1,
        "type": "opportunity_detected",
        "label": "Opportunity Detected",
        "status": "completed",
        "timestamp": "2026-10-02T10:00:00Z",
        "details": {
          "type": "abandoned_cart",
          "title": "Checkout Abandonment Spike (₹1,42,000 at risk)",
          "potential_revenue": 142000.0
        }
      },
      ...
    ]
  }
}
```

---

## Performance & Cost Telemetry

Flowmint AI tracks latency, database overhead, and model usage per merchant:

- **Token Budgets**: Strict limit of 4,096 tokens per agent turn.
- **Tool Call Cap**: Maximum 5 tool invocations per turn to prevent infinite loops.
- **Safe Read Cache**: In-memory Redis cache with 60-second TTL for read-only catalog queries.
- **Telemetry Endpoint**: `GET /api/v1/performance/metrics` returns:
  - `p50_latency_ms` & `p95_latency_ms`
  - `cache_hit_rate`
  - `total_token_usage`
  - `estimated_model_cost_usd`
