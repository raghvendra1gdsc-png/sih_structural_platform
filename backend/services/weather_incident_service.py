"""
backend/services/weather_incident_service.py
============================================
Data access and spatiotemporal clustering service for WeatherIncidentORM.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy import delete, desc, func, select
from sqlalchemy.orm import Session

from backend.db.models import WeatherIncidentORM, WeatherReportORM
from ingestion.weather_schemas import NormalizedWeatherReport, WeatherEventCategory
from ml_pipeline.incident_clustering import DEFAULT_CLUSTERING_ENGINE

logger = logging.getLogger(__name__)


class WeatherIncidentService:
    """Service handling clustered weather incidents and hotspot queries."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_incidents(
        self,
        category: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[WeatherIncidentORM], int]:
        """Query weather incidents with filters and pagination."""
        stmt = select(WeatherIncidentORM)

        if category:
            stmt = stmt.where(WeatherIncidentORM.event_category == category.lower())
        if city:
            stmt = stmt.where(func.lower(WeatherIncidentORM.city) == city.lower())
        if state:
            stmt = stmt.where(func.lower(WeatherIncidentORM.state) == state.lower())
        if severity:
            stmt = stmt.where(WeatherIncidentORM.severity == severity.lower())

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar() or 0

        stmt = stmt.order_by(desc(WeatherIncidentORM.impact_score)).limit(limit).offset(offset)
        results = list(self.db.scalars(stmt).all())
        return results, total

    def get_by_incident_id(self, incident_id: uuid.UUID) -> Optional[WeatherIncidentORM]:
        """Fetch single incident by UUID."""
        stmt = select(WeatherIncidentORM).where(WeatherIncidentORM.incident_id == incident_id)
        return self.db.scalars(stmt).first()

    def sync_incidents_from_reports(self) -> int:
        """
        Recompute incidents from all canonical reports and update database.
        """
        stmt = select(WeatherReportORM).where(WeatherReportORM.duplicate_of.is_(None))
        reports_orm = list(self.db.scalars(stmt).all())

        if not reports_orm:
            return 0

        # Convert to NormalizedWeatherReport
        norm_reports: list[NormalizedWeatherReport] = []
        for r in reports_orm:
            try:
                norm_reports.append(
                    NormalizedWeatherReport(
                        report_id=r.report_id,
                        source=r.source,
                        submitted_at=r.submitted_at,
                        event_time=r.event_time,
                        city=r.city,
                        state=r.state,
                        latitude=r.latitude,
                        longitude=r.longitude,
                        text=r.text or "",
                        event_category=WeatherEventCategory(r.event_category),
                        verification_status=r.verification_status,
                    )
                )
            except Exception:
                pass

        incidents_schema = DEFAULT_CLUSTERING_ENGINE.cluster_reports(norm_reports)

        # Truncate existing incidents and insert fresh clusters
        self.db.execute(delete(WeatherIncidentORM))

        for inc in incidents_schema:
            geom_wkt = f"SRID=4326;POINT({inc.centroid_lon} {inc.centroid_lat})"
            orm = WeatherIncidentORM(
                incident_id=inc.incident_id,
                event_category=inc.event_category.value,
                latitude=inc.centroid_lat,
                longitude=inc.centroid_lon,
                centroid=geom_wkt,
                radius_km=inc.radius_km,
                start_time=inc.start_time,
                end_time=inc.end_time,
                report_count=inc.report_count,
                verified_count=inc.verified_count,
                severity=inc.severity.value,
                impact_score=inc.impact_score,
                confidence=inc.confidence,
                city=inc.city,
                state=inc.state,
                summary=inc.summary,
            )
            self.db.add(orm)

        self.db.commit()
        logger.info("Synchronized %d weather incidents from %d canonical reports", len(incidents_schema), len(reports_orm))
        return len(incidents_schema)
