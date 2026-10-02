"""
Flowmint AI — Performance & Cost Metrics API Endpoints (Phase 4).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.database import get_db
from app.schemas.attribution import PerformanceMetricsResponse
from app.schemas.common import ApiResponse
from app.services.performance_service import PerformanceMetricsService

router = APIRouter(prefix="/performance", tags=["Performance"])


@router.get("/metrics", response_model=ApiResponse[PerformanceMetricsResponse])
async def get_performance_metrics(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    metrics = PerformanceMetricsService.get_system_performance_metrics()
    return ApiResponse.ok(PerformanceMetricsResponse.model_validate(metrics))
