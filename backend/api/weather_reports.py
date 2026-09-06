"""
backend/api/weather_reports.py
==============================
REST API endpoints for querying and ingesting weather reports.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.schemas.weather_api_schemas import (
    WeatherReportListResponse,
    WeatherReportResponse,
)
from backend.services.weather_report_service import WeatherReportService
from ingestion.weather_schemas import RawWeatherReport

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("", response_model=WeatherReportListResponse)
def list_reports(
    city: Optional[str] = Query(None, description="Filter by city name"),
    state: Optional[str] = Query(None, description="Filter by state name"),
    category: Optional[str] = Query(None, description="Filter by weather category"),
    verification_status: Optional[str] = Query(None, description="pending, verified, rejected, etc."),
    source: Optional[str] = Query(None, description="citizen, weather_api, synthetic, etc."),
    only_canonical: bool = Query(False, description="Exclude duplicate reports"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> WeatherReportListResponse:
    """Retrieve paginated list of weather reports with flexible filtering."""
    service = WeatherReportService(db)
    items, total = service.get_reports(
        city=city,
        state=state,
        category=category,
        verification_status=verification_status,
        source=source,
        only_canonical=only_canonical,
        limit=limit,
        offset=offset,
    )
    return WeatherReportListResponse(
        items=[WeatherReportResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/nearby", response_model=list[WeatherReportResponse])
def get_nearby_reports(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Longitude"),
    radius_km: float = Query(15.0, ge=0.5, le=100.0, description="Search radius in km"),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[WeatherReportResponse]:
    """Geospatial query for reports within radius using PostGIS ST_DWithin."""
    service = WeatherReportService(db)
    reports = service.get_nearby_reports(lat, lon, radius_km=radius_km, limit=limit)
    return [WeatherReportResponse.model_validate(r) for r in reports]


@router.get("/{report_id}", response_model=WeatherReportResponse)
def get_report(
    report_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> WeatherReportResponse:
    """Fetch single weather report details by report UUID."""
    service = WeatherReportService(db)
    report = service.get_by_report_id(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return WeatherReportResponse.model_validate(report)


@router.post("", response_model=WeatherReportResponse, status_code=status.HTTP_201_CREATED)
def submit_report(
    payload: RawWeatherReport,
    db: Session = Depends(get_db),
) -> WeatherReportResponse:
    """
    Ingest a new citizen or sensor weather report.
    Automatically executes normalization, AI classification, deduplication, and trust scoring.
    """
    service = WeatherReportService(db)
    created = service.ingest_report(payload)
    return WeatherReportResponse.model_validate(created)
