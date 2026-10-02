"""
Flowmint AI — Structured Tool Framework.

Defines the strongly typed BaseTool, ToolContext, and ToolResult.
Enforces:
- Schema validation via Pydantic
- Backend context injection (merchant_id, user_id, db session)
- Explicit risk levels and read-only guarantees
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession


class RiskLevel(str, Enum):
    """Risk tier for agent tool execution."""
    LOW = "low"            # Read-only queries, catalog search, analytics calculations
    MEDIUM = "medium"      # Safe drafts, cart creation, simulated calculations
    HIGH = "high"          # Pricing updates, inventory allocation, campaign creation
    CRITICAL = "critical"  # Payments, refunds, data deletion, credential management


class ToolContext(BaseModel):
    """
    Security and execution context injected by the backend.
    The LLM never supplies these attributes.
    """
    model_config = {"arbitrary_types_allowed": True}

    merchant_id: uuid.UUID
    user_id: uuid.UUID | None = None
    trace_id: str
    db: AsyncSession | None = None
    is_read_only: bool = True



class ToolResult(BaseModel):
    """Standardized result returned by all tools."""
    success: bool
    data: Any = None
    error: str | None = None
    message: str = ""

    @classmethod
    def ok(cls, data: Any = None, message: str = "") -> ToolResult:
        return cls(success=True, data=data, message=message)

    @classmethod
    def fail(cls, error: str, message: str = "") -> ToolResult:
        return cls(success=False, error=error, message=message)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class BaseTool(ABC):
    """
    Abstract base class for all Flowmint AI tools.
    Every tool must define its parameter schema via Pydantic.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for the tool."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Detailed instruction for the LLM on when and how to call this tool."""
        pass

    @property
    @abstractmethod
    def parameters_schema(self) -> type[BaseModel]:
        """Pydantic model defining the expected input parameters."""
        pass

    @property
    def risk_level(self) -> RiskLevel:
        """Risk level of the tool. Phase 2A tools are strictly LOW."""
        return RiskLevel.LOW

    @property
    def is_read_only(self) -> bool:
        """True if the tool performs zero database mutations."""
        return True

    @property
    def requires_merchant_id(self) -> bool:
        """Whether this tool requires an active merchant tenant context."""
        return True

    def to_openai_tool(self) -> dict[str, Any]:
        """Generates OpenAI-compatible function definition schema."""
        schema = self.parameters_schema.model_json_schema()
        # Clean schema title and description to fit standard OpenAI format
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    @abstractmethod
    async def execute(self, params: Any, context: ToolContext) -> ToolResult:
        """Execute the tool with validated parameters and injected context."""
        pass
