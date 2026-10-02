"""
Flowmint AI — Policy Rule Framework & Policy Engine (Phase 3).

Evaluates ActionPlans against deterministic merchant policies.
The LLM is strictly prohibited from deciding whether policies pass.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.permissions import validate_agent_can_propose_action
from app.models.governance import ActionExecution, MerchantPolicy
from app.models.opportunity import ActionPlan, ActionPlanStatus


@dataclass
class PolicyContext:
    merchant_id: uuid.UUID
    db: AsyncSession
    policy: MerchantPolicy | None = None
    agent_name: str = "growth_agent"
    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PolicyRuleResult:
    rule: str
    passed: bool
    severity: str  # "BLOCK" or "WARN"
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicyEvaluationResult:
    allowed: bool
    requires_approval: bool
    risk_level: str
    reasons: list[str]
    rule_results: list[PolicyRuleResult]
    evidence_snapshot: dict[str, Any]


class BasePolicyRule(ABC):
    name: str
    severity: str = "BLOCK"

    @abstractmethod
    async def evaluate(self, action_plan: ActionPlan, context: PolicyContext) -> PolicyRuleResult:
        pass


class MaximumDiscountRule(BasePolicyRule):
    name = "maximum_discount"
    severity = "BLOCK"

    async def evaluate(self, action_plan: ActionPlan, context: PolicyContext) -> PolicyRuleResult:
        p = action_plan.parameters or {}
        discount = Decimal(str(p.get("discount_percentage", 0)))
        max_allowed = context.policy.max_discount_percentage if context.policy else Decimal("15.00")

        if discount > max_allowed:
            return PolicyRuleResult(
                rule=self.name,
                passed=False,
                severity=self.severity,
                reason=f"Proposed discount of {discount}% exceeds merchant policy limit of {max_allowed}%.",
                evidence={"proposed_discount": float(discount), "max_allowed_discount": float(max_allowed)},
            )
        return PolicyRuleResult(
            rule=self.name,
            passed=True,
            severity=self.severity,
            reason=f"Discount of {discount}% is within policy limit ({max_allowed}%).",
            evidence={"proposed_discount": float(discount), "max_allowed_discount": float(max_allowed)},
        )


class CampaignBudgetRule(BasePolicyRule):
    name = "campaign_budget"
    severity = "BLOCK"

    async def evaluate(self, action_plan: ActionPlan, context: PolicyContext) -> PolicyRuleResult:
        p = action_plan.parameters or {}
        budget = Decimal(str(p.get("budget", 0)))
        max_budget = context.policy.max_campaign_budget if context.policy else Decimal("50000.00")

        if budget > max_budget:
            return PolicyRuleResult(
                rule=self.name,
                passed=False,
                severity=self.severity,
                reason=f"Campaign budget of ₹{budget} exceeds maximum allowable budget of ₹{max_budget}.",
                evidence={"proposed_budget": float(budget), "max_allowed_budget": float(max_budget)},
            )
        return PolicyRuleResult(
            rule=self.name,
            passed=True,
            severity=self.severity,
            reason=f"Campaign budget ₹{budget} is within policy allocation (₹{max_budget}).",
            evidence={"proposed_budget": float(budget), "max_allowed_budget": float(max_budget)},
        )


class CustomerEligibilityRule(BasePolicyRule):
    name = "customer_eligibility"
    severity = "BLOCK"

    async def evaluate(self, action_plan: ActionPlan, context: PolicyContext) -> PolicyRuleResult:
        p = action_plan.parameters or {}
        # Must have valid target entities
        cart_ids = p.get("cart_ids") or []
        target = action_plan.target

        if not target and not cart_ids:
            return PolicyRuleResult(
                rule=self.name,
                passed=False,
                severity=self.severity,
                reason="Action lacks identifiable customer or cart target criteria.",
                evidence={"target": target, "cart_ids": cart_ids},
            )

        # Minimum order value verification if promo
        min_val = Decimal(str(p.get("min_cart_value", 0)))
        if min_val < 0:
            return PolicyRuleResult(
                rule=self.name,
                passed=False,
                severity=self.severity,
                reason="Negative minimum cart value threshold is invalid.",
                evidence={"min_cart_value": float(min_val)},
            )

        return PolicyRuleResult(
            rule=self.name,
            passed=True,
            severity=self.severity,
            reason="Customer and entity eligibility criteria verified.",
            evidence={"target": target, "entity_count": len(cart_ids)},
        )


class ContactFrequencyRule(BasePolicyRule):
    name = "contact_frequency"
    severity = "BLOCK"

    async def evaluate(self, action_plan: ActionPlan, context: PolicyContext) -> PolicyRuleResult:
        cooldown_hours = context.policy.contact_cooldown_hours if context.policy else 24
        cutoff = context.now - timedelta(hours=cooldown_hours)

        # Query recent executions on the same target
        stmt = (
            select(ActionExecution)
            .join(ActionPlan, ActionExecution.action_plan_id == ActionPlan.id)
            .where(
                and_(
                    ActionExecution.merchant_id == context.merchant_id,
                    ActionPlan.target == action_plan.target,
                    ActionExecution.started_at >= cutoff,
                    ActionExecution.status.in_(["executing", "completed"]),
                )
            )
            .limit(1)
        )
        res = await context.db.execute(stmt)
        recent_execution = res.scalar_one_or_none()

        if recent_execution:
            return PolicyRuleResult(
                rule=self.name,
                passed=False,
                severity=self.severity,
                reason=f"Target '{action_plan.target}' was contacted within cooldown period ({cooldown_hours} hours).",
                evidence={"cooldown_hours": cooldown_hours, "last_executed_at": recent_execution.started_at.isoformat()},
            )

        return PolicyRuleResult(
            rule=self.name,
            passed=True,
            severity=self.severity,
            reason=f"Target complies with contact frequency limits ({cooldown_hours}h cooldown).",
            evidence={"cooldown_hours": cooldown_hours},
        )


class AgentPermissionRule(BasePolicyRule):
    name = "agent_permission"
    severity = "BLOCK"

    async def evaluate(self, action_plan: ActionPlan, context: PolicyContext) -> PolicyRuleResult:
        can_propose, reason = validate_agent_can_propose_action(context.agent_name, action_plan.action_type)
        if not can_propose:
            return PolicyRuleResult(
                rule=self.name,
                passed=False,
                severity=self.severity,
                reason=reason,
                evidence={"agent_name": context.agent_name, "action_type": action_plan.action_type},
            )
        return PolicyRuleResult(
            rule=self.name,
            passed=True,
            severity=self.severity,
            reason=f"Agent '{context.agent_name}' has verified permission for '{action_plan.action_type}'.",
            evidence={"agent_name": context.agent_name, "action_type": action_plan.action_type},
        )


class HighValueActionRule(BasePolicyRule):
    name = "high_value_action"
    severity = "WARN"

    async def evaluate(self, action_plan: ActionPlan, context: PolicyContext) -> PolicyRuleResult:
        high_threshold = context.policy.high_value_threshold if context.policy else Decimal("10000.00")
        p = action_plan.parameters or {}
        budget = Decimal(str(p.get("budget", 0)))
        est_impact = Decimal(str(action_plan.estimated_impact.get("projected_revenue", 0) if action_plan.estimated_impact else 0))

        is_high_val = budget >= high_threshold or est_impact >= high_threshold

        if is_high_val:
            return PolicyRuleResult(
                rule=self.name,
                passed=True,  # Doesn't block, but triggers mandatory human approval
                severity=self.severity,
                reason=f"Action value (₹{max(budget, est_impact)}) meets or exceeds high-value threshold (₹{high_threshold}). Mandatory human approval required.",
                evidence={"is_high_value": True, "threshold": float(high_threshold)},
            )
        return PolicyRuleResult(
            rule=self.name,
            passed=True,
            severity=self.severity,
            reason="Action value is below high-value threshold.",
            evidence={"is_high_value": False, "threshold": float(high_threshold)},
        )


class DuplicateActionRule(BasePolicyRule):
    name = "duplicate_action"
    severity = "BLOCK"

    async def evaluate(self, action_plan: ActionPlan, context: PolicyContext) -> PolicyRuleResult:
        # Check if identical action is already pending or executing
        cutoff = context.now - timedelta(hours=24)
        stmt = select(ActionPlan).where(
            and_(
                ActionPlan.merchant_id == context.merchant_id,
                ActionPlan.id != action_plan.id,
                ActionPlan.action_type == action_plan.action_type,
                ActionPlan.target == action_plan.target,
                ActionPlan.status.in_([
                    ActionPlanStatus.PROPOSED.value,
                    ActionPlanStatus.VALIDATING.value,
                    ActionPlanStatus.PENDING_APPROVAL.value,
                    ActionPlanStatus.EXECUTING.value,
                ]),
                ActionPlan.created_at >= cutoff,
            )
        ).limit(1)
        res = await context.db.execute(stmt)
        dup = res.scalar_one_or_none()

        if dup:
            return PolicyRuleResult(
                rule=self.name,
                passed=False,
                severity=self.severity,
                reason=f"Active duplicate action plan '{dup.id}' already exists for target '{action_plan.target}'.",
                evidence={"duplicate_action_plan_id": str(dup.id)},
            )
        return PolicyRuleResult(
            rule=self.name,
            passed=True,
            severity=self.severity,
            reason="No conflicting active duplicate action found.",
            evidence={},
        )


class MerchantSpecificRestrictionRule(BasePolicyRule):
    name = "merchant_specific_restriction"
    severity = "BLOCK"

    async def evaluate(self, action_plan: ActionPlan, context: PolicyContext) -> PolicyRuleResult:
        policy = context.policy
        if not policy:
            return PolicyRuleResult(
                rule=self.name,
                passed=True,
                severity=self.severity,
                reason="Default policy active; no merchant-specific restrictions.",
                evidence={},
            )

        # Check allowed action types
        if policy.allowed_action_types and action_plan.action_type not in policy.allowed_action_types:
            return PolicyRuleResult(
                rule=self.name,
                passed=False,
                severity=self.severity,
                reason=f"Action type '{action_plan.action_type}' is disabled by merchant configuration.",
                evidence={"allowed_types": policy.allowed_action_types},
            )

        # Check restricted product IDs
        p = action_plan.parameters or {}
        prod_ids = [str(pid) for pid in (p.get("product_ids") or [])]
        restricted = [str(r) for r in (policy.restricted_product_ids or [])]

        violating = set(prod_ids).intersection(set(restricted))
        if violating:
            return PolicyRuleResult(
                rule=self.name,
                passed=False,
                severity=self.severity,
                reason=f"Action includes restricted merchant products: {list(violating)}",
                evidence={"violating_products": list(violating)},
            )

        return PolicyRuleResult(
            rule=self.name,
            passed=True,
            severity=self.severity,
            reason="Merchant-specific restrictions passed.",
            evidence={},
        )


class ActionExpiryRule(BasePolicyRule):
    name = "action_expiry"
    severity = "BLOCK"

    async def evaluate(self, action_plan: ActionPlan, context: PolicyContext) -> PolicyRuleResult:
        if action_plan.created_at:
            age_hours = (context.now - action_plan.created_at).total_seconds() / 3600
            if age_hours > 72:
                return PolicyRuleResult(
                    rule=self.name,
                    passed=False,
                    severity=self.severity,
                    reason=f"Action proposal expired ({age_hours:.1f} hours old, max allowed is 72h).",
                    evidence={"age_hours": age_hours},
                )
        return PolicyRuleResult(
            rule=self.name,
            passed=True,
            severity=self.severity,
            reason="Action proposal is active and within valid time window.",
            evidence={},
        )


class PolicyEngine:
    """
    Central Policy Engine: Evaluates ActionPlans against all 9 policy rules.
    """

    def __init__(self):
        self.rules: list[BasePolicyRule] = [
            AgentPermissionRule(),
            MaximumDiscountRule(),
            CampaignBudgetRule(),
            CustomerEligibilityRule(),
            ContactFrequencyRule(),
            HighValueActionRule(),
            DuplicateActionRule(),
            MerchantSpecificRestrictionRule(),
            ActionExpiryRule(),
        ]

    async def evaluate(self, action_plan: ActionPlan, context: PolicyContext) -> PolicyEvaluationResult:
        rule_results: list[PolicyRuleResult] = []
        blocking_reasons: list[str] = []
        is_high_value = False

        for rule in self.rules:
            res = await rule.evaluate(action_plan, context)
            rule_results.append(res)
            if not res.passed and res.severity == "BLOCK":
                blocking_reasons.append(res.reason)
            if rule.name == "high_value_action" and res.evidence.get("is_high_value"):
                is_high_value = True

        allowed = len(blocking_reasons) == 0

        # Determine approval requirement:
        # Requires approval if merchant policy mandates it, OR high-value, OR risk >= medium
        policy_mandates = context.policy.require_approval_all_actions if context.policy else True
        requires_approval = policy_mandates or is_high_value or action_plan.requires_approval

        # Gather evidence snapshot
        evidence_snapshot = {
            res.rule: {
                "passed": res.passed,
                "reason": res.reason,
                "evidence": res.evidence,
            }
            for res in rule_results
        }

        from app.services.risk_engine import RiskEngine

        risk_level, _ = RiskEngine.classify(action_plan, context.policy)

        return PolicyEvaluationResult(
            allowed=allowed,
            requires_approval=requires_approval,
            risk_level=risk_level.value,
            reasons=blocking_reasons if not allowed else ["All policy checks passed."],
            rule_results=rule_results,
            evidence_snapshot=evidence_snapshot,
        )


# Global policy engine instance
policy_engine = PolicyEngine()
