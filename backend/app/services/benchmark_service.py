"""
Flowmint AI — Benchmark Persistence and Retrieval Service.

Manages test suite execution and records metrics into evaluation_benchmarks.
Enforces strict distinction between MockLLM and Real LLM evaluation runs.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Sequence

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.evaluation.runner import BenchmarkSummary, EvaluationRunner
from app.models.attribution import EvaluationBenchmark


class BenchmarkService:
    @staticmethod
    async def run_and_record_benchmark(
        db: AsyncSession,
        runner_type: str = "mock_llm",
        model_name: str | None = None,
    ) -> EvaluationBenchmark:
        """
        Executes the 900-case evaluation benchmark and saves results to the database.
        """
        effective_model = model_name or ("mock-llm-v1" if runner_type == "mock_llm" else "gpt-4o-mini")
        runner = EvaluationRunner(runner_type=runner_type, model_name=effective_model)
        summary: BenchmarkSummary = runner.run_benchmark()

        record = EvaluationBenchmark(
            runner_type=summary.runner_type,
            model_name=summary.model_name,
            dataset_version=summary.dataset_version,
            total_cases=summary.total_cases,
            passed_cases=summary.passed_cases,
            intent_accuracy=Decimal(str(summary.intent_accuracy)),
            tool_accuracy=Decimal(str(summary.tool_accuracy)),
            param_accuracy=Decimal(str(summary.param_accuracy)),
            grounding_rate=Decimal(str(summary.grounding_rate)),
            hallucination_rate=Decimal(str(summary.hallucination_rate)),
            safety_pass_rate=Decimal(str(summary.safety_pass_rate)),
            injection_resistance_rate=Decimal(str(summary.injection_resistance_rate)),
            avg_latency_ms=summary.avg_latency_ms,
            total_tokens=summary.total_tokens,
            estimated_cost_usd=Decimal(str(summary.estimated_cost_usd)),
            results_breakdown={
                "category_breakdown": summary.category_breakdown,
                "summary": {
                    "total": summary.total_cases,
                    "passed": summary.passed_cases,
                    "cost_usd": summary.estimated_cost_usd,
                    "avg_latency_ms": summary.avg_latency_ms,
                },
            },
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record

    @staticmethod
    async def list_benchmarks(
        db: AsyncSession,
        runner_type: str | None = None,
        limit: int = 20,
    ) -> Sequence[EvaluationBenchmark]:
        stmt = select(EvaluationBenchmark).order_by(desc(EvaluationBenchmark.created_at)).limit(limit)
        if runner_type:
            stmt = stmt.where(EvaluationBenchmark.runner_type == runner_type)
        res = await db.execute(stmt)
        return res.scalars().all()

    @staticmethod
    async def get_benchmark(
        db: AsyncSession,
        benchmark_id: uuid.UUID,
    ) -> EvaluationBenchmark | None:
        stmt = select(EvaluationBenchmark).where(EvaluationBenchmark.id == benchmark_id)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()
