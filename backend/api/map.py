"""
backend/api/map.py — GeoJSON FeatureCollection endpoint for interactive map rendering
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.db.models import ReportORM
from backend.db.session import get_db
from backend.schemas.common import GeoJSONFeatureCollection
from backend.services.geo_service import reports_to_geojson_feature_collection

router = APIRouter(prefix="/api/map", tags=["map"])


@router.get("/reports", response_model=GeoJSONFeatureCollection)
def get_map_reports(
    event_id: Optional[str] = Query(None, description="Filter by earthquake event ID"),
    damage_type: Optional[str] = Query(None, description="Filter by damage type"),
    severity: Optional[str] = Query(None, description="Filter by damage severity"),
    verification_status: Optional[str] = Query(None, description="Filter by verification status"),
    is_canonical: Optional[bool] = Query(True, description="Default: show canonical reports only to reduce map clutter"),
    limit: int = Query(500, ge=1, le=2000, description="Max features to return for map"),
    db: Session = Depends(get_db),
) -> GeoJSONFeatureCollection:
    """
    Returns lightweight GeoJSON FeatureCollection designed specifically for map rendering.
    Omits heavy payloads to ensure fast browser rendering.
    """
    query = db.query(ReportORM)

    if event_id:
        query = query.filter(ReportORM.earthquake_event_id == event_id)
    if damage_type:
        query = query.filter(ReportORM.damage_type == damage_type)
    if severity:
        query = query.filter(ReportORM.severity == severity)
    if verification_status:
        query = query.filter(ReportORM.verification_status == verification_status)
    if is_canonical is True:
        query = query.filter(ReportORM.duplicate_of.is_(None))
    elif is_canonical is False:
        query = query.filter(ReportORM.duplicate_of.is_not(None))

    reports = query.limit(limit).all()
    return reports_to_geojson_feature_collection(reports)
