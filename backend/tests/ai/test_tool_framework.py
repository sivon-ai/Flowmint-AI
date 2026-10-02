"""
Unit tests for the structured tool framework and ToolRegistry.
"""

import uuid
import pytest
from pydantic import BaseModel, Field

from app.ai.tools.base import BaseTool, RiskLevel, ToolContext, ToolResult
from app.ai.tools.registry import ToolRegistry, tool_registry


class DummyParams(BaseModel):
    keyword: str = Field(min_length=2)
    max_items: int = Field(default=5, ge=1, le=10)


class DummyTool(BaseTool):
    @property
    def name(self) -> str:
        return "dummy_tool"

    @property
    def description(self) -> str:
        return "A dummy test tool."

    @property
    def parameters_schema(self) -> type[BaseModel]:
        return DummyParams

    async def execute(self, params: DummyParams, context: ToolContext) -> ToolResult:
        return ToolResult.ok(data={"echo": params.keyword, "count": params.max_items})


class MutatingDummyTool(BaseTool):
    @property
    def name(self) -> str:
        return "mutating_tool"

    @property
    def description(self) -> str:
        return "Disallowed mutating tool."

    @property
    def parameters_schema(self) -> type[BaseModel]:
        return DummyParams

    @property
    def is_read_only(self) -> bool:
        return False

    async def execute(self, params: DummyParams, context: ToolContext) -> ToolResult:
        return ToolResult.ok()


class TestToolFramework:
    def test_registry_contains_phase2a_tools(self):
        expected_tools = {
            # Buyer tools
            "search_products",
            "get_product",
            "compare_products",
            "check_inventory",
            "get_related_products",
            # Analytics tools
            "get_revenue_summary",
            "get_conversion_summary",
            "get_product_performance",
            "get_payment_summary",
            "compare_periods",
            "get_order_summary",
        }
        for name in expected_tools:
            tool = tool_registry.get(name)
            assert tool is not None, f"Tool '{name}' not found in registry"
            assert tool.is_read_only is True
            assert tool.risk_level == RiskLevel.LOW

    def test_schema_generation(self):
        schemas = tool_registry.get_schemas(["search_products", "get_revenue_summary"])
        assert len(schemas) == 2
        for s in schemas:
            assert s["type"] == "function"
            fn = s["function"]
            assert "name" in fn
            assert "description" in fn
            assert "parameters" in fn

    @pytest.mark.asyncio
    async def test_tool_execution_success_and_latency(self):
        reg = ToolRegistry()
        reg.register(DummyTool())

        ctx = ToolContext(
            merchant_id=uuid.uuid4(),
            trace_id="trc_test_123",
            db=None,  # Not accessed in dummy
        )

        result, latency = await reg.execute("dummy_tool", {"keyword": "test-kw", "max_items": 8}, ctx)
        assert result.success is True
        assert result.data["echo"] == "test-kw"
        assert result.data["count"] == 8
        assert latency >= 0

    @pytest.mark.asyncio
    async def test_tool_invalid_parameters_rejected(self):
        reg = ToolRegistry()
        reg.register(DummyTool())

        ctx = ToolContext(merchant_id=uuid.uuid4(), trace_id="trc_test", db=None)

        # 1. keyword too short (< 2)
        res1, _ = await reg.execute("dummy_tool", {"keyword": "a"}, ctx)
        assert res1.success is False
        assert "validation failed" in res1.error.lower()

        # 2. max_items > 10
        res2, _ = await reg.execute("dummy_tool", {"keyword": "valid", "max_items": 99}, ctx)
        assert res2.success is False
        assert "validation failed" in res2.error.lower()

    @pytest.mark.asyncio
    async def test_permission_check_disallowed_tool(self):
        reg = ToolRegistry()
        reg.register(DummyTool())

        ctx = ToolContext(merchant_id=uuid.uuid4(), trace_id="trc_test", db=None)

        # Disallowed because it's not in allowed_names
        res, _ = await reg.execute(
            "dummy_tool",
            {"keyword": "valid"},
            ctx,
            allowed_names=["other_tool"],
        )
        assert res.success is False
        assert "not permitted" in res.error

    @pytest.mark.asyncio
    async def test_mutating_tool_rejected_in_phase2a(self):
        reg = ToolRegistry()
        reg.register(MutatingDummyTool())

        ctx = ToolContext(merchant_id=uuid.uuid4(), trace_id="trc_test", db=None)
        res, _ = await reg.execute("mutating_tool", {"keyword": "valid"}, ctx)
        assert res.success is False
        assert "mutating tool" in res.error.lower()
