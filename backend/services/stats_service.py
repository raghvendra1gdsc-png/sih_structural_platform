"""
backend/services/stats_service.py — Aggregated statistics & time-series timeline aggregation
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from backend.db.models import ReportORM
from backend.schemas.stats import (
    StatsSummaryResponse,
    TimelineDataPoint,
    TimelineResponse,
)


def get_platform_stats_summary(session: Session) -> StatsSummaryResponse:
    """
    Computes real-time platform statistics derived strictly from live PostgreSQL queries.
    Never uses hardcoded figures.
    """
    total = session.query(func.count(ReportORM.id)).scalar() or 0
    canonical = session.query(func.count(ReportORM.id)).filter(ReportORM.duplicate_of.is_(None)).scalar() or 0
    duplicate = session.query(func.count(ReportORM.id)).filter(ReportORM.duplicate_of.is_not(None)).scalar() or 0

    verified = session.query(func.count(ReportORM.id)).filter(ReportORM.verification_status == "verified").scalar() or 0
    pending = session.query(func.count(ReportORM.id)).filter(ReportORM.verification_status == "pending").scalar() or 0
    rejected = session.query(func.count(ReportORM.id)).filter(ReportORM.verification_status == "rejected").scalar() or 0

    with_images = (
        session.query(func.count(ReportORM.id))
        .filter(ReportORM.image_reference.is_not(None))
        .filter(ReportORM.image_reference != "")
        .scalar()
        or 0
    )
    classified = session.query(func.count(ReportORM.id)).filter(ReportORM.classified_at.is_not(None)).scalar() or 0

    synthetic = session.query(func.count(ReportORM.id)).filter(ReportORM.is_synthetic.is_(True)).scalar() or 0
    real = session.query(func.count(ReportORM.id)).filter(ReportORM.is_synthetic.is_(False)).scalar() or 0

    # Groupings
    dt_rows = session.query(ReportORM.damage_type, func.count(ReportORM.id)).group_by(ReportORM.damage_type).all()
    dt_counts = {(r[0].value if hasattr(r[0], "value") else str(r[0])): int(r[1]) for r in dt_rows}

    sev_rows = session.query(ReportORM.severity, func.count(ReportORM.id)).group_by(ReportORM.severity).all()
    sev_counts = {(r[0].value if hasattr(r[0], "value") else str(r[0])): int(r[1]) for r in sev_rows}

    src_rows = session.query(ReportORM.source, func.count(ReportORM.id)).group_by(ReportORM.source).all()
    src_counts = {(r[0].value if hasattr(r[0], "value") else str(r[0])): int(r[1]) for r in src_rows}

    evt_rows = (
        session.query(ReportORM.earthquake_event_id, func.count(ReportORM.id))
        .filter(ReportORM.earthquake_event_id.is_not(None))
        .group_by(ReportORM.earthquake_event_id)
        .all()
    )
    evt_counts = {str(r[0]): int(r[1]) for r in evt_rows}

    return StatsSummaryResponse(
        total_reports=total,
        canonical_reports=canonical,
        duplicate_reports=duplicate,
        verified_reports=verified,
        pending_reports=pending,
        rejected_reports=rejected,
        reports_with_images=with_images,
        classified_reports=classified,
        synthetic_reports=synthetic,
        real_reports=real,
        damage_type_counts=dt_counts,
        severity_counts=sev_counts,
        source_counts=src_counts,
        event_counts=evt_counts,
    )


def get_reports_timeline(
    session: Session,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    interval: Literal["hour", "day", "week"] = "day",
) -> TimelineResponse:
    """
    Computes time-series report counts bucketed by the specified interval (hour/day/week)
    using PostgreSQL date_trunc.
    """
    valid_intervals = {"hour", "day", "week"}
    if interval not in valid_intervals:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid interval '{interval}'. Supported intervals: {sorted(list(valid_intervals))}",
        )

    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_from must be before or equal to date_to",
        )

    # Use date_trunc for PostgreSQL
    bucket_col = func.date_trunc(interval, ReportORM.submitted_at).label("time_bucket")

    query = session.query(bucket_col, func.count(ReportORM.id))

    if date_from:
        query = query.filter(ReportORM.submitted_at >= date_from)
    if date_to:
        query = query.filter(ReportORM.submitted_at <= date_to)

    rows = query.group_by(bucket_col).order_by(bucket_col.asc()).all()

    data: list[TimelineDataPoint] = []
    total_in_period = 0

    for bucket_dt, count in rows:
        if bucket_dt is not None:
            formatted_date = bucket_dt.strftime("%Y-%m-%dT%H:%M:%SZ") if interval == "hour" else bucket_dt.strftime("%Y-%m-%d")
            data.append(TimelineDataPoint(date=formatted_date, count=int(count)))
            total_in_period += int(count)

    return TimelineResponse(
        interval=interval,
        total_reports=total_in_period,
        data=data,
    )
