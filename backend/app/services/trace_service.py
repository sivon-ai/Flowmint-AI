"""
Flowmint AI — End-to-End Trace Service (Phase 4).

Reconstructs the full causal journey of an AI commerce action:
Opportunity -> Agent Run -> Tool Calls -> ActionPlan -> Policy Check -> Risk Classification -> Approval -> Execution -> Outcome -> Audit Log.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentRun, ToolCallRecord
from app.models.attribution import ActionOutcome
from app.models.governance import ActionExecution, Approval, AuditLog
from app.models.opportunity import ActionPlan, Opportunity


class TraceService:
    @staticmethod
    async def get_trace(
        db: AsyncSession,
        merchant_id: uuid.UUID,
        trace_id: str,
    ) -> dict[str, Any] | None:
        """
        Reconstructs the complete trace timeline by trace_id or linked entity identifiers.
        """
        # 1. Fetch AgentRun
        run_stmt = select(AgentRun).where(
            AgentRun.merchant_id == merchant_id,
            AgentRun.trace_id == trace_id,
        )
        run_res = await db.execute(run_stmt)
        agent_run = run_res.scalar_one_or_none()

        # 2. Fetch ToolCallRecords
        tools_stmt = (
            select(ToolCallRecord)
            .join(AgentRun, ToolCallRecord.run_id == AgentRun.id)
            .where(
                AgentRun.merchant_id == merchant_id,
                ToolCallRecord.trace_id == trace_id,
            )
            .order_by(ToolCallRecord.created_at)
        )
        tools_res = await db.execute(tools_stmt)
        tool_records = tools_res.scalars().all()

        # 3. Fetch AuditLogs for this trace
        audit_stmt = (
            select(AuditLog)
            .where(
                AuditLog.merchant_id == merchant_id,
                AuditLog.trace_id == trace_id,
            )
            .order_by(AuditLog.created_at)
        )
        audit_res = await db.execute(audit_stmt)
        audit_logs = audit_res.scalars().all()

        # 4. Resolve ActionPlan, Opportunity, Approval, Execution, Outcome
        # Either from audit logs or directly
        action_id: uuid.UUID | None = None
        for a in audit_logs:
            if a.action_id:
                action_id = a.action_id
                break

        action_plan: ActionPlan | None = None
        opportunity: Opportunity | None = None
        approval: Approval | None = None
        execution: ActionExecution | None = None
        outcome: ActionOutcome | None = None

        if action_id:
            plan_res = await db.execute(
                select(ActionPlan).where(
                    ActionPlan.id == action_id,
                    ActionPlan.merchant_id == merchant_id,
                )
            )
            action_plan = plan_res.scalar_one_or_none()

            if action_plan and action_plan.opportunity_id:
                opp_res = await db.execute(
                    select(Opportunity).where(
                        Opportunity.id == action_plan.opportunity_id,
                        Opportunity.merchant_id == merchant_id,
                    )
                )
                opportunity = opp_res.scalar_one_or_none()

            app_res = await db.execute(
                select(Approval).where(
                    Approval.action_plan_id == action_id,
                    Approval.merchant_id == merchant_id,
                )
            )
            approval = app_res.scalars().first()

            exec_res = await db.execute(
                select(ActionExecution).where(
                    ActionExecution.action_plan_id == action_id,
                    ActionExecution.merchant_id == merchant_id,
                )
            )
            execution = exec_res.scalars().first()

            out_res = await db.execute(
                select(ActionOutcome).where(
                    ActionOutcome.action_id == action_id,
                    ActionOutcome.merchant_id == merchant_id,
                )
            )
            outcome = out_res.scalars().first()

        # If not found via audit, search outcome directly by trace_id
        if not outcome:
            out_res2 = await db.execute(
                select(ActionOutcome).where(
                    ActionOutcome.merchant_id == merchant_id,
                    ActionOutcome.trace_id == trace_id,
                )
            )
            outcome = out_res2.scalar_one_or_none()

        # Build chronological timeline nodes
        nodes: list[dict[str, Any]] = []

        # Step 1: Opportunity Detection
        if opportunity:
            nodes.append({
                "step": 1,
                "type": "opportunity_detected",
                "label": "Opportunity Detected",
                "status": "completed",
                "timestamp": opportunity.created_at.isoformat(),
                "details": {
                    "opportunity_id": str(opportunity.id),
                    "type": opportunity.type,
                    "title": opportunity.title,
                    "priority": opportunity.priority,
                    "potential_revenue": float(opportunity.estimated_value),
                },
            })

        # Step 2: Agent Run & Investigation
        if agent_run:
            nodes.append({
                "step": 2,
                "type": "agent_run",
                "label": f"Agent Run ({agent_run.agent_name})",
                "status": agent_run.status,
                "timestamp": agent_run.created_at.isoformat(),
                "latency_ms": agent_run.latency_ms,
                "tokens": agent_run.prompt_tokens + agent_run.completion_tokens,
                "details": {
                    "agent": agent_run.agent_name,
                    "prompt_tokens": agent_run.prompt_tokens,
                    "completion_tokens": agent_run.completion_tokens,
                },
            })

        # Step 3: Tool Calls
        for idx, tool in enumerate(tool_records, start=1):
            nodes.append({
                "step": 3,
                "sub_step": idx,
                "type": "tool_call",
                "label": f"Tool: {tool.tool_name}",
                "status": tool.status,
                "timestamp": tool.created_at.isoformat(),
                "latency_ms": tool.latency_ms,
                "details": {
                    "tool": tool.tool_name,
                    "parameters": tool.parameters,
                    "error": tool.error_message,
                },
            })

        # Step 4: ActionPlan Formulation
        if action_plan:
            nodes.append({
                "step": 4,
                "type": "action_plan",
                "label": f"ActionPlan: {action_plan.action_type}",
                "status": action_plan.status,
                "timestamp": action_plan.created_at.isoformat(),
                "details": {
                    "action_id": str(action_plan.id),
                    "action_type": action_plan.action_type,
                    "risk_level": action_plan.risk_level,
                    "requires_approval": action_plan.requires_approval,
                    "estimated_impact": action_plan.estimated_impact,
                },
            })

        # Step 5: Policy Checks & Audit Events
        for audit in audit_logs:
            nodes.append({
                "step": 5,
                "type": "audit_log",
                "label": f"Audit: {audit.event_type}",
                "status": "logged",
                "timestamp": audit.created_at.isoformat(),
                "details": {
                    "event_type": audit.event_type,
                    "actor_type": audit.actor_type,
                    "previous_status": audit.previous_status,
                    "new_status": audit.new_status,
                    "reason": audit.reason,
                    "policy_results": audit.policy_results,
                },
            })

        # Step 6: Approval
        if approval:
            nodes.append({
                "step": 6,
                "type": "approval",
                "label": f"Approval ({approval.status.upper()})",
                "status": approval.status,
                "timestamp": (approval.decided_at or approval.created_at).isoformat(),
                "details": {
                    "approval_id": str(approval.id),
                    "decided_by": str(approval.decided_by) if approval.decided_by else None,
                    "decision_reason": approval.decision_reason,
                    "expires_at": approval.expires_at.isoformat(),
                },
            })

        # Step 7: Execution
        if execution:
            nodes.append({
                "step": 7,
                "type": "execution",
                "label": f"Execution ({execution.status.upper()})",
                "status": execution.status,
                "timestamp": execution.started_at.isoformat(),
                "details": {
                    "execution_id": str(execution.id),
                    "tool_name": execution.tool_name,
                    "idempotency_key": execution.idempotency_key,
                    "result": execution.tool_result,
                },
            })

        # Step 8: Outcome & Attribution
        if outcome:
            nodes.append({
                "step": 8,
                "type": "outcome",
                "label": f"Outcome ({outcome.label})",
                "status": "attributed",
                "timestamp": outcome.created_at.isoformat(),
                "details": {
                    "outcome_id": str(outcome.id),
                    "label": outcome.label,
                    "orders_attributed": outcome.orders_attributed,
                    "gross_revenue": float(outcome.gross_revenue),
                    "discount_cost": float(outcome.discount_cost),
                    "net_revenue_impact": float(outcome.net_revenue_impact),
                    "confidence": float(outcome.confidence),
                },
            })

        return {
            "trace_id": trace_id,
            "merchant_id": str(merchant_id),
            "total_nodes": len(nodes),
            "timeline": nodes,
        }
