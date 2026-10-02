"""
Flowmint AI — AI Evaluation Benchmark API Endpoints (Phase 4).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.database import get_db
from app.schemas.attribution import BenchmarkRunRequest, EvaluationBenchmarkResponse
from app.schemas.common import ApiResponse
from app.services.benchmark_service import BenchmarkService

router = APIRouter(prefix="/evaluation", tags=["Evaluation"])


@router.get("/benchmarks", response_model=ApiResponse[list[EvaluationBenchmarkResponse]])
async def list_benchmarks(
    runner_type: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    benchmarks = await BenchmarkService.list_benchmarks(db, runner_type=runner_type, limit=limit)
    return ApiResponse.ok([EvaluationBenchmarkResponse.model_validate(b) for b in benchmarks])


@router.get("/benchmarks/{id}", response_model=ApiResponse[EvaluationBenchmarkResponse])
async def get_benchmark(
    id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = await BenchmarkService.get_benchmark(db, id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Benchmark run {id} not found",
        )
    return ApiResponse.ok(EvaluationBenchmarkResponse.model_validate(record))


@router.post("/run", response_model=ApiResponse[EvaluationBenchmarkResponse])
async def run_benchmark(
    req: BenchmarkRunRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = await BenchmarkService.run_and_record_benchmark(
        db=db,
        runner_type=req.runner_type,
        model_name=req.model_name,
    )
    return ApiResponse.ok(EvaluationBenchmarkResponse.model_validate(record))
