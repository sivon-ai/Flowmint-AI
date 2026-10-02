"""Health check endpoints."""

from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
async def health_check():
    return {"status": "ok", "service": "flowmint-ai"}


@router.get("/ready")
async def readiness_check():
    # TODO: Check DB and Redis connectivity
    return {"status": "ready"}
