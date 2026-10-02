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
  - **MockLLM:** ~10–20ms latency, 100% deterministic regression test fixture.
  - **Gemini 1.5 Flash:** ~400–800ms latency, fast multi-turn conversational reasoning.
  - **OpenAI GPT-4o / GPT-4o-mini:** ~500–1200ms latency, high schema adherence.
  - **Anthropic Claude 3.5 Sonnet:** ~800–1600ms latency, deep contextual reasoning.

### 6. Provider Downtime Fail-Closed Behavior
- **Constraint:** If an external LLM provider experiences an outage or timeout (> 10s), the system fails closed:
  - Conversational copilot informs the merchant of provider unavailability.
  - Background decision workflows mark the run as `FAILED_TIMEOUT` without attempting unverified actions.
  - Zero state mutations occur during external AI provider degradation.

### 7. Cloud Staging & Real-LLM Benchmarks Are Credential-Gated
- **Constraint:** Live execution of empirical benchmarks against commercial frontier models (OpenAI, Gemini, Anthropic) and live remote deployment to cloud staging (Render, Vercel) require external merchant credentials and platform tokens.
- **Enforcement:** In local or offline evaluation environments, the system executes the verified MockLLM regression suite (900 cases) and reports cloud/real benchmarks as **BLOCKED** rather than manufacturing unverified empirical results.
