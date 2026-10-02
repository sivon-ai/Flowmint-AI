"""
Unit and integration tests for Agent Orchestrator.
"""

from decimal import Decimal
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agents.orchestrator import AgentOrchestrator
from app.ai.providers.mock import MockLLMProvider
from app.models.agent import AgentMessage, AgentRun, AgentSession, ToolCallRecord
from app.models.merchant import Merchant
from app.models.product import Product
from tests.ai.fixtures import ANALYTICS_QUERIES, BUYER_QUERIES


class TestAgentOrchestrator:
    def test_intent_routing_accuracy_on_fixtures(self):
        orchestrator = AgentOrchestrator()

        # Test all 20 Buyer Queries
        for q in BUYER_QUERIES:
            intent = orchestrator.route_intent(q)
            assert intent == "buyer_agent", f"Buyer query '{q}' misclassified as '{intent}'"

        # Test all 10 Analytics Queries
        for q in ANALYTICS_QUERIES:
            intent = orchestrator.route_intent(q)
            assert intent == "analytics_agent", f"Analytics query '{q}' misclassified as '{intent}'"

    def test_intent_routing_clarification(self):
        orchestrator = AgentOrchestrator()
        assert orchestrator.route_intent("Hello!") == "clarification"
        assert orchestrator.route_intent("What is the weather today?") == "clarification"

    @pytest.mark.asyncio
    async def test_orchestrator_full_lifecycle_and_persistence(
        self, db_session: AsyncSession, merchant: Merchant
    ):
        # Seed product
        p = Product(
            merchant_id=merchant.id,
            name="Gaming Mouse Pro",
            slug="gaming-mouse-pro",
            sku="MOUSE-01",
            price=Decimal("1999.00"),
            status="active",
        )
        db_session.add(p)
        await db_session.commit()

        provider = MockLLMProvider()
        orchestrator = AgentOrchestrator(provider=provider)

        # 1. First turn: user asks for product
        result, session = await orchestrator.run(
            db=db_session,
            merchant_id=merchant.id,
            user_message="Find me a gaming mouse",
        )

        assert session.id is not None
        assert session.merchant_id == merchant.id
        assert result.agent_name == "buyer_agent"
        assert result.action_plan is None

        # Verify AgentMessages in DB
        msgs_res = await db_session.execute(
            select(AgentMessage).where(AgentMessage.session_id == session.id).order_by(AgentMessage.created_at.asc())
        )
        messages = msgs_res.scalars().all()
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[0].content == "Find me a gaming mouse"
        assert messages[1].role == "assistant"
        assert "Gaming Mouse Pro" in messages[1].content

        # Verify AgentRun in DB
        run_res = await db_session.execute(
            select(AgentRun).where(AgentRun.session_id == session.id)
        )
        run = run_res.scalar_one()
        assert run.trace_id == result.trace_id
        assert run.agent_name == "buyer_agent"
        assert run.status == "success"
        assert run.latency_ms >= 0

        # Verify ToolCallRecord in DB
        tc_res = await db_session.execute(
            select(ToolCallRecord).where(ToolCallRecord.run_id == run.id)
        )
        tcs = tc_res.scalars().all()
        assert len(tcs) >= 1
        assert tcs[0].tool_name == "search_products"
        assert tcs[0].status == "success"
        assert tcs[0].trace_id == result.trace_id

        # 2. Second turn: Continue in same session
        result2, session2 = await orchestrator.run(
            db=db_session,
            merchant_id=merchant.id,
            user_message="What was our total revenue this month?",
            session_id=session.id,
        )

        assert session2.id == session.id
        assert result2.agent_name == "analytics_agent"

        # Check total messages in session now = 4
        all_msgs_res = await db_session.execute(
            select(AgentMessage).where(AgentMessage.session_id == session.id)
        )
        assert len(all_msgs_res.scalars().all()) == 4
