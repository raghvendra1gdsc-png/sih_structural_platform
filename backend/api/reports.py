"""
backend/api/reports.py — Report list, geospatial radius search, and single report endpoints
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.schemas.reports import (
    NearbyReportListResponse,
    ReportListResponse,
    ReportResponse,
)
from backend.services.report_service import (
    get_nearby_reports,
    get_report_by_id,
    get_reports,
)

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("", response_model=ReportListResponse)
def list_reports(
    event_id: Optional[str] = Query(None, description="Filter by USGS earthquake event ID"),
    verification_status: Optional[str] = Query(None, description="Filter by verification status (pending, verified, rejected)"),
    damage_type: Optional[str] = Query(None, description="Filter by structural damage type"),
    damage_severity: Optional[str] = Query(None, description="Filter by damage severity"),
    source: Optional[str] = Query(None, description="Filter by data source"),
    is_synthetic: Optional[bool] = Query(None, description="Filter by synthetic demo flag"),
    is_canonical: Optional[bool] = Query(None, description="Filter canonical reports only (true) or duplicates (false)"),
    date_from: Optional[datetime] = Query(None, description="Earliest submission datetime (UTC)"),
    date_to: Optional[datetime] = Query(None, description="Latest submission datetime (UTC)"),
    latitude: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Center latitude for spatial radius filter"),
    longitude: Optional[float] = Query(None, ge=-180.0, le=180.0, description="Center longitude for spatial radius filter"),
    radius_km: Optional[float] = Query(None, gt=0.0, le=1000.0, description="Search radius in kilometers"),
    limit: int = Query(50, ge=1, le=500, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
) -> ReportListResponse:
    """
    Search and filter reports from PostgreSQL/PostGIS.
    Supports attribute filtering, temporal ranges, spatial radius bounding, and safe pagination.
    """
    return get_reports(
        session=db,
        event_id=event_id,
        verification_status=verification_status,
        damage_type=damage_type,
        damage_severity=damage_severity,
        source=source,
        is_synthetic=is_synthetic,
        is_canonical=is_canonical,
        date_from=date_from,
        date_to=date_to,
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        limit=limit,
        offset=offset,
    )


@router.get("/nearby", response_model=NearbyReportListResponse)
def find_nearby_reports(
    latitude: float = Query(..., ge=-90.0, le=90.0, description="Center latitude"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="Center longitude"),
    radius_km: float = Query(50.0, gt=0.0, le=1000.0, description="Search radius in kilometers"),
    limit: int = Query(50, ge=1, le=500, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
) -> NearbyReportListResponse:
    """
    Geospatial radius search using PostGIS ST_DWithin on WGS-84 geography points.
    Calculates meter-accurate spherical geodesic distance and returns reports sorted by proximity.
    """
    return get_nearby_reports(
        session=db,
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        limit=limit,
        offset=offset,
    )


@router.get("/{report_id}", response_model=ReportResponse)
def get_single_report(
    report_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ReportResponse:
    """
    Retrieve full metadata and intelligence attributes for a single report by its UUID.
    Returns HTTP 404 if the report does not exist.
    """
    report = get_report_by_id(session=db, report_id=report_id)
    return ReportResponse.model_validate(report)
