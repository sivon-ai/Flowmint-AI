# Flowmint AI — Revenue Attribution Engine

## Overview

The Flowmint AI Revenue Attribution Engine closes the loop between AI intelligence and verified business outcomes. It translates autonomous and approval-gated actions into measurable financial accounting:

$$\text{Opportunity} \to \text{ActionPlan} \to \text{Approval} \to \text{Execution} \to \text{Affected Entities} \to \text{Observed Outcome} \to \text{Attribution}$$

---

## Strict Label Hierarchy

To prevent inflated or manufactured ROI claims, Flowmint AI enforces an immutable metric taxonomy across all APIs and user interfaces:

| Label | Meaning | When Used |
|---|---|---|
| `SIMULATED` | Theoretical projection computed using What-If counterfactual formulas. | In the Simulation Workbench before action formulation. |
| `ESTIMATED` | Expected recovery or revenue generated during ActionPlan proposal. | On pending ActionPlans and human approval cards. |
| `OBSERVED` | Real completed order transactions verified in the database. | After execution during observation window. |
| `ATTRIBUTED` | Statistically adjusted impact using difference-in-differences or cohort matching. | In merchant ROI reports and ledger analytics. |

> [!CAUTION]
> Projected or simulated revenue must **NEVER** be reported as actual recovered revenue.

---

## Net Revenue Impact Formula

All financial ledger entries record both gross and deduction metrics deterministically:

$$\text{Net Revenue Impact} = \text{Gross Recovered Revenue} - \text{Discount Cost} - \text{Operational Cost}$$

Example from Canonical Demo:
- **Campaign**: 10% Abandoned Cart Recovery Offer
- **Eligible Entities**: 37 abandoned carts (₹1,42,000 at risk)
- **Actual Recoveries**: 7 completed checkout orders
- **Observed Gross Revenue**: ₹9,850.00
- **Discount Cost (10%)**: ₹985.00
- **Operational Cost**: ₹0.00
- **Observed Net Revenue Impact**: **+₹8,865.00**
- **Confidence**: 1.000 (100% deterministic event attribution)

---

## Database Architecture (`action_outcomes`)

```sql
CREATE TABLE action_outcomes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id UUID NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    action_id UUID NOT NULL REFERENCES action_plans(id) ON DELETE CASCADE,
    execution_id UUID REFERENCES action_executions(id) ON DELETE SET NULL,
    campaign_id UUID REFERENCES campaigns(id) ON DELETE SET NULL,
    opportunity_id UUID REFERENCES opportunities(id) ON DELETE SET NULL,
    trace_id VARCHAR(100),
    label VARCHAR(20) NOT NULL, -- SIMULATED, ESTIMATED, OBSERVED, ATTRIBUTED
    attribution_method VARCHAR(50) NOT NULL, -- deterministic_event, rule_based, etc.
    confidence NUMERIC(4, 3) NOT NULL DEFAULT 1.000,
    baseline_period JSONB NOT NULL DEFAULT '{}',
    observation_period JSONB NOT NULL DEFAULT '{}',
    affected_entities JSONB NOT NULL DEFAULT '{}',
    orders_attributed INTEGER NOT NULL DEFAULT 0,
    gross_revenue NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    discount_cost NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    operational_cost NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    net_revenue_impact NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## Attribution Methods

1. **`deterministic_event`**: Exact order checkout matching discount codes, recovered cart IDs, or payment retry links created by the execution tool.
2. **`rule_based`**: Time-window correlation within a 24-hour observation window of campaign delivery.
3. **`difference_in_differences`**: Comparison of conversion rate delta between targeted cart cohort vs untreated control group.
4. **`cohort_analysis`**: Longitudinal customer repeat purchase and LTV tracking.
