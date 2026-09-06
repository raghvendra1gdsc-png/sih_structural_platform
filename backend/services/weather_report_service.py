"""
backend/services/weather_report_service.py
==========================================
Data access and ingestion service for weather reports using SQLAlchemy 2.x and PostGIS.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from geoalchemy2 import Geography
from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID
from sqlalchemy import cast, desc, func, select
from sqlalchemy.orm import Session

from backend.db.models import VerificationAuditORM, WeatherReportORM
from ingestion.weather_normaliser import normalise_weather_report
from ingestion.weather_schemas import (
    NormalizedWeatherReport,
    RawWeatherReport,
    WeatherEventCategory,
    WeatherReportSource,
)
from ml_pipeline.trust_engine import DEFAULT_TRUST_ENGINE
from ml_pipeline.weather_classifier import DEFAULT_WEATHER_CLASSIFIER
from ml_pipeline.weather_dedup import DEFAULT_DEDUP_ENGINE

logger = logging.getLogger(__name__)


class WeatherReportService:
    """Service handling CRUD and spatial queries for WeatherReportORM."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_reports(
        self,
        city: Optional[str] = None,
        state: Optional[str] = None,
        category: Optional[str] = None,
        verification_status: Optional[str] = None,
        source: Optional[str] = None,
        only_canonical: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[WeatherReportORM], int]:
        """Query reports with filtering and total count."""
        stmt = select(WeatherReportORM)

        if city:
            stmt = stmt.where(func.lower(WeatherReportORM.city) == city.lower())
        if state:
            stmt = stmt.where(func.lower(WeatherReportORM.state) == state.lower())
        if category:
            stmt = stmt.where(WeatherReportORM.event_category == category.lower())
        if verification_status:
            stmt = stmt.where(WeatherReportORM.verification_status == verification_status.lower())
        if source:
            stmt = stmt.where(WeatherReportORM.source == source.lower())
        if only_canonical:
            stmt = stmt.where(WeatherReportORM.duplicate_of.is_(None))

        # Total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar() or 0

        # Paginated results ordered by event time descending
        stmt = stmt.order_by(desc(WeatherReportORM.event_time)).limit(limit).offset(offset)
        results = list(self.db.scalars(stmt).all())
        return results, total

    def get_by_report_id(self, report_id: uuid.UUID) -> Optional[WeatherReportORM]:
        """Fetch single report by canonical report_id UUID."""
        stmt = select(WeatherReportORM).where(WeatherReportORM.report_id == report_id)
        return self.db.scalars(stmt).first()

    def get_nearby_reports(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 15.0,
        limit: int = 30,
    ) -> list[WeatherReportORM]:
        """
        Geospatial PostGIS query for reports within radius using ST_DWithin on geography.
        """
        center_geog = cast(ST_SetSRID(ST_MakePoint(longitude, latitude), 4326), Geography)
        report_geog = cast(WeatherReportORM.geometry, Geography)
        stmt = (
            select(WeatherReportORM)
            .where(ST_DWithin(report_geog, center_geog, radius_km * 1000.0))
            .order_by(desc(WeatherReportORM.event_time))
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def ingest_report(
        self,
        raw_payload: RawWeatherReport | dict[str, Any],
    ) -> WeatherReportORM:
        """
        Full ingestion pipeline:
        Normalize -> AI Classify -> Deduplicate check -> Trust Score -> Persist PostGIS
        """
        norm: NormalizedWeatherReport = normalise_weather_report(raw_payload)

        # 1. AI Classification
        cls_result = DEFAULT_WEATHER_CLASSIFIER.classify(
            text=norm.text,
            fallback_category=norm.event_category.value if norm.event_category else None,
        )
        norm.event_category = cls_result.category
        norm.event_confidence = cls_result.confidence
        norm.classification_model = cls_result.model_name

        # 2. Check nearby reports for dedup & corroboration
        nearby = self.get_nearby_reports(norm.latitude, norm.longitude, radius_km=5.0, limit=10)
        
        # Deduplication against nearby canonical reports
        for n in nearby:
            if n.duplicate_of is None and n.report_id != norm.report_id:
                n_norm = NormalizedWeatherReport(
                    report_id=n.report_id,
                    source=n.source,
                    submitted_at=n.submitted_at,
                    event_time=n.event_time,
                    city=n.city,
                    state=n.state,
                    latitude=n.latitude,
                    longitude=n.longitude,
                    text=n.text or "",
                    event_category=WeatherEventCategory(n.event_category),
                )
                decision = DEFAULT_DEDUP_ENGINE.compare_reports(norm, n_norm)
                if decision.is_duplicate:
                    norm.duplicate_of = n.report_id
                    norm.verification_status = "duplicate"
                    break

        # 3. Trust scoring
        trust_eval = DEFAULT_TRUST_ENGINE.evaluate(
            report=norm,
            nearby_reports_count=len(nearby),
        )
        norm.source_trust_score = trust_eval.trust_score
        norm.misinformation_score = trust_eval.misinformation_score
        norm.trust_reasons = trust_eval.reasons

        # 4. Save to PostGIS DB
        geom_wkt = f"SRID=4326;POINT({norm.longitude} {norm.latitude})"
        orm = WeatherReportORM(
            report_id=norm.report_id,
            source=norm.source.value if hasattr(norm.source, "value") else str(norm.source),
            source_report_id=norm.source_report_id,
            submitted_at=norm.submitted_at,
            event_time=norm.event_time,
            city=norm.city,
            state=norm.state,
            district=norm.district,
            country=norm.country,
            latitude=norm.latitude,
            longitude=norm.longitude,
            geometry=geom_wkt,
            text=norm.text,
            media_urls=norm.media_urls,
            image_hash=norm.image_hash,
            video_reference=norm.video_reference,
            hashtags=norm.hashtags,
            event_category=norm.event_category.value,
            event_confidence=norm.event_confidence,
            classification_model=norm.classification_model,
            verification_status=norm.verification_status.value if hasattr(norm.verification_status, "value") else str(norm.verification_status),
            source_trust_score=norm.source_trust_score,
            misinformation_score=norm.misinformation_score,
            trust_reasons=norm.trust_reasons,
            duplicate_of=norm.duplicate_of,
            is_synthetic=norm.is_synthetic,
            processing_status="processed",
        )
        self.db.add(orm)
        self.db.commit()
        self.db.refresh(orm)
        return orm

    def update_verification(
        self,
        report_id: uuid.UUID,
        new_status: str,
        reason: Optional[str] = None,
        reviewer: str = "admin",
    ) -> WeatherReportORM:
        """Update report verification state and create audit record."""
        report = self.get_by_report_id(report_id)
        if not report:
            raise ValueError(f"Report {report_id} not found.")

        prev = report.verification_status
        report.verification_status = new_status.lower()

        audit = VerificationAuditORM(
            report_id=report.report_id,
            previous_status=prev,
            new_status=new_status.lower(),
            action=new_status.lower(),
            reason=reason or f"Action taken by {reviewer}",
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(report)
        return report

    def merge_report(
        self,
        report_id: uuid.UUID,
        canonical_id: uuid.UUID,
        reason: Optional[str] = None,
    ) -> WeatherReportORM:
        """Merge a duplicate report into a canonical record with audit."""
        report = self.get_by_report_id(report_id)
        if not report:
            raise ValueError(f"Report {report_id} not found.")
        canon = self.get_by_report_id(canonical_id)
        if not canon:
            raise ValueError(f"Canonical report {canonical_id} not found.")

        prev = report.verification_status
        report.duplicate_of = canonical_id
        report.verification_status = "merged"

        audit = VerificationAuditORM(
            report_id=report.report_id,
            previous_status=prev,
            new_status="merged",
            action="merge",
            merged_into=canonical_id,
            reason=reason or f"Merged into canonical {canonical_id}",
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(report)
        return report
