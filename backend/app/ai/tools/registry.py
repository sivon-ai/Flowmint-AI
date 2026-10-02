"""
Flowmint AI — Tool Registry.

Manages tool discovery, schema extraction, parameter validation,
permission enforcement, and safe execution with latency tracking.
"""

from __future__ import annotations

import time
from typing import Any

from pydantic import ValidationError

from app.ai.tools.base import BaseTool, ToolContext, ToolResult


class ToolRegistry:
    """Central registry of executable AI tools."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    @property
    def tools(self) -> dict[str, BaseTool]:
        """Dictionary of registered tools."""
        return self._tools

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        """Retrieve tool by name."""
        return self._tools.get(name)

    def list_tools(self, allowed_names: list[str] | None = None) -> list[BaseTool]:
        """List all or filtered tools."""
        if allowed_names is None:
            return list(self._tools.values())
        return [t for name, t in self._tools.items() if name in allowed_names]

    def get_schemas(self, allowed_names: list[str] | None = None) -> list[dict[str, Any]]:
        """Return OpenAI-compatible tool specifications for allowed tools."""
        tools = self.list_tools(allowed_names)
        return [t.to_openai_tool() for t in tools]

    async def execute(
        self,
        name: str,
        raw_params: dict[str, Any],
        context: ToolContext,
        allowed_names: list[str] | None = None,
    ) -> tuple[ToolResult, int]:
        """
        Execute a tool safely:
        1. Verify tool exists
        2. Verify tool is permitted in the agent's allowed list
        3. Validate parameters using Pydantic schema
        4. Track latency
        5. Return (ToolResult, latency_ms)
        """
        start_time = time.perf_counter()

        # 1. Tool existence check
        tool = self.get(name)
        if not tool:
            latency = int((time.perf_counter() - start_time) * 1000)
            return ToolResult.fail(f"Tool '{name}' is not registered"), latency

        # 2. Permission check
        if allowed_names is not None and name not in allowed_names:
            latency = int((time.perf_counter() - start_time) * 1000)
            return ToolResult.fail(f"Tool '{name}' is not permitted for this agent"), latency

        # 3. Read-only enforcement for Phase 2A
        if not tool.is_read_only:
            latency = int((time.perf_counter() - start_time) * 1000)
            return ToolResult.fail(f"Tool '{name}' is a mutating tool, which is disallowed in Phase 2A"), latency

        # 4. Parameter validation
        try:
            validated_params = tool.parameters_schema.model_validate(raw_params)
        except ValidationError as err:
            latency = int((time.perf_counter() - start_time) * 1000)
            return ToolResult.fail(f"Parameter validation failed for '{name}': {err}"), latency

        # 5. Execution
        try:
            result = await tool.execute(validated_params, context)
        except Exception as exc:
            latency = int((time.perf_counter() - start_time) * 1000)
            return ToolResult.fail(f"Error executing '{name}': {str(exc)}"), latency

        latency = int((time.perf_counter() - start_time) * 1000)
        return result, latency


# Global tool registry singleton
tool_registry = ToolRegistry()
