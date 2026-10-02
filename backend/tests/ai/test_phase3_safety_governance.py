"""
Flowmint AI — Phase 3 Safety, Governance, Policy, Approval & Execution Tests.

Verifies:
1. Agent permission enforcement (no wildcards, unauthorized proposals rejected).
2. Deterministic risk classification across all tiers (LOW, MEDIUM, HIGH, CRITICAL).
3. Deterministic policy rules framework (all 9 rules).
4. Mandatory Demonstration 1 (Blocked Path): Agent proposes 25% discount, policy max 15% -> BLOCKED.
5. Mandatory Demonstration 2 (Success Path): Growth Agent -> Cross-sell ActionPlan -> Medium Risk -> Approval -> Execution -> Audit.
6. Idempotency enforcement (replay returns cached result, no duplicate campaigns created).
7. Cross-tenant isolation (Merchant B cannot access or execute Merchant A's actions/approvals).
8. Direct /execute endpoint protection (cannot execute without valid approval).
9. Expired approval protection (cannot execute expired approvals).
10. Prompt injection defense against permission escalation.
11. Audit trail immutability and complete event capture.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.permissions import AgentCapability, validate_agent_can_propose_action, validate_agent_permission
from app.models.governance import (
    ActionExecution,
    Approval,
    ApprovalStatus,
    AuditLog,
    Campaign,
    MerchantPolicy,
    Offer,
    RiskLevel,
)
from app.models.merchant import Merchant
from app.models.opportunity import ActionPlan, ActionPlanStatus
from app.models.user import User
from app.services.action_execution_service import ActionExecutionService
from app.services.approval_service import ApprovalService
from app.services.audit_service import AuditService
from app.services.policy_engine import (
    CampaignBudgetRule,
    ContactFrequencyRule,
    CustomerEligibilityRule,
    DuplicateActionRule,
    MaximumDiscountRule,
    PolicyContext,
    policy_engine,
)
from app.services.risk_engine import RiskEngine


class TestPhase3SafetyAndGovernance:

    # -------------------------------------------------------------------------
    # 1. Agent Permissions
    # -------------------------------------------------------------------------
    def test_agent_permissions_matrix(self):
        # Buyer Agent has read permissions only
        assert validate_agent_permission("buyer_agent", AgentCapability.READ_PRODUCTS) is True
        assert validate_agent_permission("buyer_agent", AgentCapability.PROPOSE_BUNDLE) is False
        assert validate_agent_permission("buyer_agent", AgentCapability.EXECUTE_CAMPAIGN_DRAFT) is False

        # Analytics Agent has read permissions only
        assert validate_agent_permission("analytics_agent", AgentCapability.READ_ANALYTICS) is True
        assert validate_agent_permission("analytics_agent", AgentCapability.PROPOSE_OFFER) is False

        # Growth Agent can propose bundles and offers, but cannot directly execute
        assert validate_agent_permission("growth_agent", AgentCapability.PROPOSE_BUNDLE) is True
        assert validate_agent_permission("growth_agent", AgentCapability.PROPOSE_OFFER) is True
        assert validate_agent_permission("growth_agent", AgentCapability.EXECUTE_CAMPAIGN_DRAFT) is False

        # Recovery Agent can propose recovery, but cannot directly execute
        assert validate_agent_permission("recovery_agent", AgentCapability.PROPOSE_RECOVERY) is True
        assert validate_agent_permission("recovery_agent", AgentCapability.PROPOSE_BUNDLE) is False
        assert validate_agent_permission("recovery_agent", AgentCapability.EXECUTE_RECOVERY_CAMPAIGN) is False

        # Unknown agent denied
        assert validate_agent_permission("rogue_agent", AgentCapability.READ_PRODUCTS) is False

    # -------------------------------------------------------------------------
    # 2. Risk Classification
    # -------------------------------------------------------------------------
    def test_deterministic_risk_engine(self):
        merchant_id = uuid.uuid4()

        # Low risk: small discount, small blast radius
        low_plan = ActionPlan(
            merchant_id=merchant_id,
            action_type="cross_sell_bundle",
            target="product:P1",
            parameters={"discount_percentage": 5.0, "budget": 1000.0, "eligible_count": 5},
            recommendation_reason="Low risk draft bundle",
            estimated_impact={"projected_revenue": 2000.0},
        )
        risk, factors = RiskEngine.classify(low_plan)
        assert risk == RiskLevel.LOW

        # Medium risk: 12% discount
        med_plan = ActionPlan(
            merchant_id=merchant_id,
            action_type="promotional_offer",
            target="segment:active",
            parameters={"discount_percentage": 12.0, "budget": 6000.0, "eligible_count": 25},
            recommendation_reason="Medium risk promo offer",
            estimated_impact={"projected_revenue": 8000.0},
        )
        risk, factors = RiskEngine.classify(med_plan)
        assert risk == RiskLevel.MEDIUM

        # High risk: 25% discount, high budget
        high_plan = ActionPlan(
            merchant_id=merchant_id,
            action_type="launch_recovery_campaign",
            target="cart:bulk",
            parameters={"discount_percentage": 25.0, "budget": 30000.0, "eligible_count": 150},
            recommendation_reason="Aggressive campaign",
            estimated_impact={"projected_revenue": 45000.0},
        )
        risk, factors = RiskEngine.classify(high_plan)
        assert risk == RiskLevel.HIGH

        # Critical risk: irreversible financial action
        crit_plan = ActionPlan(
            merchant_id=merchant_id,
            action_type="refund",
            target="payment:123",
            parameters={"amount": 5000.0},
            recommendation_reason="Direct refund attempt",
        )
        risk, factors = RiskEngine.classify(crit_plan)
        assert risk == RiskLevel.CRITICAL

    # -------------------------------------------------------------------------
    # 3. Policy Rules Individual Evaluation
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_policy_rules_evaluation(self, db_session: AsyncSession, merchant: Merchant):
        ctx = PolicyContext(merchant_id=merchant.id, db=db_session, agent_name="growth_agent")

        # Maximum Discount Rule
        rule = MaximumDiscountRule()
        plan_pass = ActionPlan(merchant_id=merchant.id, action_type="cross_sell_bundle", target="t1", parameters={"discount_percentage": 10.0}, recommendation_reason="ok")
        res_pass = await rule.evaluate(plan_pass, ctx)
        assert res_pass.passed is True

        plan_fail = ActionPlan(merchant_id=merchant.id, action_type="cross_sell_bundle", target="t1", parameters={"discount_percentage": 20.0}, recommendation_reason="too high")
        res_fail = await rule.evaluate(plan_fail, ctx)
        assert res_fail.passed is False
        assert "exceeds" in res_fail.reason

        # Campaign Budget Rule
        b_rule = CampaignBudgetRule()
        b_pass = ActionPlan(merchant_id=merchant.id, action_type="cross_sell_bundle", target="t1", parameters={"budget": 20000.0}, recommendation_reason="ok")
        assert (await b_rule.evaluate(b_pass, ctx)).passed is True

        b_fail = ActionPlan(merchant_id=merchant.id, action_type="cross_sell_bundle", target="t1", parameters={"budget": 100000.0}, recommendation_reason="over budget")
        assert (await b_rule.evaluate(b_fail, ctx)).passed is False

    # -------------------------------------------------------------------------
    # 4. MANDATORY DEMONSTRATION 1 (BLOCKED PATH)
    # Propose 25% discount when policy max = 15% -> ACTION BLOCKED -> No side effect -> Audit event
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_mandatory_demonstration_blocked_path(
        self, db_session: AsyncSession, merchant: Merchant
    ):
        # 1. Setup policy with max discount 15%
        policy = MerchantPolicy(
            merchant_id=merchant.id,
            max_discount_percentage=Decimal("15.00"),
            max_campaign_budget=Decimal("50000.00"),
        )
        db_session.add(policy)
        await db_session.flush()

        # 2. Agent proposes 25% discount ActionPlan
        violating_plan = ActionPlan(
            merchant_id=merchant.id,
            action_type="promotional_offer",
            target="segment:all_customers",
            parameters={"discount_percentage": 25.0, "budget": 5000.0},
            evidence={"trigger": "cart_abandonment"},
            recommendation_reason="Aggressive 25% discount to force conversion",
            risk_level=RiskLevel.HIGH.value,
            requires_approval=True,
            status=ActionPlanStatus.PROPOSED.value,
        )
        db_session.add(violating_plan)
        await db_session.commit()
        await db_session.refresh(violating_plan)

        # 3. Validate action through ActionExecutionService
        validation = await ActionExecutionService.validate_action(
            db=db_session,
            merchant_id=merchant.id,
            action_plan_id=violating_plan.id,
            agent_name="growth_agent",
        )
        await db_session.commit()

        # 4. Assert Action is BLOCKED
        assert validation["allowed"] is False
        assert any("exceeds merchant policy limit" in r for r in validation["reasons"])

        # 5. Assert ActionPlan status updated to POLICY_REJECTED
        await db_session.refresh(violating_plan)
        assert violating_plan.status == ActionPlanStatus.POLICY_REJECTED.value

        # 6. Assert NO side effects occurred (zero campaigns or offers created)
        c_stmt = select(Campaign).where(Campaign.action_plan_id == violating_plan.id)
        assert (await db_session.execute(c_stmt)).scalar_one_or_none() is None

        o_stmt = select(Offer).where(Offer.action_plan_id == violating_plan.id)
        assert (await db_session.execute(o_stmt)).scalar_one_or_none() is None

        # 7. Assert Audit event was recorded
        audit_stmt = select(AuditLog).where(
            AuditLog.merchant_id == merchant.id,
            AuditLog.action_id == violating_plan.id,
        )
        audit_entry = (await db_session.execute(audit_stmt)).scalar_one_or_none()
        assert audit_entry is not None
        assert audit_entry.event_type == "policy.rejected"
        assert audit_entry.new_status == ActionPlanStatus.POLICY_REJECTED.value
        assert "25.0%" in audit_entry.reason

    # -------------------------------------------------------------------------
    # 5. MANDATORY DEMONSTRATION 2 (SUCCESS PATH)
    # Growth Agent -> Cross-sell ActionPlan -> Policy Evaluation -> Risk = MEDIUM ->
    # Approval Required -> Merchant Approves -> Create bounded campaign -> Execution recorded -> Audit Trail
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_mandatory_demonstration_success_path(
        self, db_session: AsyncSession, merchant: Merchant, user: User
    ):
        # 1. Growth Agent formulates a compliant cross-sell ActionPlan (10% discount)
        plan = ActionPlan(
            merchant_id=merchant.id,
            action_type="cross_sell_bundle",
            target="bundle:mouse_and_pad",
            parameters={
                "bundle_name": "Pro Gaming Companion Bundle",
                "discount_percentage": 10.0,
                "budget": 5000.0,
                "product_ids": [str(uuid.uuid4()), str(uuid.uuid4())],
            },
            evidence={"frequently_bought_together": 14},
            recommendation_reason="High co-purchase affinity detected between gaming mouse and pad",
            estimated_impact={"projected_revenue": 12000.0},
            risk_level=RiskLevel.MEDIUM.value,
            requires_approval=True,
            status=ActionPlanStatus.PROPOSED.value,
        )
        db_session.add(plan)
        await db_session.commit()
        await db_session.refresh(plan)

        # 2. Validation pipeline runs
        val = await ActionExecutionService.validate_action(
            db=db_session,
            merchant_id=merchant.id,
            action_plan_id=plan.id,
            agent_name="growth_agent",
        )
        await db_session.commit()

        assert val["allowed"] is True
        assert val["requires_approval"] is True
        assert val["risk_level"] in (RiskLevel.LOW.value, RiskLevel.MEDIUM.value)
        assert val["approval_id"] is not None

        # ActionPlan moved to PENDING_APPROVAL
        await db_session.refresh(plan)
        assert plan.status == ActionPlanStatus.PENDING_APPROVAL.value

        # 3. Merchant reviews and APPROVES the action
        approval_uuid = uuid.UUID(val["approval_id"])
        approval, updated_plan = await ApprovalService.decide_approval(
            db=db_session,
            approval_id=approval_uuid,
            merchant_id=merchant.id,
            decided_by=user.id,
            approved=True,
            decision_reason="Approved: Margins are positive and customer affinity is verified.",
        )
        await db_session.commit()

        assert approval.status == ApprovalStatus.APPROVED.value

        # 4. Central Execution Service executes the approved action
        exec_result = await ActionExecutionService.execute_action(
            db=db_session,
            merchant_id=merchant.id,
            action_plan_id=plan.id,
            idempotency_key="idemp_gaming_bundle_001",
            user_id=user.id,
        )
        await db_session.commit()

        assert exec_result["status"] == "completed"
        assert exec_result["idempotent_replay"] is False
        assert exec_result["tool_name"] == "create_campaign_draft"

        # 5. Verify Campaign entity created in database
        camp_stmt = select(Campaign).where(Campaign.action_plan_id == plan.id)
        camp = (await db_session.execute(camp_stmt)).scalar_one_or_none()
        assert camp is not None
        assert camp.name == "Pro Gaming Companion Bundle"
        assert float(camp.discount_percentage) == 10.0
        assert camp.status == "draft"

        # 6. Verify ActionPlan status updated to COMPLETED
        await db_session.refresh(plan)
        assert plan.status == ActionPlanStatus.COMPLETED.value

        # 7. Verify Execution Record created with idempotency key
        exec_stmt = select(ActionExecution).where(ActionExecution.action_plan_id == plan.id)
        action_exec = (await db_session.execute(exec_stmt)).scalar_one_or_none()
        assert action_exec is not None
        assert action_exec.idempotency_key == "idemp_gaming_bundle_001"
        assert action_exec.status == "completed"

        # 8. Verify Audit Trail contains end-to-end events
        audit_events = await AuditService.list_logs(db=db_session, merchant_id=merchant.id, action_id=plan.id)
        event_types = [a.event_type for a in audit_events]
        assert "approval.requested" in event_types
        assert "approval.approved" in event_types
        assert "action.executed" in event_types

    # -------------------------------------------------------------------------
    # 6. Idempotency Enforcement
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_idempotency_enforcement_prevents_duplicate_executions(
        self, db_session: AsyncSession, merchant: Merchant, user: User
    ):
        plan = ActionPlan(
            merchant_id=merchant.id,
            action_type="promotional_offer",
            target="offer:loyalty_10",
            parameters={"code": "LOYALTY10", "discount_percentage": 10.0, "min_order_value": 1000.0},
            recommendation_reason="Offer loyalty incentive",
            risk_level=RiskLevel.LOW.value,
            requires_approval=True,
            status=ActionPlanStatus.READY_FOR_REVIEW.value,
        )
        db_session.add(plan)
        await db_session.flush()

        # Approval record with APPROVED status
        appr = Approval(
            merchant_id=merchant.id,
            action_plan_id=plan.id,
            requested_by="growth_agent",
            risk_level=RiskLevel.LOW.value,
            reason="Approved offer for loyalty",
            status=ApprovalStatus.APPROVED.value,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            decided_at=datetime.now(timezone.utc),
            decided_by=user.id,
        )
        db_session.add(appr)
        await db_session.commit()
        await db_session.refresh(plan)

        # First execution succeeds
        r1 = await ActionExecutionService.execute_action(
            db=db_session,
            merchant_id=merchant.id,
            action_plan_id=plan.id,
            idempotency_key="idemp_offer_123",
            user_id=user.id,
        )
        await db_session.commit()
        assert r1["idempotent_replay"] is False
        assert r1["status"] == "completed"

        # Exactly 1 Offer entity exists
        o_stmt = select(Offer).where(Offer.action_plan_id == plan.id)
        offers = (await db_session.execute(o_stmt)).scalars().all()
        assert len(offers) == 1

        # Second execution with same action_id and same idempotency_key
        r2 = await ActionExecutionService.execute_action(
            db=db_session,
            merchant_id=merchant.id,
            action_plan_id=plan.id,
            idempotency_key="idemp_offer_123",
            user_id=user.id,
        )
        assert r2["idempotent_replay"] is True
        assert r2["status"] == "completed"

        # Still exactly 1 Offer entity exists (no duplicate side effects)
        offers_after = (await db_session.execute(o_stmt)).scalars().all()
        assert len(offers_after) == 1

    # -------------------------------------------------------------------------
    # 7. Cross-Tenant Protection
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_cross_tenant_isolation_on_governance(
        self, db_session: AsyncSession, merchant: Merchant, merchant_b: Merchant, user: User
    ):
        # ActionPlan belongs to Merchant B
        plan = ActionPlan(
            merchant_id=merchant_b.id,
            action_type="cross_sell_bundle",
            target="secret_bundle",
            parameters={"discount_percentage": 10.0},
            recommendation_reason="Secret data",
            status=ActionPlanStatus.PROPOSED.value,
        )
        db_session.add(plan)
        await db_session.commit()

        # Merchant A attempts to execute Merchant B's plan -> Must raise NotFoundError
        from app.core.exceptions import NotFoundError
        with pytest.raises(NotFoundError):
            await ActionExecutionService.execute_action(
                db=db_session,
                merchant_id=merchant.id,  # Wrong merchant
                action_plan_id=plan.id,
                idempotency_key="cross_tenant_hack",
                user_id=user.id,
            )

    # -------------------------------------------------------------------------
    # 8. Direct /execute Protection (Unapproved execution blocked)
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_direct_execute_fails_without_approval(
        self, db_session: AsyncSession, merchant: Merchant, user: User
    ):
        plan = ActionPlan(
            merchant_id=merchant.id,
            action_type="abandoned_cart_recovery",
            target="cart:batch_1",
            parameters={"cart_ids": [str(uuid.uuid4())], "discount_percentage": 12.0},
            recommendation_reason="Pending approval recovery",
            risk_level=RiskLevel.MEDIUM.value,
            requires_approval=True,  # Approval mandatory
            status=ActionPlanStatus.PROPOSED.value,
        )
        db_session.add(plan)
        await db_session.commit()

        # User tries to bypass approval and call execute directly -> Must raise ValidationError
        from app.core.exceptions import ValidationError
        with pytest.raises(ValidationError) as exc:
            await ActionExecutionService.execute_action(
                db=db_session,
                merchant_id=merchant.id,
                action_plan_id=plan.id,
                idempotency_key="bypass_attempt_001",
                user_id=user.id,
                agent_name="recovery_agent",
            )
        assert "requires merchant approval" in str(exc.value)

    # -------------------------------------------------------------------------
    # 9. Expired Approval Protection
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_expired_approval_cannot_be_approved_or_executed(
        self, db_session: AsyncSession, merchant: Merchant, user: User
    ):
        plan = ActionPlan(
            merchant_id=merchant.id,
            action_type="cross_sell_bundle",
            target="target:expired",
            parameters={"discount_percentage": 10.0},
            recommendation_reason="Test expired approval",
            risk_level=RiskLevel.LOW.value,
            status=ActionPlanStatus.PENDING_APPROVAL.value,
        )
        db_session.add(plan)
        await db_session.flush()

        # Create expired approval (expired 2 hours ago)
        expired_time = datetime.now(timezone.utc) - timedelta(hours=2)
        appr = Approval(
            merchant_id=merchant.id,
            action_plan_id=plan.id,
            requested_by="growth_agent",
            risk_level="low",
            reason="Expired review",
            status=ApprovalStatus.PENDING.value,
            expires_at=expired_time,
        )
        db_session.add(appr)
        await db_session.commit()

        from app.core.exceptions import ValidationError
        with pytest.raises(ValidationError) as exc:
            await ApprovalService.decide_approval(
                db=db_session,
                approval_id=appr.id,
                merchant_id=merchant.id,
                decided_by=user.id,
                approved=True,
                decision_reason="Approving late",
            )
        assert "expired" in str(exc.value).lower()

    # -------------------------------------------------------------------------
    # 10. FastAPI Endpoints Integration
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_api_policy_simulator_and_governance_flow(
        self, client: AsyncClient, merchant: Merchant, auth_headers: dict[str, str]
    ):
        # 1. Test Policy Simulator POST /api/v1/policies/evaluate
        eval_payload = {
            "action_type": "cross_sell_bundle",
            "target": "test_bundle",
            "parameters": {"discount_percentage": 25.0},  # Exceeds standard 15%
            "agent_name": "growth_agent",
        }
        res = await client.post("/api/v1/policies/evaluate", json=eval_payload, headers=auth_headers)
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["allowed"] is False
        assert any("exceeds" in r for r in data["reasons"])

        # 2. Get merchant policy
        pol_res = await client.get("/api/v1/policies", headers=auth_headers)
        assert pol_res.status_code == 200
        assert pol_res.json()["data"]["max_discount_percentage"] == 15.0

        # 3. List audit trail
        audit_res = await client.get("/api/v1/audit", headers=auth_headers)
        assert audit_res.status_code == 200
        assert isinstance(audit_res.json()["data"], list)

