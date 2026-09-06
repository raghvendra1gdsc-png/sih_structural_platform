"""
backend/api/weather_stats.py
============================
REST API endpoints for real-time analytics, KPIs, category distributions,
source reliability, and big-data quality metrics.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.services.weather_stats_service import WeatherStatsService

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/summary")
def get_stats_summary(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return primary dashboard KPI metrics (reports, verified, pending, incidents, impact)."""
    service = WeatherStatsService(db)
    return service.get_summary()


@router.get("/by-category")
def get_stats_by_category(
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Return observation counts grouped by weather category."""
    service = WeatherStatsService(db)
    return service.get_by_category()


@router.get("/by-state")
def get_stats_by_state(
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Return observation counts grouped by Indian state."""
    service = WeatherStatsService(db)
    return service.get_by_state()


@router.get("/timeline")
def get_stats_timeline(
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Return report submission counts bucketed by hour."""
    service = WeatherStatsService(db)
    return service.get_timeline(limit_hours=hours)


@router.get("/source-reliability")
def get_source_reliability(
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Return report volume and average trust scores per data source."""
    service = WeatherStatsService(db)
    return service.get_source_reliability()


@router.get("/data-quality")
def get_data_quality(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return big-data pipeline operational metrics: ingestion latency, dedup %, queue depth."""
    service = WeatherStatsService(db)
    return service.get_data_quality()
