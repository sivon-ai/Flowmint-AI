"""
Flowmint AI — Tools Module (Phase 2A).

Exports all safe read-only buyer and analytics tools, and registers them
in the global tool_registry.
"""

from app.ai.tools.analytics_tools import (
    ComparePeriodsTool,
    GetConversionSummaryTool,
    GetOrderSummaryTool,
    GetPaymentSummaryTool,
    GetProductPerformanceTool,
    GetRevenueSummaryTool,
)
from app.ai.tools.base import BaseTool, RiskLevel, ToolContext, ToolResult
from app.ai.tools.buyer_tools import (
    CheckInventoryTool,
    CompareProductsTool,
    GetProductTool,
    GetRelatedProductsTool,
    SearchProductsTool,
)
from app.ai.tools.growth_recovery_tools import (
    AbandonedCartsTool,
    CustomerPurchaseHistoryTool,
    FailedPaymentsTool,
    FrequentlyBoughtTogetherTool,
    InventoryHealthTool,
    RecoveryCandidatesTool,
)
from app.ai.tools.registry import ToolRegistry, tool_registry

# Register all Phase 2A Buyer Tools
tool_registry.register(SearchProductsTool())
tool_registry.register(GetProductTool())
tool_registry.register(CompareProductsTool())
tool_registry.register(CheckInventoryTool())
tool_registry.register(GetRelatedProductsTool())

# Register all Phase 2A Analytics Tools
tool_registry.register(GetRevenueSummaryTool())
tool_registry.register(GetConversionSummaryTool())
tool_registry.register(GetProductPerformanceTool())
tool_registry.register(GetPaymentSummaryTool())
tool_registry.register(ComparePeriodsTool())
tool_registry.register(GetOrderSummaryTool())

# Register Phase 2B Growth Tools
tool_registry.register(FrequentlyBoughtTogetherTool())
tool_registry.register(CustomerPurchaseHistoryTool())
tool_registry.register(InventoryHealthTool())

# Register Phase 2B Recovery Tools
tool_registry.register(AbandonedCartsTool())
tool_registry.register(FailedPaymentsTool())
tool_registry.register(RecoveryCandidatesTool())

__all__ = [
    "BaseTool",
    "RiskLevel",
    "ToolContext",
    "ToolResult",
    "ToolRegistry",
    "tool_registry",
    # Buyer tools
    "SearchProductsTool",
    "GetProductTool",
    "CompareProductsTool",
    "CheckInventoryTool",
    "GetRelatedProductsTool",
    # Analytics tools
    "GetRevenueSummaryTool",
    "GetConversionSummaryTool",
    "GetProductPerformanceTool",
    "GetPaymentSummaryTool",
    "ComparePeriodsTool",
    "GetOrderSummaryTool",
    # Growth & Recovery tools
    "FrequentlyBoughtTogetherTool",
    "CustomerPurchaseHistoryTool",
    "InventoryHealthTool",
    "AbandonedCartsTool",
    "FailedPaymentsTool",
    "RecoveryCandidatesTool",
]
