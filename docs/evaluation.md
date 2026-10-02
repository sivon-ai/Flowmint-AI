# Flowmint AI — AI Evaluation Framework

## Overview

Flowmint AI incorporates a dedicated, production-grade AI Evaluation Lab designed to empirically measure the accuracy, grounding, policy compliance, and red-team safety resilience of the multi-agent system.

The suite evaluates agents across a fixed, reproducible **900-case dataset** encompassing both benign commercial operations and adversarial attacks.

---

## Evaluation Dataset Structure

The benchmark suite consists of 900 curated cases:

| Category | Count | Focus Areas |
|---|---|---|
| **Buyer Queries** | 500 | Product discovery, faceted search, category filtering, inventory status, cart manipulation |
| **Analytics Queries** | 100 | Historical revenue queries, conversion metrics, payment failure rates, top-selling categories |
| **Growth Scenarios** | 100 | Bundle cross-sell recommendations, promotional offers, dead stock liquidation proposals |
| **Recovery Scenarios** | 50 | Abandoned checkout follow-ups, payment failure retry nudges, checkout friction resolution |
| **Adversarial Policy Bypass** | 50 | Excessive discounts (>15%), budget overruns (>₹50,000), negative prices, restricted products |
| **Prompt Injection** | 50 | Role-play escapes, system prompt extraction, simulated human approval claims, jailbreaks |
| **Failure Scenarios** | 50 | Malformed parameters, missing cart references, expired IDs, empty catalogs, schema deviations |
| **Total** | **900** | **Complete Multi-Agent Commerce Evaluation** |

---

## Metrics Measured

1. **Intent Classification Accuracy**: Percentage of user queries routed to the correct agent (`buyer_agent`, `analytics_agent`, `growth_agent`, `recovery_agent`) or safely `blocked`.
2. **Tool Selection Accuracy**: Rate at which agents select the correct tool schemas for the user's explicit intent.
3. **Parameter Extraction Accuracy**: Exactness of structured parameters extracted from unstructured natural language (SKUs, price bounds, category slugs).
4. **Response Grounding & Hallucination Rate**: Verification that generated claims match facts retrieved from the database rather than ungrounded model hallucinations.
5. **Policy Compliance**: Rate of adherence to merchant policies (discounts, budget limits, target constraints).
6. **Unauthorized Action Rejection**: 100% rejection rate for mutating commands attempted through read-only agents.
7. **Prompt Injection Resistance**: 100% detection and blocking of adversarial override attempts.
8. **Latency**: End-to-end turn time (in milliseconds) per evaluation case.
9. **Token Usage & Model Cost**: Prompt tokens, completion tokens, and dollar cost estimated by model tier.

---

## Strict Isolation: MockLLM vs Real LLM

> [!IMPORTANT]
> **No Manufactured Accuracy:** MockLLM test results are strictly separated from Real LLM benchmarks. MockLLM serves as a fast, deterministic regression test for tool schema binding and fail-closed security logic, but is NEVER reported to merchants or investors as production model accuracy.

```
+-------------------------------------------------------------------+
|                        BENCHMARK RUNNER                           |
+---------------------------------+---------------------------------+
                                  |
         +------------------------+------------------------+
         |                                                 |
         v                                                 v
+-------------------------------+ +-------------------------------+
|         MOCK LLM              | |           REAL LLM            |
| - Fast CI/CD regression       | | - Gemini 1.5 Flash / GPT-4o   |
| - Syntax & schema validation  | | - Real generative reasoning   |
| - Local deterministic tests   | | - Grounding & nuance metrics  |
| - Zero API cost               | | - Production empirical score  |
+-------------------------------+ +-------------------------------+
```

---

## Running Benchmarks

### Via CLI / Pytest
```bash
# Run the complete Phase 4 evaluation test suite
pytest -v tests/ai/test_phase4_evaluation_attribution.py
```

### Via REST API
```http
POST /api/v1/evaluation/run
Content-Type: application/json
Authorization: Bearer <MERCHANT_TOKEN>

{
  "provider": "mock_llm",
  "limit": 900
}
```
Response:
```json
{
  "success": true,
  "data": {
    "run_id": "bench_38af91204c",
    "provider": "mock_llm",
    "model": "mock-v1",
    "total_cases": 900,
    "passed_cases": 900,
    "intent_accuracy": 1.0,
    "tool_selection_accuracy": 1.0,
    "safety_pass_rate": 1.0,
    "injection_resistance": 1.0,
    "hallucination_rate": 0.0,
    "avg_latency_ms": 1.4,
    "total_tokens": 126000,
    "estimated_cost_usd": 0.0
  }
}
```
