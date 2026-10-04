"""
Flowmint AI — Agent Orchestrator (Phase 2A).

Handles:
- Deterministic intent classification (Buyer vs Analytics vs Clarification)
- Session and message lifecycle persistence
- Run/trace creation and audit logging
- Tool call record persistence
- Enforcing tenant boundaries across all agent runs
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.agents.analytics_agent import AnalyticsAgent
from app.ai.agents.base import AgentResult, BaseAgent
from app.ai.agents.buyer_agent import BuyerAgent
from app.ai.agents.growth_agent import GrowthAgent
from app.ai.agents.recovery_agent import RecoveryAgent
from app.ai.providers.base import LLMMessage, LLMProvider
from app.ai.providers.factory import get_llm_provider
from app.ai.tools.base import ToolContext
from app.core.exceptions import NotFoundError, ValidationError
from app.models.agent import AgentMessage, AgentRun, AgentSession, ToolCallRecord


class AgentOrchestrator:
    """Central router and persistence orchestrator for Flowmint AI agents."""

    def __init__(self, provider: LLMProvider | None = None):
        self._custom_provider = provider

    @property
    def provider(self) -> LLMProvider:
        return self._custom_provider or get_llm_provider()

    @property
    def buyer_agent(self) -> BuyerAgent:
        return BuyerAgent(self.provider)

    @property
    def analytics_agent(self) -> AnalyticsAgent:
        return AnalyticsAgent(self.provider)

    @property
    def growth_agent(self) -> GrowthAgent:
        return GrowthAgent(self.provider)

    @property
    def recovery_agent(self) -> RecoveryAgent:
        return RecoveryAgent(self.provider)

    def route_intent(self, message: str) -> str:
        """
        Deterministic intent router:
        - growth_agent: cross-sell, bundles, upsell, product affinities
        - recovery_agent: abandoned cart recovery, failed payment retries
        - analytics_agent: revenue, sales, orders, conversions, payment performance
        - buyer_agent: product discovery, specifications, stock, comparison
        - clarification: ambiguous or greeting
        """
        m = message.lower().strip()

        # Growth patterns
        growth_keywords = [
            "cross sell", "cross-sell", "bundle", "bundles", "upsell",
            "frequently bought together", "bought together", "companion",
            "recommended bundle", "package deal", "affinity",
        ]
        if any(k in m for k in growth_keywords):
            return "growth_agent"

        # Recovery patterns (actions, strategies, and workflows)
        recovery_keywords = [
            "recover", "recovery", "retry payment", "recovery offer",
            "abandonment recovery", "recovery plan", "recovery nudge",
            "recovery strategy",
        ]
        if any(k in m for k in recovery_keywords):
            return "recovery_agent"

        # Analytics patterns
        analytics_keywords = [
            "revenue", "sales", "earnings", "income", "profit",
            "aov", "conversion", "funnel", "bounce", "abandoned",
            "performance", "top selling", "best seller", "worst seller", "selling",
            "order", "orders", "how many orders", "order summary", "completed orders",
            "payment", "payments", "why did revenue", "fall today", "drop",
            "compare period", "unit volume",
        ]
        if any(k in m for k in analytics_keywords):
            return "analytics_agent"

        # Buyer patterns
        buyer_keywords = [
            "find", "search", "looking for", "laptop", "phone", "watch",
            "shoes", "price", "under", "below", "compare", "stock",
            "available", "inventory", "units left", "similar", "alternatives",
            "recommend", "buy", "product", "features", "specs", "difference",
            "vs", "which is better", "cheapest", "gift", "accessories",
            "headphones", "earbuds", "monitor", "chair", "charger",
            "keyboard", "tablet",
        ]
        if any(k in m for k in buyer_keywords):
            return "buyer_agent"

        return "clarification"

    async def get_or_create_session(
        self,
        db: AsyncSession,
        merchant_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        session_id: uuid.UUID | None = None,
        agent_name: str = "orchestrator",
        title: str | None = None,
    ) -> AgentSession:
        """Retrieves an existing session or creates a new one scoped to merchant_id."""
        if session_id:
            res = await db.execute(
                select(AgentSession)
                .options(selectinload(AgentSession.messages))
                .where(
                    AgentSession.id == session_id,
                    AgentSession.merchant_id == merchant_id,
                )
            )
            session = res.scalar_one_or_none()
            if not session:
                raise NotFoundError("AgentSession", str(session_id))
            return session

        # Create new session
        session = AgentSession(
            merchant_id=merchant_id,
            user_id=user_id,
            agent_name=agent_name,
            title=title or f"Chat {time.strftime('%Y-%m-%d %H:%M')}",
            status="active",
        )
        db.add(session)
        await db.flush()
        return session

    async def run(
        self,
        db: AsyncSession,
        merchant_id: uuid.UUID,
        user_message: str,
        user_id: uuid.UUID | None = None,
        session_id: uuid.UUID | None = None,
        forced_agent: str | None = None,
    ) -> tuple[AgentResult, AgentSession]:
        """
        Full orchestrated agent execution cycle:
        1. Routing
        2. Session persistence
        3. Context injection
        4. Agent execution
        5. Run trace and tool call audit logging
        """
        start_time = time.perf_counter()
        trace_id = f"trc_{uuid.uuid4().hex[:12]}"

        # 1. Routing
        selected_agent_name = forced_agent or self.route_intent(user_message)

        # 2. Get or create session
        session = await self.get_or_create_session(
            db=db,
            merchant_id=merchant_id,
            user_id=user_id,
            session_id=session_id,
            agent_name=selected_agent_name,
        )

        # Save user message
        user_msg_record = AgentMessage(
            session_id=session.id,
            role="user",
            content=user_message,
        )
        db.add(user_msg_record)
        await db.flush()

        # Prepare tool execution context
        context = ToolContext(
            merchant_id=merchant_id,
            user_id=user_id,
            trace_id=trace_id,
            db=db,
            is_read_only=True,
        )

        # 3. Handle Clarification if needed
        if selected_agent_name == "clarification":
            clarification_text = (
                "Hello! I am Flowmint AI. I can assist you with:\n"
                "- **Product Discovery & Inventory**: e.g., 'Find me wireless headphones under ₹3,000'\n"
                "- **Store Revenue & Analytics**: e.g., 'How much revenue was generated this week?'\n\n"
                "How would you like to proceed?"
            )
            result = AgentResult(
                response=clarification_text,
                action_plan=None,
                trace_id=trace_id,
                agent_name="orchestrator",
                latency_ms=int((time.perf_counter() - start_time) * 1000),
            )
        else:
            # 4. Dispatch to specialized agent
            agent: BaseAgent
            if selected_agent_name == "buyer_agent":
                agent = self.buyer_agent
            elif selected_agent_name == "analytics_agent":
                agent = self.analytics_agent
            elif selected_agent_name == "growth_agent":
                agent = self.growth_agent
            elif selected_agent_name == "recovery_agent":
                agent = self.recovery_agent
            else:
                agent = self.buyer_agent

            # Extract message history for conversation memory safely
            history = []
            if session_id:
                past_res = await db.execute(
                    select(AgentMessage)
                    .where(AgentMessage.session_id == session.id)
                    .order_by(AgentMessage.created_at.desc())
                    .limit(6)
                )
                past_records = list(reversed(past_res.scalars().all()))
                for past in past_records[:-1]:  # exclude the just-added user message
                    history.append(LLMMessage(role=past.role, content=past.content))

            result = await agent.execute(
                user_message=user_message,
                context=context,
                history=history,
            )

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        result.latency_ms = latency_ms

        # 5. Persist Run and Trace Audit Record
        agent_run = AgentRun(
            session_id=session.id,
            trace_id=trace_id,
            merchant_id=merchant_id,
            user_id=user_id,
            agent_name=result.agent_name,
            model=getattr(self.provider, "model", "mock-model"),
            status="success",
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            latency_ms=latency_ms,
        )
        db.add(agent_run)
        await db.flush()

        # 6. Persist Tool Calls
        for tc in result.tool_calls:
            tc_rec = ToolCallRecord(
                run_id=agent_run.id,
                trace_id=trace_id,
                tool_name=tc["name"],
                parameters=tc["arguments"],
                result=tc["result"],
                status="success" if tc.get("success", True) else "failed",
                latency_ms=tc.get("latency_ms", 0),
                error_message=tc.get("error"),
            )
            db.add(tc_rec)

        # 7. Persist Assistant Response Message
        assistant_msg_record = AgentMessage(
            session_id=session.id,
            role="assistant",
            content=result.response,
            metadata_json={
                "trace_id": trace_id,
                "structured_data": result.structured_data,
                "action_plan": result.action_plan,
            },
        )
        db.add(assistant_msg_record)

        await db.commit()
        await db.refresh(session)

        return result, session
