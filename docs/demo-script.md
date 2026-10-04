# Flowmint AI — Competition Demo Script & Walkthrough

This document outlines the official script for presenting Flowmint AI to judges and reviewers. It covers the **Canonical Success Path**, the **Blocked Adversarial/Policy Violation Path**, and the **Interactive `/judge` Experience**.

---

## 🎯 System Overview (The 30-Second Elevator Pitch)
> "Traditional e-commerce platforms either give merchants static dashboards with no execution, or risky black-box AI chatbots that make unauthorized mistakes.
> 
> **Flowmint AI** is an autonomous revenue operating system for commerce. It constantly monitors telemetry for at-risk revenue, formulates bounded action plans, passes them through a deterministic policy and risk engine, enforces human-in-the-loop sign-off, executes atomically and idempotently, and attributes ground-truth financial outcomes."

---

## 🧭 Live Interactive Judge Mode (`/judge`)
Flowmint AI provides a single guided 12-step walkthrough accessible at `/judge` (or via the **Judge Walkthrough** tab in the sidebar). Judges do not need to hunt through menus:

- **Step 1: Revenue Command Center** — Telemetry overview, monthly GMV, ₹1,42,000 at-risk signal.
- **Step 2: Detected Opportunity** — Spike of 37 abandoned checkouts over the last 24 hours.
- **Step 3: Inspectable Evidence** — Raw telemetry JSON, eligible cohorts, and baseline statistics.
- **Step 4: AI Investigation** — Recovery Agent reasoning chain with read-only tool calls.
- **Step 5: What-if Simulation** — Deterministic Monte Carlo simulation testing a 10% discount (`SIMULATED`).
- **Step 6: ActionPlan Formulation** — Bounded proposal created with expiry, budget limits, and rollback.
- **Step 7: Policy Check** — Deterministic Policy Engine verifying 9 hard merchant rules.
- **Step 8: Risk Classification** — Automated classification as `MEDIUM` risk (external messaging + price change).
- **Step 9: Approval Gate** — Operator review and cryptographic approval record (`HITL`).
- **Step 10: Execution** — Atomic tool execution with idempotency lock (`apply_cart_recovery_offer`).
- **Step 11: Outcome** — Ground-truth recovered orders labeled `OBSERVED` (+₹8,865 net lift).
- **Step 12: Trace / Audit** — Full causal DAG reconstruction linking commerce event to ledger.

## 🤖 Live Fireworks AI Inference in Demo

Flowmint AI uses Fireworks AI's Qwen 3.8 Max model for live inference (`accounts/fireworks/models/qwen3p8-max`). MockLLM remains available for deterministic regression testing.

### Preferred Demonstration Story:
1. **Live Fireworks LLM Interaction:**
   - Buyer or Merchant enters natural language query (e.g. `"Find laptops or electronics under 70000"`).
   - Fireworks Qwen 3.8 Max processes the prompt and emits structured tool calls (`search_products`).
   - The tool executes strictly read-only queries against live PostgreSQL database catalog.
   - Grounded summary returned with zero hallucinations and zero database mutations.

2. **Deterministic Revenue Governance Transition:**
   - Once LLM reasoning is demonstrated, show the bounded-autonomy revenue lifecycle:
     - **Revenue Telemetry** &rarr; **Opportunity Detection** &rarr; **What-if Simulation** &rarr; **Policy Engine** &rarr; **Risk Engine** &rarr; **HITL Approval Gate** &rarr; **Atomic Execution** &rarr; **Attribution Ledger** &rarr; **Causal Audit Trail**.
   - Conclude with the **Scenario B: 25% Discount Rejection** to prove policy enforcement remains 100% deterministic and outside the LLM.

---


## 🏆 Scenario A: Canonical Success Demo (Cart Recovery)

### Step 1: Trigger / Detection
1. Merchant logs in to `admin@techmart.in`.
2. Navigate to **Opportunities** (`/opportunities`).
3. Observe `High Checkout Abandonment (₹1,42,000 at risk)` detected with 92% confidence.
4. Click **Inspect Evidence**:
   - 37 abandoned checkouts in the last 24h.
   - All 37 users outside the 24-hour contact cooldown window.
   - All cart items confirmed in stock.

### Step 2: What-if Simulation
1. Navigate to **Simulations** (`/simulations`).
2. Run simulation with `10.0% discount` on the 37 carts.
3. Observe deterministic math output:
   - Projected conversions: 9–11 carts.
   - Projected gross lift: ₹38,370.
   - Projected net impact: ₹34,533.
   - Label: `SIMULATED` (explicitly not claimed as actual bankable revenue).

### Step 3: ActionPlan & Policy Pass
1. ActionPlan `plan_rec_cart_019` is generated in `PROPOSED` state.
2. The Policy Engine runs:
   - Max discount cap: `10% <= 15%` &rarr; **PASS**.
   - Campaign budget: `₹3,837 <= ₹50,000` &rarr; **PASS**.
   - Cooldown: `24h` &rarr; **PASS**.
3. Risk Engine assigns **MEDIUM** risk &rarr; requires human approval.

### Step 4: Human-in-the-Loop Sign-off & Execution
1. Navigate to **Approvals** (`/approvals`).
2. Review ActionPlan bounds: 48h expiration, max 37 recipients, ₹15,000 budget cap.
3. Click **Approve Execution**.
4. Action executes atomically:
   - Idempotency key `idem_cart_recovery_...` is locked.
   - Duplicate attempts return existing execution without re-running.

### Step 5: Real Outcome & Attribution
1. Navigate to **Attribution** (`/attribution`).
2. Observe Canonical Benchmark Report:
   - Eligible carts: 37
   - Actual conversions: 3 orders completed
   - Gross revenue: ₹9,850
   - Discount cost: -₹985
   - Net revenue impact: **+₹8,865**
   - Label: `OBSERVED`
   - Attribution Method: `DETERMINISTIC EVENT LINK`

### Step 6: Complete Provenance Trace
1. Click **View Full Trace** or navigate to `/traces?id=tr_canon_cart_recovery_01`.
2. Inspect the 12-node causal DAG tracing the initial event to the final audit record.

---

## 🚫 Scenario B: Blocked Failure Demo (Adversarial Policy Violation)

### Objective
Prove that Flowmint AI strictly fails closed when an action violates merchant policy or agent permissions.

### Steps
1. Navigate to **Judge Mode** (`/judge`) and click **Blocked Failure Demo (25% Discount)**, or test via Policy Simulator in `/policies`.
2. An agent or adversary proposes an aggressive **25% discount** to recover stalled carts.
3. Merchant policy specifies: `max_discount_percentage: 15.0%`.
4. **Result:**
   - Policy Engine evaluates `rule_max_discount_cap`: `25.0% > 15.0%` &rarr; **REJECTED**.
   - Action status changes to `BLOCKED`.
   - Action is never forwarded to the Approval queue.
   - Tool execution is empirically verified to fail closed across tested scenarios.
   - An immutable audit log entry is written: `event_type="policy.violation_blocked"`.
   - Zero state mutation or discount leakage occurs.

---

## 🛡️ Security Controls Empirically Verified
- **No Direct Mutation:** Read-only agents cannot execute writes.
- **Fail-Closed Governance:** Policy violations halt execution immediately.
- **Strict Idempotency:** Duplicate execution requests are rejected via unique database constraints.
- **Attribution Separation:** Simulated and Estimated revenue are clearly separated from Observed cash.
- **Full Trace Provenance:** Every action links back to raw commerce telemetry.
