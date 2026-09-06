"""
backend/api/stats.py — Aggregated platform statistics and time-series timeline endpoints
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.schemas.stats import (
    StatsSummaryResponse,
    TimelineResponse,
)
from backend.services.stats_service import (
    get_platform_stats_summary,
    get_reports_timeline,
)

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/summary", response_model=StatsSummaryResponse)
def get_stats_summary(
    db: Session = Depends(get_db),
) -> StatsSummaryResponse:
    """
    Returns platform-wide summary statistics derived exclusively from live SQL aggregations.
    Includes report totals, canonical/duplicate breakdown, verification state,
    damage type/severity distributions, and earthquake event counts.
    """
    return get_platform_stats_summary(session=db)


@router.get("/timeline", response_model=TimelineResponse)
def get_timeline(
    date_from: Optional[datetime] = Query(None, description="Start date for timeline (UTC)"),
    date_to: Optional[datetime] = Query(None, description="End date for timeline (UTC)"),
    interval: Literal["hour", "day", "week"] = Query("day", description="Aggregation bucket interval"),
    db: Session = Depends(get_db),
) -> TimelineResponse:
    """
    Returns time-series report volume bucketed by hour, day, or week.
    Powers interactive charts and trend displays in the dashboard.
    """
    return get_reports_timeline(
        session=db,
        date_from=date_from,
        date_to=date_to,
        interval=interval,
    )
