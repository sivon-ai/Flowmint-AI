# Flowmint AI — Known Limitations & Non-Goals

In accordance with our core principle of **Zero Hallucination and Transparent Engineering**, this document explicitly records the design boundaries, known constraints, and non-goals of Flowmint AI.

---

## 🚫 Autonomous Execution Boundaries

### 1. Refunds Are Strictly Manual (Never Autonomous)
- **Constraint:** Flowmint AI does **not** allow autonomous issuance or processing of customer refunds.
- **Rationale:** Automatic bank reversals present extreme financial loss and fraud risks. All customer refund requests remain strictly within the merchant operator's manual purview via the payment processor's dashboard or administrative tools.
- **Safety Rule:** No write tool in the agent registry has access to refund execution capabilities.

### 2. Third-Party Messaging Channels in Test/Simulated Mode
- **Constraint:** Direct external customer notifications (e.g. WhatsApp Business Cloud API, transactional SMS gateways, email sending) run in test/simulated mode unless merchant production API credentials and webhook callbacks are explicitly bound.
- **Rationale:** Prevents accidental unsolicited spam or regulatory non-compliance during evaluation and staging.
- **Safety Rule:** Campaign messages generate deterministic outbox events (`cart.recovery_voucher_applied`) rather than unmonitored raw socket dispatch.

---

## 📊 Attribution & Financial Modeling Boundaries

### 3. Time-Bounded Attribution Windows
- **Constraint:** Revenue attribution is evaluated over bounded observation windows (typically 7 to 14 days following action execution).
- **Rationale:** Long-term customer purchases cannot be deterministically linked to a single past nudge without confounding macroeconomic variables.
- **Labeling Standard:** All linkages using direct voucher code or cart tracking are labeled `DETERMINISTIC EVENT LINK` rather than making generalized statistical causal claims.

### 4. Simulations and Forecasts Are Not Guarantees
- **Constraint:** Monte Carlo and arithmetic What-if Simulations represent ex-ante mathematical projections based on historical priors.
- **Labeling Standard:** Projections are strictly labeled `SIMULATED` or `ESTIMATED` and must **never** be interpreted or reported as bankable recovered revenue until actual customer orders are recorded as `OBSERVED`.

---

## 🤖 AI & LLM Provider Constraints

### 5. AI Performance Varies by Provider and Model
- **Constraint:** While Flowmint AI's safety guarantees (Policy Engine, HITL approval, schema validation, multi-tenant isolation) are enforced deterministically in Python/SQL code, LLM intent classification latency and semantic extraction accuracy depend on the chosen inference provider:
  - **Fireworks AI (Qwen 3.8 Max):** Primary live inference provider (`accounts/fireworks/models/qwen3p8-max`); native structured tool calling verified with ~3.5–4.5s round-trip latency.
  - **MockLLM:** ~1–2ms latency, 100% deterministic regression test fixture.
  - **OpenAI GPT-4o / GPT-4o-mini:** Alternative external provider.
  - **Anthropic Claude 3.5 Sonnet:** Alternative external provider.
  - **Gemini 1.5 Pro / Flash:** Alternative external provider.

### 6. Provider Downtime Fail-Closed Behavior
- **Constraint:** If an external LLM provider experiences an outage, timeout (> 10s), or missing credentials, the system fails closed:
  - The provider returns an explicit error (`AI_PROVIDER_ERROR` or `AI_CONFIG_ERROR`).
  - The system **never silently substitutes MockLLM** for real provider calls.
  - Conversational copilot informs the merchant of provider unavailability.
  - Background decision workflows mark the run as `FAILED_TIMEOUT` without attempting unverified actions.
  - Zero state mutations occur during external AI provider degradation.

### 7. Cloud Staging & Real-LLM Benchmarks Are Credential-Gated
- **Constraint:** Live Fireworks inference and structured tool calling have been verified. Cloud deployment remains credential-gated unless actually deployed. MockLLM remains available for deterministic regression testing.
- **Reporting Standard:** We do not claim 100% model accuracy in general, guaranteed responses, guaranteed causality, or custom fine-tuning. On Flowmint's 900-case evaluation suite, the Fireworks Qwen3.8 Max configuration achieved the measured evaluation result under the documented test protocol. Real LLM benchmarks report only actual measured metrics.

