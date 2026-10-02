"""
Flowmint AI — Action Execution Service & Pipeline (Phase 3).

Central coordinator for bounded revenue actions.
Enforces the mandatory pipeline:
ActionPlan → Permission → Policy → Risk → Approval → Idempotency → Controlled Tool → Audit.
The LLM is strictly prohibited from bypassing this pipeline.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.permissions import validate_agent_can_propose_action
from app.ai.tools.base import ToolContext
from app.ai.tools.write_tools import controlled_write_registry
from app.core.exceptions import NotFoundError, ValidationError
from app.models.governance import (
    ActionExecution,
    Approval,
    ApprovalStatus,
    ExecutionStatus,
    MerchantPolicy,
)
from app.models.opportunity import ActionPlan, ActionPlanStatus, Opportunity, OpportunityStatus
from app.services.approval_service import ApprovalService
from app.services.audit_service import AuditService
from app.services.policy_engine import PolicyContext, policy_engine
from app.services.risk_engine import RiskEngine


class ActionExecutionService:
    """
    Central execution service enforcing safety, policy, approval, and idempotency invariants.
    """

    @staticmethod
    async def validate_action(
        db: AsyncSession,
        merchant_id: uuid.UUID,
        action_plan_id: uuid.UUID,
        agent_name: str = "growth_agent",
    ) -> dict[str, Any]:
        """
        Validates an ActionPlan against Agent permissions and Policy rules.
        Does NOT execute any write tool.
        """
        stmt = (
            select(ActionPlan)
            .where(
                ActionPlan.id == action_plan_id,
                ActionPlan.merchant_id == merchant_id,
            )
        )
        res = await db.execute(stmt)
        action_plan = res.scalar_one_or_none()
        if not action_plan:
            raise NotFoundError(f"Action plan '{action_plan_id}' not found")

        # Load merchant policy if configured
        pol_stmt = select(MerchantPolicy).where(
            MerchantPolicy.merchant_id == merchant_id,
            MerchantPolicy.is_active == True,
        )
        pol_res = await db.execute(pol_stmt)
        policy = pol_res.scalar_one_or_none()

        # Permission check
        can_propose, perm_reason = validate_agent_can_propose_action(agent_name, action_plan.action_type)
        if not can_propose:
            action_plan.status = ActionPlanStatus.POLICY_REJECTED.value
            await db.flush()
            await AuditService.log_event(
                db=db,
                merchant_id=merchant_id,
                actor_type="agent",
                actor_id=agent_name,
                action_id=action_plan.id,
                agent=agent_name,
                event_type="action.blocked",
                previous_status=ActionPlanStatus.PROPOSED.value,
                new_status=ActionPlanStatus.POLICY_REJECTED.value,
                reason=perm_reason,
            )
            return {
                "allowed": False,
                "requires_approval": True,
                "reasons": [perm_reason],
                "risk_level": "critical",
                "rule_results": [],
            }

        # Policy Engine evaluation
        context = PolicyContext(
            merchant_id=merchant_id,
            db=db,
            policy=policy,
            agent_name=agent_name,
        )
        evaluation = await policy_engine.evaluate(action_plan, context)

        if not evaluation.allowed:
            action_plan.status = ActionPlanStatus.POLICY_REJECTED.value
            await db.flush()
            await AuditService.log_event(
                db=db,
                merchant_id=merchant_id,
                actor_type="system",
                actor_id="policy_engine",
                action_id=action_plan.id,
                agent=agent_name,
                event_type="policy.rejected",
                previous_status=ActionPlanStatus.PROPOSED.value,
                new_status=ActionPlanStatus.POLICY_REJECTED.value,
                reason="; ".join(evaluation.reasons),
                policy_results=evaluation.evidence_snapshot,
            )
            return {
                "allowed": False,
                "requires_approval": False,
                "approval_id": None,
                "risk_level": evaluation.risk_level,
                "reasons": evaluation.reasons,
                "rule_results": [
                    {
                        "rule": r.rule,
                        "passed": r.passed,
                        "severity": r.severity,
                        "reason": r.reason,
                        "evidence": r.evidence,
                    }
                    for r in evaluation.rule_results
                ],
            }

        # If allowed and requires approval, generate approval request
        if evaluation.requires_approval:
            action_plan.status = ActionPlanStatus.PENDING_APPROVAL.value
            approval = await ApprovalService.create_approval(
                db=db,
                merchant_id=merchant_id,
                action_plan_id=action_plan.id,
                requested_by=agent_name,
                risk_level=evaluation.risk_level,
                reason=f"Action '{action_plan.action_type}' requires human review: {action_plan.recommendation_reason}",
                policy_snapshot=evaluation.evidence_snapshot,
            )
            approval_id = str(approval.id)
        else:
            action_plan.status = ActionPlanStatus.AUTO_APPROVED.value
            approval_id = None

        await db.flush()

        return {
            "allowed": True,
            "requires_approval": evaluation.requires_approval,
            "approval_id": approval_id,
            "risk_level": evaluation.risk_level,
            "reasons": evaluation.reasons,
            "rule_results": [
                {
                    "rule": r.rule,
                    "passed": r.passed,
                    "severity": r.severity,
                    "reason": r.reason,
                    "evidence": r.evidence,
                }
                for r in evaluation.rule_results
            ],
        }

    validate_action_plan = validate_action

    @staticmethod
    async def execute_action(
        db: AsyncSession,
        merchant_id: uuid.UUID,
        action_plan_id: uuid.UUID,
        idempotency_key: str,
        user_id: uuid.UUID | None = None,
        agent_name: str = "growth_agent",
    ) -> dict[str, Any]:
        """
        Executes a validated, approved ActionPlan through the appropriate controlled write tool.
        Strictly enforces permission, policy, risk, approval, and idempotency checks.
        """
        if not idempotency_key or not idempotency_key.strip():
            raise ValidationError("Idempotency key is required for action execution")

        # 1. Tenant-isolated lookup
        stmt = (
            select(ActionPlan)
            .options(selectinload(ActionPlan.opportunity))
            .where(
                ActionPlan.id == action_plan_id,
                ActionPlan.merchant_id == merchant_id,
            )
        )
        res = await db.execute(stmt)
        action_plan = res.scalar_one_or_none()
        if not action_plan:
            raise NotFoundError(f"Action plan '{action_plan_id}' not found")

        # 2. Idempotency Check: Prior execution by ActionPlan ID
        existing_exec_stmt = select(ActionExecution).where(
            ActionExecution.merchant_id == merchant_id,
            ActionExecution.action_plan_id == action_plan.id,
            ActionExecution.status == ExecutionStatus.COMPLETED.value,
        )
        existing_exec_res = await db.execute(existing_exec_stmt)
        existing_exec = existing_exec_res.scalar_one_or_none()
        if existing_exec:
            return {
                "status": "completed",
                "idempotent_replay": True,
                "execution_id": str(existing_exec.id),
                "action_id": str(action_plan.id),
                "tool_name": existing_exec.tool_name,
                "result": existing_exec.tool_result,
                "message": "Action previously completed; returning cached idempotent execution result.",
            }

        # Idempotency Check: Prior execution by idempotency_key
        key_exec_stmt = select(ActionExecution).where(
            ActionExecution.merchant_id == merchant_id,
            ActionExecution.idempotency_key == idempotency_key,
        )
        key_exec_res = await db.execute(key_exec_stmt)
        key_exec = key_exec_res.scalar_one_or_none()
        if key_exec and key_exec.status == ExecutionStatus.COMPLETED.value:
            return {
                "status": "completed",
                "idempotent_replay": True,
                "execution_id": str(key_exec.id),
                "action_id": str(action_plan.id),
                "tool_name": key_exec.tool_name,
                "result": key_exec.tool_result,
                "message": "Idempotency key previously executed; returning cached result.",
            }

        # 3. Re-verify Policy Constraints
        pol_stmt = select(MerchantPolicy).where(
            MerchantPolicy.merchant_id == merchant_id,
            MerchantPolicy.is_active == True,
        )
        pol_res = await db.execute(pol_stmt)
        policy = pol_res.scalar_one_or_none()

        context = PolicyContext(
            merchant_id=merchant_id,
            db=db,
            policy=policy,
            agent_name=agent_name,
        )
        evaluation = await policy_engine.evaluate(action_plan, context)
        if not evaluation.allowed:
            action_plan.status = ActionPlanStatus.POLICY_REJECTED.value
            await db.flush()
            await AuditService.log_event(
                db=db,
                merchant_id=merchant_id,
                actor_type="user" if user_id else "agent",
                actor_id=str(user_id or agent_name),
                action_id=action_plan.id,
                event_type="action.blocked",
                previous_status=action_plan.status,
                new_status=ActionPlanStatus.POLICY_REJECTED.value,
                reason="Policy violation during execution attempt: " + "; ".join(evaluation.reasons),
                policy_results=evaluation.evidence_snapshot,
            )
            raise ValidationError(f"Action blocked by policy: {'; '.join(evaluation.reasons)}")

        # 4. Re-verify Approval Requirements
        if evaluation.requires_approval or action_plan.requires_approval:
            appr_stmt = (
                select(Approval)
                .where(
                    Approval.merchant_id == merchant_id,
                    Approval.action_plan_id == action_plan.id,
                )
                .order_by(Approval.created_at.desc())
            )
            appr_res = await db.execute(appr_stmt)
            approval = appr_res.scalar_one_or_none()

            now = datetime.now(timezone.utc)
            if not approval:
                # Create pending approval
                await ApprovalService.create_approval(
                    db=db,
                    merchant_id=merchant_id,
                    action_plan_id=action_plan.id,
                    requested_by=agent_name,
                    risk_level=evaluation.risk_level,
                    reason=action_plan.recommendation_reason,
                    policy_snapshot=evaluation.evidence_snapshot,
                )
                raise ValidationError("Action requires merchant approval before execution. Approval request created.")

            if approval.status == ApprovalStatus.PENDING.value:
                if approval.expires_at < now:
                    approval.status = ApprovalStatus.EXPIRED.value
                    await db.flush()
                    raise ValidationError("Approval request for this action has expired.")
                raise ValidationError("Action is pending merchant approval.")
            elif approval.status == ApprovalStatus.REJECTED.value:
                raise ValidationError(f"Action was explicitly rejected: {approval.decision_reason}")
            elif approval.status == ApprovalStatus.EXPIRED.value:
                raise ValidationError("Approval request for this action has expired.")
            elif approval.status != ApprovalStatus.APPROVED.value:
                raise ValidationError(f"Invalid approval status '{approval.status}' for execution.")

        # 5. Record Execution In-Progress (Atomic lock with DB UniqueConstraint)
        execution = ActionExecution(
            merchant_id=merchant_id,
            action_plan_id=action_plan.id,
            idempotency_key=idempotency_key,
            status=ExecutionStatus.EXECUTING.value,
            tool_name="controlled_tool",
            tool_parameters=action_plan.parameters,
            tool_result={},
            started_at=datetime.now(timezone.utc),
        )
        db.add(execution)
        action_plan.status = ActionPlanStatus.EXECUTING.value
        await db.flush()

        # 6. Map to Controlled Write Tool & Execute
        tool_name = "create_campaign_draft"
        tool_params: dict[str, Any] = {
            "name": f"Action-{action_plan.action_type.replace('_', ' ').title()}",
            "action_plan_id": str(action_plan.id),
        }

        p = action_plan.parameters or {}
        if action_plan.action_type in ("abandoned_cart_recovery", "payment_retry_nudge"):
            tool_name = "launch_recovery_campaign"
            tool_params = {
                "name": p.get("campaign_name", f"Cart Recovery {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"),
                "cart_ids": p.get("cart_ids", []),
                "discount_percentage": float(p.get("discount_percentage", 10.0)),
                "action_plan_id": str(action_plan.id),
            }
        elif action_plan.action_type == "promotional_offer":
            tool_name = "create_offer"
            tool_params = {
                "code": p.get("code", f"OFFER{uuid.uuid4().hex[:6].upper()}"),
                "discount_percentage": float(p.get("discount_percentage", 10.0)),
                "min_order_value": float(p.get("min_order_value", 0.0)),
                "validity_days": int(p.get("validity_days", 7)),
                "action_plan_id": str(action_plan.id),
            }
        else:  # cross_sell_bundle, etc.
            tool_name = "create_campaign_draft"
            tool_params = {
                "name": p.get("bundle_name", f"Bundle Deal {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"),
                "campaign_type": "cross_sell_bundle",
                "discount_percentage": float(p.get("discount_percentage", 10.0)),
                "budget": float(p.get("budget", 1000.0)),
                "target_criteria": {"product_ids": p.get("product_ids", [])},
                "action_plan_id": str(action_plan.id),
            }

        execution.tool_name = tool_name
        execution.tool_parameters = tool_params

        tool = controlled_write_registry.get(tool_name)
        if not tool:
            execution.status = ExecutionStatus.FAILED.value
            execution.error_message = f"Controlled tool '{tool_name}' not registered"
            action_plan.status = ActionPlanStatus.FAILED.value
            await db.flush()
            raise ValidationError(f"Execution failed: {execution.error_message}")

        tool_ctx = ToolContext(
            merchant_id=merchant_id,
            user_id=user_id,
            trace_id=f"trc_exec_{uuid.uuid4().hex[:12]}",
            db=db,
            is_read_only=False,  # Authorized write execution
        )

        tool_result = await tool.execute(tool_params, tool_ctx)

        # 7. Finalize State & Record Audit Log
        if tool_result.success:
            execution.status = ExecutionStatus.COMPLETED.value
            execution.tool_result = tool_result.data or {}
            execution.completed_at = datetime.now(timezone.utc)
            action_plan.status = ActionPlanStatus.COMPLETED.value

            # If linked to an Opportunity, mark it RESOLVED
            if action_plan.opportunity:
                action_plan.opportunity.status = OpportunityStatus.RESOLVED.value
                action_plan.opportunity.resolved_at = datetime.now(timezone.utc)

            await AuditService.log_event(
                db=db,
                merchant_id=merchant_id,
                actor_type="user" if user_id else "system",
                actor_id=str(user_id or "ActionExecutionService"),
                action_id=action_plan.id,
                event_type="action.executed",
                previous_status=ActionPlanStatus.EXECUTING.value,
                new_status=ActionPlanStatus.COMPLETED.value,
                reason=f"Action executed via tool '{tool_name}' successfully.",
                execution_result=tool_result.data,
                trace_id=tool_ctx.trace_id,
            )
            await db.flush()

            # Phase 4: Automatically link executed action to Attribution Engine
            try:
                from app.services.attribution_service import AttributionService
                await AttributionService.record_outcome_for_execution(
                    db=db,
                    merchant_id=merchant_id,
                    action_plan_id=action_plan.id,
                    execution_id=execution.id,
                )
            except Exception as attr_err:
                logger.warning(f"Attribution recording warning: {attr_err}")

            return {
                "status": "completed",
                "idempotent_replay": False,
                "execution_id": str(execution.id),
                "action_id": str(action_plan.id),
                "tool_name": tool_name,
                "result": tool_result.data,
                "message": tool_result.message or "Action executed successfully.",
            }
        else:
            execution.status = ExecutionStatus.FAILED.value
            execution.error_message = tool_result.error or "Unknown error"
            execution.completed_at = datetime.now(timezone.utc)
            action_plan.status = ActionPlanStatus.FAILED.value

            await AuditService.log_event(
                db=db,
                merchant_id=merchant_id,
                actor_type="user" if user_id else "system",
                actor_id=str(user_id or "ActionExecutionService"),
                action_id=action_plan.id,
                event_type="action.failed",
                previous_status=ActionPlanStatus.EXECUTING.value,
                new_status=ActionPlanStatus.FAILED.value,
                reason=f"Execution tool '{tool_name}' failed: {tool_result.error}",
                execution_result={"error": tool_result.error},
                trace_id=tool_ctx.trace_id,
            )
            await db.flush()
            raise ValidationError(f"Action execution failed: {tool_result.error}")
