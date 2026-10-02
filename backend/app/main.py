"""
Flowmint AI — FastAPI Application Factory.

Creates the FastAPI app with:
- CORS middleware
- Exception handlers
- API router mounting
- Startup/shutdown lifecycle events
"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.config import get_settings
from app.core.exceptions import FlowmintError

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.getLogger(__name__).info("Flowmint AI starting up...")
    yield
    from app.database import engine
    await engine.dispose()
    logging.getLogger(__name__).info("Flowmint AI shut down.")


app = FastAPI(
    title="Flowmint AI",
    description="Bounded-autonomy revenue operating system for AI-ready merchants",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Exception Handlers ---
@app.exception_handler(FlowmintError)
async def flowmint_error_handler(request: Request, exc: FlowmintError):
    """Convert FlowmintError subclasses to structured JSON responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "data": None,
            "errors": [
                {
                    "code": exc.code,
                    "message": exc.message,
                    "field": getattr(exc, "field", None),
                }
            ],
        },
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions — never expose internals."""
    logging.getLogger(__name__).exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "data": None,
            "errors": [{"code": "INTERNAL_ERROR", "message": "An internal error occurred"}],
        },
    )


# --- Routers ---
app.include_router(api_router)
