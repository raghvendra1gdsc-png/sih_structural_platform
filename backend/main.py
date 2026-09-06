"""
backend/main.py — National Weather Big Data Analytics Platform FastAPI Application
"""

from __future__ import annotations

import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api import (
    alerts_router,
    health_router,
    provider_health_router,
    system_health_router,
    weather_admin_router,
    weather_forecast_router,
    weather_gpt_router,
    weather_incidents_router,
    weather_map_router,
    weather_reports_router,
    weather_stats_router,
)
from backend.core.config import settings


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("backend.main")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


def create_app() -> FastAPI:
    """Return the FastAPI application instance."""
    return app


# ---------------------------------------------------------------------------
# CORS Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Global Exception Handlers
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all unhandled exception handler.
    Logs error internally and returns a clean 500 without leaking database stack traces.
    """
    logger.error("Unhandled server exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again later."},
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(health_router)
app.include_router(weather_reports_router)
app.include_router(weather_incidents_router)
app.include_router(weather_map_router)
app.include_router(weather_stats_router)
app.include_router(weather_forecast_router)
app.include_router(weather_admin_router)
app.include_router(weather_gpt_router)
app.include_router(alerts_router)
app.include_router(provider_health_router)
app.include_router(system_health_router)



# ---------------------------------------------------------------------------
# Root Endpoint
# ---------------------------------------------------------------------------


@app.get("/", tags=["ops"])
async def root() -> JSONResponse:
    return JSONResponse(
        {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "status": "online",
            "domain": "National Weather Big Data Analytics Platform",
            "docs": "/docs",
            "openapi": "/openapi.json",
        }
    )
