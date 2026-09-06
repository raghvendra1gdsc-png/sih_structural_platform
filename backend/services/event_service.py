"""
backend/services/event_service.py — Earthquake event retrieval & impact summary aggregation
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from backend.db.models import EarthquakeEventORM, ReportORM
from backend.schemas.events import (
    EventImpactSummary,
    EventListResponse,
    EventResponse,
)


def get_events(
    session: Session,
    geographic_scope: Optional[str] = None,
    min_magnitude: Optional[float] = None,
    max_magnitude: Optional[float] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
) -> EventListResponse:
    """List earthquake events with optional filtering and pagination."""
    query = session.query(EarthquakeEventORM)

    if geographic_scope:
        query = query.filter(EarthquakeEventORM.geographic_scope == geographic_scope)
    if min_magnitude is not None:
        query = query.filter(EarthquakeEventORM.magnitude >= min_magnitude)
    if max_magnitude is not None:
        query = query.filter(EarthquakeEventORM.magnitude <= max_magnitude)
    if date_from:
        query = query.filter(EarthquakeEventORM.event_time >= date_from)
    if date_to:
        query = query.filter(EarthquakeEventORM.event_time <= date_to)

    total = query.count()
    items = query.order_by(desc(EarthquakeEventORM.event_time)).offset(offset).limit(limit).all()

    return EventListResponse(
        items=[EventResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_event_by_id(session: Session, event_id: str) -> EarthquakeEventORM:
    """Retrieve an earthquake event by USGS event_id, or raise 404."""
    event = session.query(EarthquakeEventORM).filter(EarthquakeEventORM.event_id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Earthquake event '{event_id}' not found.",
        )
    return event


def get_event_summary(session: Session, event_id: str) -> EventImpactSummary:
    """
    Computes an impact summary for a given earthquake event by aggregating associated reports in PostgreSQL.
    """
    event = get_event_by_id(session, event_id)

    # Base query for reports attached to this earthquake
    r_query = session.query(ReportORM).filter(ReportORM.earthquake_event_id == event_id)
    total_reports = r_query.count()

    canonical_reports = r_query.filter(ReportORM.duplicate_of.is_(None)).count()
    duplicate_reports = r_query.filter(ReportORM.duplicate_of.is_not(None)).count()

    verified_reports = r_query.filter(ReportORM.verification_status == "verified").count()
    pending_reports = r_query.filter(ReportORM.verification_status == "pending").count()
    rejected_reports = r_query.filter(ReportORM.verification_status == "rejected").count()

    # Distributions via GROUP BY
    sev_rows = (
        session.query(ReportORM.severity, func.count(ReportORM.id))
        .filter(ReportORM.earthquake_event_id == event_id)
        .group_by(ReportORM.severity)
        .all()
    )
    severity_dist = {
        (row[0].value if hasattr(row[0], "value") else str(row[0])): int(row[1])
        for row in sev_rows
    }

    type_rows = (
        session.query(ReportORM.damage_type, func.count(ReportORM.id))
        .filter(ReportORM.earthquake_event_id == event_id)
        .group_by(ReportORM.damage_type)
        .all()
    )
    type_dist = {
        (row[0].value if hasattr(row[0], "value") else str(row[0])): int(row[1])
        for row in type_rows
    }

    src_rows = (
        session.query(ReportORM.source, func.count(ReportORM.id))
        .filter(ReportORM.earthquake_event_id == event_id)
        .group_by(ReportORM.source)
        .all()
    )
    src_dist = {
        (row[0].value if hasattr(row[0], "value") else str(row[0])): int(row[1])
        for row in src_rows
    }

    # Bounding box of reports
    bbox_row = (
        session.query(
            func.min(ReportORM.latitude),
            func.max(ReportORM.latitude),
            func.min(ReportORM.longitude),
            func.max(ReportORM.longitude),
        )
        .filter(ReportORM.earthquake_event_id == event_id)
        .first()
    )

    bounding_box = None
    if bbox_row and bbox_row[0] is not None:
        bounding_box = {
            "min_latitude": round(float(bbox_row[0]), 5),
            "max_latitude": round(float(bbox_row[1]), 5),
            "min_longitude": round(float(bbox_row[2]), 5),
            "max_longitude": round(float(bbox_row[3]), 5),
        }

    return EventImpactSummary(
        event_id=event.event_id,
        place=event.place,
        magnitude=event.magnitude,
        event_time=event.event_time,
        geographic_scope=event.geographic_scope.value if hasattr(event.geographic_scope, "value") else str(event.geographic_scope),
        total_reports=total_reports,
        canonical_reports=canonical_reports,
        duplicate_reports=duplicate_reports,
        verified_reports=verified_reports,
        pending_reports=pending_reports,
        rejected_reports=rejected_reports,
        severity_distribution=severity_dist,
        damage_type_distribution=type_dist,
        source_distribution=src_dist,
        bounding_box=bounding_box,
    )
