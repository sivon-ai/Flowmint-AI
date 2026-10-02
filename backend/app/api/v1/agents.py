"""
Flowmint AI — Agent API Endpoints (Phase 2A).

Provides:
- POST /api/v1/agents/chat (Intent-routed orchestration)
- POST /api/v1/agents/buyer (Direct Buyer Agent)
- POST /api/v1/agents/analytics (Direct Analytics Agent)
- GET  /api/v1/agents/sessions (List merchant sessions)
- GET  /api/v1/agents/sessions/{id} (Get session with history)
- GET  /api/v1/agents/runs/{id} (Get run trace and tool calls)
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.agents.orchestrator import AgentOrchestrator
from app.api.deps import CurrentUser, get_current_user
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.agent import AgentRun, AgentSession
from app.schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    AgentMessageResponse,
    AgentRunDetailResponse,
    AgentSessionDetailResponse,
    AgentSessionResponse,
    ToolCallDetailResponse,
)
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/agents", tags=["Agents"])
orchestrator = AgentOrchestrator()


@router.post("/chat", response_model=ApiResponse[AgentChatResponse])
async def agent_chat(
    data: AgentChatRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    General agent conversational endpoint.
    Routes intelligently between Buyer Agent and Analytics Agent.
    """
    result, session = await orchestrator.run(
        db=db,
        merchant_id=user.merchant_id,
        user_id=user.user_id,
        user_message=data.message,
        session_id=data.session_id,
    )
    return ApiResponse.ok(
        AgentChatResponse(
            session_id=session.id,
            trace_id=result.trace_id,
            agent_name=result.agent_name,
            response=result.response,
            structured_data=result.structured_data,
            action_plan=result.action_plan,
            tool_calls=result.tool_calls,
            latency_ms=result.latency_ms,
        )
    )


@router.post("/buyer", response_model=ApiResponse[AgentChatResponse])
async def buyer_agent_chat(
    data: AgentChatRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Directly invokes the Buyer Agent for product and inventory queries."""
    result, session = await orchestrator.run(
        db=db,
        merchant_id=user.merchant_id,
        user_id=user.user_id,
        user_message=data.message,
        session_id=data.session_id,
        forced_agent="buyer_agent",
    )
    return ApiResponse.ok(
        AgentChatResponse(
            session_id=session.id,
            trace_id=result.trace_id,
            agent_name=result.agent_name,
            response=result.response,
            structured_data=result.structured_data,
            action_plan=result.action_plan,
            tool_calls=result.tool_calls,
            latency_ms=result.latency_ms,
        )
    )


@router.post("/analytics", response_model=ApiResponse[AgentChatResponse])
async def analytics_agent_chat(
    data: AgentChatRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Directly invokes the Analytics Agent for revenue and performance queries."""
    result, session = await orchestrator.run(
        db=db,
        merchant_id=user.merchant_id,
        user_id=user.user_id,
        user_message=data.message,
        session_id=data.session_id,
        forced_agent="analytics_agent",
    )
    return ApiResponse.ok(
        AgentChatResponse(
            session_id=session.id,
            trace_id=result.trace_id,
            agent_name=result.agent_name,
            response=result.response,
            structured_data=result.structured_data,
            action_plan=result.action_plan,
            tool_calls=result.tool_calls,
            latency_ms=result.latency_ms,
        )
    )


@router.post("/growth", response_model=ApiResponse[AgentChatResponse])
async def growth_agent_chat(
    data: AgentChatRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Directly invokes the Growth Agent for cross-sell, bundle, and upsell recommendations."""
    result, session = await orchestrator.run(
        db=db,
        merchant_id=user.merchant_id,
        user_id=user.user_id,
        user_message=data.message,
        session_id=data.session_id,
        forced_agent="growth_agent",
    )
    return ApiResponse.ok(
        AgentChatResponse(
            session_id=session.id,
            trace_id=result.trace_id,
            agent_name=result.agent_name,
            response=result.response,
            structured_data=result.structured_data,
            action_plan=result.action_plan,
            tool_calls=result.tool_calls,
            latency_ms=result.latency_ms,
        )
    )


@router.post("/recovery", response_model=ApiResponse[AgentChatResponse])
async def recovery_agent_chat(
    data: AgentChatRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Directly invokes the Recovery Agent for abandoned cart and failed payment recovery."""
    result, session = await orchestrator.run(
        db=db,
        merchant_id=user.merchant_id,
        user_id=user.user_id,
        user_message=data.message,
        session_id=data.session_id,
        forced_agent="recovery_agent",
    )
    return ApiResponse.ok(
        AgentChatResponse(
            session_id=session.id,
            trace_id=result.trace_id,
            agent_name=result.agent_name,
            response=result.response,
            structured_data=result.structured_data,
            action_plan=result.action_plan,
            tool_calls=result.tool_calls,
            latency_ms=result.latency_ms,
        )
    )


@router.get("/sessions", response_model=ApiResponse[list[AgentSessionResponse]])
async def list_agent_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List agent chat sessions for the current merchant."""
    query = (
        select(AgentSession)
        .where(AgentSession.merchant_id == user.merchant_id)
        .order_by(AgentSession.updated_at.desc())
        .limit(limit)
    )
    res = await db.execute(query)
    sessions = res.scalars().all()
    return ApiResponse.ok([AgentSessionResponse.model_validate(s) for s in sessions])


@router.get("/sessions/{session_id}", response_model=ApiResponse[AgentSessionDetailResponse])
async def get_agent_session_detail(
    session_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve an agent session with chronological message history."""
    query = (
        select(AgentSession)
        .options(selectinload(AgentSession.messages))
        .where(
            AgentSession.id == session_id,
            AgentSession.merchant_id == user.merchant_id,
        )
    )
    res = await db.execute(query)
    session = res.scalar_one_or_none()
    if not session:
        raise NotFoundError("AgentSession", str(session_id))

    messages = [
        AgentMessageResponse(
            id=m.id,
            role=m.role,
            content=m.content,
            tool_calls=m.tool_calls,
            metadata_json=m.metadata_json,
            created_at=m.created_at,
        )
        for m in session.messages
    ]

    return ApiResponse.ok(
        AgentSessionDetailResponse(
            session=AgentSessionResponse.model_validate(session),
            messages=messages,
        )
    )


@router.get("/runs/{run_id}", response_model=ApiResponse[AgentRunDetailResponse])
async def get_agent_run_detail(
    run_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full execution trace and tool calls for an agent run."""
    query = (
        select(AgentRun)
        .options(selectinload(AgentRun.tool_calls))
        .where(
            AgentRun.id == run_id,
            AgentRun.merchant_id == user.merchant_id,
        )
    )
    res = await db.execute(query)
    run = res.scalar_one_or_none()
    if not run:
        raise NotFoundError("AgentRun", str(run_id))

    tool_call_details = [
        ToolCallDetailResponse(
            id=tc.id,
            tool_name=tc.tool_name,
            parameters=tc.parameters,
            result=tc.result,
            status=tc.status,
            latency_ms=tc.latency_ms,
            error_message=tc.error_message,
            created_at=tc.created_at,
        )
        for tc in run.tool_calls
    ]

    return ApiResponse.ok(
        AgentRunDetailResponse(
            id=run.id,
            session_id=run.session_id,
            trace_id=run.trace_id,
            agent_name=run.agent_name,
            model=run.model,
            status=run.status,
            prompt_tokens=run.prompt_tokens,
            completion_tokens=run.completion_tokens,
            latency_ms=run.latency_ms,
            error_message=run.error_message,
            tool_calls=tool_call_details,
            created_at=run.created_at,
        )
    )
