"""
Flowmint AI — Agent Base Interface (Phase 2A).

Defines BaseAgent, AgentResult, and the execution loop.
Enforces that action_plan remains None for read-only agents in Phase 2A.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from app.ai.providers.base import LLMMessage, LLMProvider
from app.ai.providers.factory import get_llm_provider
from app.ai.security.sanitizer import detect_injection_risk, sanitize_user_input, wrap_untrusted_data
from app.ai.tools.base import RiskLevel, ToolContext, ToolResult
from app.ai.tools.registry import tool_registry


class AgentResult(BaseModel):
    """Structured result returned by an agent invocation."""
    response: str
    structured_data: Any | None = None
    action_plan: dict[str, Any] | None = None  # Populated only as PROPOSED action plan by Growth/Recovery agents
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    trace_id: str
    agent_name: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0


class BaseAgent(ABC):
    """Abstract base class for all Flowmint AI agents."""

    def __init__(self, provider: LLMProvider | None = None):
        self.provider = provider or get_llm_provider()

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique agent name (e.g. buyer_agent, analytics_agent)."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of the agent's capabilities."""
        pass

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Core system instruction for the agent."""
        pass

    @property
    @abstractmethod
    def allowed_tools(self) -> list[str]:
        """List of tool names this agent is authorized to invoke."""
        pass

    @property
    def max_risk_level(self) -> RiskLevel:
        """Maximum permitted tool risk level. Phase 2A is strictly LOW."""
        return RiskLevel.LOW

    async def execute(
        self,
        user_message: str,
        context: ToolContext,
        history: list[LLMMessage] | None = None,
    ) -> AgentResult:
        """
        Executes the agent loop:
        1. Sanitize input & detect adversarial attempts
        2. Format messages & system prompt
        3. Request tool execution from LLM
        4. Execute validated tools through ToolRegistry
        5. Return grounded AgentResult with action_plan=None
        """
        clean_input = sanitize_user_input(user_message)
        if detect_injection_risk(clean_input):
            return AgentResult(
                response="I detected an instruction pattern that conflicts with my safety guardrails. I cannot process this request.",
                action_plan=None,
                trace_id=context.trace_id,
                agent_name=self.name,
            )

        # Build initial message chain
        messages: list[LLMMessage] = [
            LLMMessage(role="system", content=self.system_prompt),
        ]
        if history:
            messages.extend(history)
        messages.append(LLMMessage(role="user", content=clean_input))

        # Get permitted tool schemas
        tool_schemas = tool_registry.get_schemas(self.allowed_tools)

        # 1st LLM call
        first_resp = await self.provider.generate(
            messages=messages,
            tools=tool_schemas if tool_schemas else None,
            temperature=0.1,
            max_tokens=1024,
        )

        executed_tool_calls: list[dict[str, Any]] = []
        structured_data: dict[str, Any] | None = None
        total_prompt_tokens = first_resp.usage.prompt_tokens
        total_completion_tokens = first_resp.usage.completion_tokens

        # Check if model requested tool execution
        if first_resp.tool_calls:
            # Append assistant message with tool calls
            messages.append(
                LLMMessage(
                    role="assistant",
                    content=first_resp.content or "",
                    tool_calls=first_resp.tool_calls,
                )
            )

            for tc in first_resp.tool_calls:
                tool_name = tc.function.name
                tool_args = tc.function.arguments

                # Execute via registry with permission enforcement
                result, latency = await tool_registry.execute(
                    name=tool_name,
                    raw_params=tool_args,
                    context=context,
                    allowed_names=self.allowed_tools,
                )

                executed_tool_calls.append({
                    "id": tc.id,
                    "name": tool_name,
                    "arguments": tool_args,
                    "result": result.data,
                    "success": result.success,
                    "error": result.error,
                    "latency_ms": latency,
                })

                if result.success and result.data is not None:
                    structured_data = result.data

                # Wrap tool output in untrusted data container
                tool_output_str = json.dumps(result.to_dict())
                safe_output = wrap_untrusted_data(tool_output_str, source=tool_name)

                messages.append(
                    LLMMessage(
                        role="tool",
                        content=safe_output,
                        tool_call_id=tc.id,
                        name=tool_name,
                    )
                )

            # 2nd LLM call for grounded synthesis
            second_resp = await self.provider.generate(
                messages=messages,
                tools=None,
                temperature=0.1,
                max_tokens=1024,
            )
            final_text = second_resp.content or "No response generated."
            total_prompt_tokens += second_resp.usage.prompt_tokens
            total_completion_tokens += second_resp.usage.completion_tokens
        else:
            final_text = first_resp.content or "I have processed your request."

        return AgentResult(
            response=final_text,
            structured_data=structured_data,
            action_plan=None,  # STRICTLY None for Phase 2A
            tool_calls=executed_tool_calls,
            trace_id=context.trace_id,
            agent_name=self.name,
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
        )
