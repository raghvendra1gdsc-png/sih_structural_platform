"""
backend/api/events.py — Earthquake event listing, details, and impact summary endpoints
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.schemas.events import (
    EventImpactSummary,
    EventListResponse,
    EventResponse,
)
from backend.services.event_service import (
    get_event_by_id,
    get_event_summary,
    get_events,
)

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=EventListResponse)
def list_events(
    geographic_scope: Optional[str] = Query(None, description="Filter by geographic scope (india, regional, other)"),
    min_magnitude: Optional[float] = Query(None, ge=0.0, le=10.0, description="Minimum magnitude threshold"),
    max_magnitude: Optional[float] = Query(None, ge=0.0, le=10.0, description="Maximum magnitude threshold"),
    date_from: Optional[datetime] = Query(None, description="Earliest event datetime (UTC)"),
    date_to: Optional[datetime] = Query(None, description="Latest event datetime (UTC)"),
    limit: int = Query(50, ge=1, le=500, description="Max events to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
) -> EventListResponse:
    """
    List seismic events stored from USGS feeds, sorted by event time descending.
    """
    return get_events(
        session=db,
        geographic_scope=geographic_scope,
        min_magnitude=min_magnitude,
        max_magnitude=max_magnitude,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )


@router.get("/{event_id}", response_model=EventResponse)
def get_single_event(
    event_id: str,
    db: Session = Depends(get_db),
) -> EventResponse:
    """
    Retrieve seismic parameters and USGS metadata for a single earthquake event.
    Returns HTTP 404 if the event is not found.
    """
    event = get_event_by_id(session=db, event_id=event_id)
    return EventResponse.model_validate(event)


@router.get("/{event_id}/summary", response_model=EventImpactSummary)
def get_single_event_summary(
    event_id: str,
    db: Session = Depends(get_db),
) -> EventImpactSummary:
    """
    Computes an impact summary for an earthquake event based on aggregated reports in PostgreSQL.
    Provides report counts, verification breakdown, damage and severity distributions, and geographic bounds.
    """
    return get_event_summary(session=db, event_id=event_id)
