"""
backend/api/weather_incidents.py
================================
REST API endpoints for queried clustered weather incidents and hotspot zones.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.schemas.weather_api_schemas import (
    WeatherIncidentListResponse,
    WeatherIncidentResponse,
)
from backend.services.weather_incident_service import WeatherIncidentService

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("", response_model=WeatherIncidentListResponse)
def list_incidents(
    category: Optional[str] = Query(None, description="rainfall, flooding, thunderstorm, etc."),
    city: Optional[str] = Query(None, description="City name"),
    state: Optional[str] = Query(None, description="State name"),
    severity: Optional[str] = Query(None, description="low, moderate, high, severe"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> WeatherIncidentListResponse:
    """Retrieve list of active weather incidents ordered by platform impact score."""
    service = WeatherIncidentService(db)
    items, total = service.get_incidents(
        category=category,
        city=city,
        state=state,
        severity=severity,
        limit=limit,
        offset=offset,
    )
    return WeatherIncidentListResponse(
        items=[WeatherIncidentResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{incident_id}", response_model=WeatherIncidentResponse)
def get_incident(
    incident_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> WeatherIncidentResponse:
    """Fetch details of a specific weather incident."""
    service = WeatherIncidentService(db)
    inc = service.get_by_incident_id(incident_id)
    if not inc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return WeatherIncidentResponse.model_validate(inc)


@router.post("/recluster", status_code=status.HTTP_200_OK)
def trigger_clustering(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Trigger spatiotemporal re-clustering of reports into incidents."""
    service = WeatherIncidentService(db)
    count = service.sync_incidents_from_reports()
    return {"status": "success", "incidents_created": count}
