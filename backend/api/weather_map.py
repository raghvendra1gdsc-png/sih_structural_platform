"""
backend/api/weather_map.py
==========================
GeoJSON map endpoints for reports, clustered incidents, and density hotspots.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.db.models import WeatherIncidentORM, WeatherReportORM
from backend.db.session import get_db

router = APIRouter(prefix="/api/map", tags=["map"])


@router.get("/reports")
def get_map_reports(
    category: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    limit: int = Query(250, ge=10, le=1000),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return GeoJSON FeatureCollection of canonical weather reports for map rendering."""
    stmt = select(WeatherReportORM).where(WeatherReportORM.duplicate_of.is_(None))
    if category:
        stmt = stmt.where(WeatherReportORM.event_category == category.lower())
    if city:
        stmt = stmt.where(WeatherReportORM.city.ilike(f"%{city}%"))

    reports = list(self_db := db.scalars(stmt.order_by(desc(WeatherReportORM.event_time)).limit(limit)).all())

    features = []
    for r in reports:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [r.longitude, r.latitude],
            },
            "properties": {
                "report_id": str(r.report_id),
                "city": r.city,
                "state": r.state,
                "category": r.event_category,
                "confidence": r.event_confidence,
                "trust_score": r.source_trust_score,
                "verification_status": r.verification_status,
                "text": r.text,
                "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


@router.get("/incidents")
def get_map_incidents(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return GeoJSON FeatureCollection of clustered weather incidents with impact scores."""
    stmt = select(WeatherIncidentORM).order_by(desc(WeatherIncidentORM.impact_score))
    incidents = list(db.scalars(stmt).all())

    features = []
    for inc in incidents:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [inc.longitude, inc.latitude],
            },
            "properties": {
                "incident_id": str(inc.incident_id),
                "city": inc.city,
                "state": inc.state,
                "category": inc.event_category,
                "report_count": inc.report_count,
                "verified_count": inc.verified_count,
                "severity": inc.severity,
                "impact_score": inc.impact_score,
                "radius_km": inc.radius_km,
                "summary": inc.summary,
                "start_time": inc.start_time.isoformat() if inc.start_time else None,
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


@router.get("/hotspots")
def get_map_hotspots(
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Return simplified hotspot list for rapid map overlay rendering."""
    stmt = (
        select(WeatherIncidentORM)
        .where(WeatherIncidentORM.impact_score >= 50.0)
        .order_by(desc(WeatherIncidentORM.impact_score))
    )
    incidents = list(db.scalars(stmt).all())

    return [
        {
            "id": str(inc.incident_id),
            "city": inc.city,
            "category": inc.event_category,
            "latitude": inc.latitude,
            "longitude": inc.longitude,
            "impact_score": inc.impact_score,
            "severity": inc.severity,
            "radius_km": inc.radius_km,
            "report_count": inc.report_count,
        }
        for inc in incidents
    ]
