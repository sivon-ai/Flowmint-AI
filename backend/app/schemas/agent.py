"""
Flowmint AI — Agent Pydantic Schemas (Phase 2A).

Strongly typed request and response schemas for AI endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    """User prompt to the agent orchestrator."""
    message: str = Field(min_length=1, max_length=2000, description="User prompt or natural language query")
    session_id: uuid.UUID | None = Field(default=None, description="Optional existing session UUID to continue conversation")


class AgentChatResponse(BaseModel):
    """Structured response from the agent orchestrator."""
    session_id: uuid.UUID
    trace_id: str
    agent_name: str
    response: str
    structured_data: Any | None = None
    action_plan: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    latency_ms: int


class AgentMessageResponse(BaseModel):
    """Message item inside a session."""
    id: uuid.UUID
    role: str
    content: str
    tool_calls: list[Any] | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentSessionResponse(BaseModel):
    """Summary of an agent session."""
    id: uuid.UUID
    merchant_id: uuid.UUID
    user_id: uuid.UUID | None = None
    agent_name: str
    title: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentSessionDetailResponse(BaseModel):
    """Session details with chronological message list."""
    session: AgentSessionResponse
    messages: list[AgentMessageResponse]


class ToolCallDetailResponse(BaseModel):
    """Audit record of a tool execution."""
    id: uuid.UUID
    tool_name: str
    parameters: dict[str, Any]
    result: Any | None = None
    status: str
    latency_ms: int
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentRunDetailResponse(BaseModel):
    """Full execution trace of an agent run."""
    id: uuid.UUID
    session_id: uuid.UUID
    trace_id: str
    agent_name: str
    model: str
    status: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    error_message: str | None = None
    tool_calls: list[ToolCallDetailResponse] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}
