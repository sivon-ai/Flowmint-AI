"""
Integration tests for AI Agent API endpoints (/api/v1/agents/*).
"""

from decimal import Decimal
import pytest
from httpx import AsyncClient

from app.models.merchant import Merchant
from app.models.product import Product
from app.models.inventory import Inventory


class TestAgentAPI:
    @pytest.mark.asyncio
    async def test_agent_chat_endpoint(
        self, client: AsyncClient, auth_headers: dict, merchant: Merchant, db_session
    ):
        # Seed product
        p = Product(
            merchant_id=merchant.id,
            name="Air Buds Pro",
            slug="air-buds-pro",
            sku="BUDS-01",
            price=Decimal("2999.00"),
            description="True wireless earbuds with active noise cancellation",
            status="active",
        )
        db_session.add(p)
        await db_session.flush()
        inv = Inventory(product_id=p.id, merchant_id=merchant.id, quantity=15, reserved=0)
        db_session.add(inv)
        await db_session.commit()

        # 1. Chat via POST /api/v1/agents/chat
        resp = await client.post(
            "/api/v1/agents/chat",
            headers=auth_headers,
            json={"message": "Find me wireless earbuds"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["agent_name"] == "buyer_agent"
        assert data["session_id"] is not None
        assert data["trace_id"].startswith("trc_")
        assert "Air Buds Pro" in data["response"]
        session_id = data["session_id"]

        # 2. Get session details via GET /api/v1/agents/sessions/{id}
        sess_resp = await client.get(
            f"/api/v1/agents/sessions/{session_id}",
            headers=auth_headers,
        )
        assert sess_resp.status_code == 200
        sess_data = sess_resp.json()["data"]
        assert sess_data["session"]["id"] == session_id
        assert len(sess_data["messages"]) == 2  # user + assistant

    @pytest.mark.asyncio
    async def test_buyer_and_analytics_direct_endpoints(
        self, client: AsyncClient, auth_headers: dict
    ):
        # Direct Buyer
        b_res = await client.post(
            "/api/v1/agents/buyer",
            headers=auth_headers,
            json={"message": "Search for shoes"},
        )
        assert b_res.status_code == 200
        assert b_res.json()["data"]["agent_name"] == "buyer_agent"

        # Direct Analytics
        a_res = await client.post(
            "/api/v1/agents/analytics",
            headers=auth_headers,
            json={"message": "Show me revenue statistics"},
        )
        assert a_res.status_code == 200
        assert a_res.json()["data"]["agent_name"] == "analytics_agent"

    @pytest.mark.asyncio
    async def test_list_sessions_and_get_run_trace(
        self, client: AsyncClient, auth_headers: dict, merchant: Merchant, db_session
    ):
        # Create a run via chat
        chat_res = await client.post(
            "/api/v1/agents/chat",
            headers=auth_headers,
            json={"message": "How many orders were placed?"},
        )
        assert chat_res.status_code == 200

        # List sessions
        list_res = await client.get("/api/v1/agents/sessions", headers=auth_headers)
        assert list_res.status_code == 200
        sessions = list_res.json()["data"]
        assert len(sessions) >= 1

        # Query run trace from database to test GET /api/v1/agents/runs/{id}
        from app.models.agent import AgentRun
        from sqlalchemy import select
        run_res = await db_session.execute(
            select(AgentRun).where(AgentRun.merchant_id == merchant.id).order_by(AgentRun.created_at.desc()).limit(1)
        )
        run = run_res.scalar_one()

        get_run_res = await client.get(
            f"/api/v1/agents/runs/{run.id}",
            headers=auth_headers,
        )
        assert get_run_res.status_code == 200
        run_data = get_run_res.json()["data"]
        assert run_data["id"] == str(run.id)
        assert run_data["trace_id"] == run.trace_id
        assert run_data["status"] == "success"

    @pytest.mark.asyncio
    async def test_cross_tenant_session_protection(
        self, client: AsyncClient, auth_headers: dict, auth_headers_b: dict
    ):
        """Merchant A cannot access Merchant B's agent session."""
        # Merchant B creates session
        res_b = await client.post(
            "/api/v1/agents/chat",
            headers=auth_headers_b,
            json={"message": "Confidential store query"},
        )
        sess_b_id = res_b.json()["data"]["session_id"]

        # Merchant A attempts to access Merchant B's session -> 404
        res_a = await client.get(
            f"/api/v1/agents/sessions/{sess_b_id}",
            headers=auth_headers,
        )
        assert res_a.status_code == 404
