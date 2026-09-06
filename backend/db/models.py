"""
backend/db/models.py
=====================
SQLAlchemy 2.x ORM models for the Disaster Structural Intelligence Platform.

Database: PostgreSQL 15 + PostGIS 3.4
ORM:      SQLAlchemy 2.x (mapped_column / DeclarativeBase style)
Geometry: GeoAlchemy2 WKBElement POINT with SRID=4326 (WGS-84)

Tables
------
earthquake_events  — One row per USGS seismic event
reports            — One row per normalised citizen/synthetic report

Design notes
------------
- PostGIS geometry is stored as POINT(lon lat) in SRID 4326.
- All timestamps stored in UTC (TIMESTAMP WITH TIME ZONE).
- Migrations are managed by Alembic; DO NOT use create_all() in production.
- Enum columns use native PostgreSQL ENUM types via SQLAlchemy's Enum().
"""

from __future__ import annotations

import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from ingestion.schemas import (
    DamageSeverity,
    DamageType,
    GeographicScope,
    MagnitudeType,
    ReportSource,
    VerificationStatus,
)
from ingestion.weather_schemas import (
    SeverityLevel,
    WeatherEventCategory,
    WeatherReportSource,
    VerificationStatus as WeatherVerificationStatus,
)


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


# ---------------------------------------------------------------------------
# earthquake_events table
# ---------------------------------------------------------------------------


class EarthquakeEventORM(Base):
    """
    Stores USGS earthquake events with PostGIS spatial indexing.

    The ``event_id`` is the original USGS feature ID (e.g. ``"us7000mkwb"``).
    It is stored verbatim and used as the foreign key target for reports.
    """

    __tablename__ = "earthquake_events"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    # USGS identifiers (preserved verbatim — never alter)
    event_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
        comment="USGS feature ID, e.g. 'us7000mkwb'. Never fabricate.",
    )
    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="usgs",
        comment="Always 'usgs' for USGS-sourced events.",
    )

    # Seismic parameters
    magnitude: Mapped[float] = mapped_column(Float, nullable=False)
    magnitude_type: Mapped[str] = mapped_column(
        Enum(MagnitudeType, name="magnitude_type_enum", create_type=True),
        nullable=False,
        default=MagnitudeType.unknown.value,
    )

    # Geometry (stored as WGS-84 lat/lon; redundant columns kept for easy querying)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    depth_km: Mapped[float] = mapped_column(Float, nullable=False)

    # PostGIS geometry — POINT(longitude latitude) SRID 4326
    geometry: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326),
        nullable=False,
        comment="PostGIS POINT(lon lat) in WGS-84 (SRID 4326).",
    )

    # USGS metadata
    place: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="USGS place string, preserved verbatim.",
    )
    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="UTC datetime of the seismic event.",
    )
    url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Canonical USGS event URL, preserved verbatim.",
    )

    # Geographic classification (appended by ingestion layer)
    geographic_scope: Mapped[str] = mapped_column(
        Enum(GeographicScope, name="geographic_scope_enum", create_type=True),
        nullable=False,
        default=GeographicScope.other.value,
        comment="Tier 1=india, Tier 2=regional, Tier 3=other.",
    )

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationship (back-populated by Report)
    reports: Mapped[list["ReportORM"]] = relationship(
        "ReportORM",
        back_populates="earthquake_event",
        foreign_keys="[ReportORM.earthquake_event_id]",
    )

    def __repr__(self) -> str:
        return (
            f"<EarthquakeEventORM id={self.event_id!r} "
            f"M{self.magnitude} scope={self.geographic_scope}>"
        )


# ---------------------------------------------------------------------------
# reports table
# ---------------------------------------------------------------------------


class ReportORM(Base):
    """
    Stores normalised citizen/synthetic reports with PostGIS spatial indexing.

    ``report_id`` is the UUID from the Pydantic NormalizedReport model.
    ``earthquake_event_id`` is a string FK referencing earthquake_events.event_id.
    """

    __tablename__ = "reports"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    # Canonical report UUID (from Pydantic model)
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        index=True,
    )

    # Provenance
    source: Mapped[str] = mapped_column(
        Enum(ReportSource, name="report_source_enum", create_type=True),
        nullable=False,
    )
    source_record_id: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True,
        comment="Original ID in source system (Reddit post ID, etc.).",
    )

    # Temporal
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="UTC submission timestamp.",
    )

    # Spatial (redundant float columns + PostGIS geometry)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    geometry: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326),
        nullable=False,
        comment="PostGIS POINT(lon lat) in WGS-84 (SRID 4326).",
    )

    # Location / text
    location_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_reference: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Earthquake association
    earthquake_event_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("earthquake_events.event_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ML fields (Phase 3 populates these)
    damage_type: Mapped[str] = mapped_column(
        Enum(DamageType, name="damage_type_enum", create_type=True),
        nullable=False,
        default=DamageType.unknown.value,
    )
    severity: Mapped[str] = mapped_column(
        Enum(DamageSeverity, name="damage_severity_enum", create_type=True),
        nullable=False,
        default=DamageSeverity.unknown.value,
    )
    classification_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="CLIP zero-shot top softmax score [0, 1]. Heuristic score, not probability.",
    )
    classification_model: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="Pretrained CLIP model identifier used for classification.",
    )
    classified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="UTC timestamp when classified by CLIP.",
    )

    # Verification (Phase 6 admin panel)
    verification_status: Mapped[str] = mapped_column(
        Enum(VerificationStatus, name="verification_status_enum", create_type=True),
        nullable=False,
        default=VerificationStatus.pending.value,
        index=True,
    )
    trust_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Trust score [0,1]. None until Phase 4 trust-scoring runs. Never hardcode.",
    )

    # Deduplication (Phase 2)
    # duplicate_of stores the report_id (UUID) of the canonical record.
    # We reference reports.id (PK) via a separate lookup — storing just the UUID
    # avoids a circular FK that PostgreSQL cannot resolve at CREATE TABLE time.
    duplicate_of: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment=(
            "report_id UUID of the canonical report if this is a duplicate. "
            "Populated by Phase 2 dedup. Not a FK to avoid circular constraint issues."
        ),
    )

    # Synthetic flag — must be preserved verbatim through all transformations
    is_synthetic: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment="True = generated by synthetic_report_generator. Never show as real.",
    )

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    earthquake_event: Mapped["EarthquakeEventORM | None"] = relationship(
        "EarthquakeEventORM",
        back_populates="reports",
        foreign_keys=[earthquake_event_id],
    )

    # No ORM relationship for duplicate_of — it is resolved via application logic
    # (Phase 2) to avoid circular FK constraints at DDL time.

    def __repr__(self) -> str:
        return (
            f"<ReportORM report_id={self.report_id!r} "
            f"source={self.source!r} synthetic={self.is_synthetic}>"
        )


# ---------------------------------------------------------------------------
# verification_audit table
# ---------------------------------------------------------------------------


class VerificationAuditORM(Base):
    """
    Audit log for human verification actions on reports (Phase 4 / Phase 6).

    Preserves previous and new verification statuses, action taken,
    reason text, optional canonical merge target, and UTC timestamp.
    """

    __tablename__ = "verification_audit"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reports.report_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="References reports.report_id (canonical report UUID).",
    )
    previous_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="Status prior to verification action.",
    )
    new_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="Status after verification action.",
    )
    action: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="Action performed: approve, reject, or merge.",
    )
    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human reviewer justification / notes.",
    )
    merged_into: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="If action='merge', report_id of canonical report.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<VerificationAuditORM report_id={self.report_id!r} "
            f"action={self.action!r} {self.previous_status}->{self.new_status}>"
        )


# ---------------------------------------------------------------------------
# weather_reports table
# ---------------------------------------------------------------------------


class WeatherReportORM(Base):
    """
    Stores multi-source weather reports with PostGIS spatial indexing.
    Canonical table for the National Weather Big Data Analytics Platform.
    """

    __tablename__ = "weather_reports"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    # Canonical report UUID
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        index=True,
    )

    # Provenance
    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=WeatherReportSource.citizen.value,
        index=True,
    )
    source_report_id: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True,
    )

    # Temporal
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    # Geography
    city: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="Unknown",
        index=True,
    )
    state: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="India",
        index=True,
    )
    district: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    country: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="India",
    )

    # Spatial coordinates & PostGIS geometry
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    geometry: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326),
        nullable=False,
        comment="PostGIS POINT(lon lat) in WGS-84 (SRID 4326).",
    )

    # Content
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_urls: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    image_hash: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    video_reference: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True,
    )
    hashtags: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    # AI Classification
    event_category: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=WeatherEventCategory.other.value,
        index=True,
    )
    event_confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    classification_model: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    # Trust & Verification
    verification_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=WeatherVerificationStatus.pending.value,
        index=True,
    )
    source_trust_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=50.0,
    )
    misinformation_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    trust_reasons: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    # Deduplication
    duplicate_of: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Provenance flag
    is_synthetic: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    processing_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="processed",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<WeatherReportORM report_id={self.report_id!r} "
            f"city={self.city!r} category={self.event_category!r}>"
        )


# ---------------------------------------------------------------------------
# weather_incidents table
# ---------------------------------------------------------------------------


class WeatherIncidentORM(Base):
    """
    Stores spatiotemporally clustered weather incidents and hotspot zones.
    """

    __tablename__ = "weather_incidents"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        index=True,
    )

    event_category: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    # Geospatial Centroid & Bounds
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    centroid: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326),
        nullable=False,
        comment="Incident centroid POINT(lon lat) SRID 4326.",
    )
    radius_km: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=5.0,
    )

    # Temporal bounds
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # Aggregates
    report_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    verified_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    severity: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=SeverityLevel.moderate.value,
        index=True,
    )
    impact_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=50.0,
        index=True,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.8,
    )

    # Location info
    city: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )
    state: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<WeatherIncidentORM incident_id={self.incident_id!r} "
            f"city={self.city!r} impact={self.impact_score}>"
        )


