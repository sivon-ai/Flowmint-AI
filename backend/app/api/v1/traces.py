"""
Flowmint AI — Trace Viewer API Endpoints (Phase 4).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.database import get_db
from app.schemas.attribution import TraceResponse
from app.schemas.common import ApiResponse
from app.services.trace_service import TraceService

router = APIRouter(prefix="/traces", tags=["Traces"])


@router.get("", response_model=ApiResponse[list[dict[str, Any]]])
async def list_traces(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    traces = await TraceService.list_recent_traces(db, current_user.merchant_id)
    return ApiResponse.ok(traces)


@router.get("/{trace_id}", response_model=ApiResponse[TraceResponse])
async def get_trace(
    trace_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    trace_data = await TraceService.get_trace(db, current_user.merchant_id, trace_id)
    if not trace_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace {trace_id} not found",
        )
    return ApiResponse.ok(TraceResponse.model_validate(trace_data))
