"""
backend/api/alerts.py
=====================
Platform intelligence alerts and rapid event escalation detection.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.db.models import WeatherIncidentORM
from backend.db.session import get_db
from backend.schemas.weather_api_schemas import AlertItem

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertItem])
def get_active_alerts(
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[AlertItem]:
    """
    Generate platform intelligence alerts based on high-impact incidents
    and rapid report escalation.
    """
    stmt = (
        select(WeatherIncidentORM)
        .where(WeatherIncidentORM.impact_score >= 38.0)
        .order_by(desc(WeatherIncidentORM.impact_score))
        .limit(limit)
    )
    incidents = list(db.scalars(stmt).all())

    alerts: list[AlertItem] = []
    now = datetime.now(timezone.utc)

    for inc in incidents:
        if inc.impact_score >= 75.0:
            alert_type = "HIGH_IMPACT_ALERT"
            title = f"CRITICAL WEATHER ALERT — {inc.city.upper()}"
            msg = (
                f"Severe {inc.event_category.replace('_', ' ')} incident with impact score "
                f"{inc.impact_score:.0f}/100. {inc.report_count} citizen reports registered across a {inc.radius_km:.1f} km zone."
            )
        elif inc.report_count >= 15:
            alert_type = "RAPID_EVENT_ESCALATION"
            title = f"RAPID WEATHER ESCALATION — {inc.city.upper()}"
            msg = (
                f"Surge in observations: {inc.report_count} citizen reports received for {inc.event_category}. "
                f"Platform Impact Score: {inc.impact_score:.0f}/100."
            )
        else:
            alert_type = "WEATHER_ADVISORY"
            title = f"WEATHER ADVISORY — {inc.city.upper()}"
            msg = (
                f"Active {inc.event_category.replace('_', ' ')} cluster ({inc.severity.upper()}). "
                f"Impact score: {inc.impact_score:.0f}/100."
            )

        alerts.append(
            AlertItem(
                id=f"alert-{inc.incident_id}",
                alert_type=alert_type,
                severity=inc.severity,
                title=title,
                message=msg,
                city=inc.city,
                state=inc.state,
                impact_score=inc.impact_score,
                timestamp=inc.start_time or now,
            )
        )

    return alerts
