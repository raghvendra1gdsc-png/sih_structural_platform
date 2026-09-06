"""
ingestion/schemas.py
====================
Canonical Pydantic v2 models for the Disaster Structural Intelligence Platform.

All inter-module data exchange must use these models.
Later phases (ML, dedup, FastAPI) may extend these models; do NOT modify existing
fields without a schema-version bump and migration plan.

DATA INTEGRITY RULES (see AGENTS.md §7):
- is_synthetic MUST be True for any record not sourced from a verified external feed.
- All timestamps are UTC.
- Coordinate precision is preserved as-is from the source.
- source + source_record_id must be propagated through all transformations.

PHASE 1 additions:
- GeographicScope enum for USGS event classification (india / regional / other).
- EarthquakeEvent gains geographic_scope field.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ReportSource(str, Enum):
    """Known data sources for raw reports."""

    usgs = "usgs"
    synthetic = "synthetic"
    reddit = "reddit"
    citizen_api = "citizen_api"
    unknown = "unknown"


class VerificationStatus(str, Enum):
    """Human/admin verification lifecycle for a normalized report."""

    pending = "pending"
    verified = "verified"
    rejected = "rejected"
    merged = "merged"


class DamageSeverity(str, Enum):
    """Coarse damage severity classification."""

    unknown = "unknown"
    none = "none"
    minor = "minor"
    moderate = "moderate"
    severe = "severe"
    destroyed = "destroyed"


class DamageType(str, Enum):
    """Structural damage category — aligned with xBD taxonomy where possible."""

    structural_crack = "structural_crack"
    partial_collapse = "partial_collapse"
    complete_collapse = "complete_collapse"
    facade_damage = "facade_damage"
    debris = "debris"
    non_structural_damage = "non_structural_damage"
    unknown = "unknown"


class MagnitudeType(str, Enum):
    """USGS magnitude scale codes (subset most relevant to India region)."""

    ml = "ml"   # Local (Richter)
    mb = "mb"   # Body-wave
    ms = "ms"   # Surface-wave
    mw = "mw"   # Moment magnitude
    mww = "mww"
    mwr = "mwr"
    mwb = "mwb"
    mwc = "mwc"
    md = "md"
    mi = "mi"
    unknown = "unknown"

    @classmethod
    def _missing_(cls, value: object) -> "MagnitudeType":  # type: ignore[override]
        """Accept any unknown magnitude type without crashing."""
        return cls.unknown


class GeographicScope(str, Enum):
    """
    Geographic relevance classification for a USGS earthquake event.

    india    — USGS place string explicitly mentions India, or coordinates fall
               inside the India administrative polygon approximation.
    regional — Event outside India but within a neighbouring country whose
               earthquakes plausibly affect India (Nepal, Pakistan, Afghanistan,
               Bangladesh, Bhutan, Myanmar, Sri Lanka, Tibet/China border belt).
    other    — All remaining events (e.g. deep ocean, distant locations).

    The original USGS metadata is NEVER altered; this field is appended by the
    ingestion layer after classification.
    """

    india = "india"
    regional = "regional"
    other = "other"


# ---------------------------------------------------------------------------
# EarthquakeEvent
# ---------------------------------------------------------------------------


class EarthquakeEvent(BaseModel):
    """
    Represents a single seismic event ingested from the USGS GeoJSON API.

    Field names map directly to USGS GeoJSON properties so that round-tripping
    is lossless.  The ``event_id`` is the USGS feature ``id`` string (e.g.
    ``"us7000mkwb"``).

    Phase 1 added: geographic_scope
    """

    event_id: str = Field(
        ...,
        description="USGS feature ID, e.g. 'us7000mkwb'. Never fabricate this.",
    )
    source: str = Field(
        default="usgs",
        description="Always 'usgs' for records from this model.",
    )
    magnitude: float = Field(
        ...,
        ge=0.0,
        le=10.0,
        description="Earthquake magnitude (Richter scale or equivalent).",
    )
    magnitude_type: MagnitudeType = Field(
        default=MagnitudeType.unknown,
        description="USGS magnitude scale code.",
    )
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    depth_km: float = Field(
        ...,
        ge=0.0,
        description="Hypocentre depth in kilometres.",
    )
    place: str = Field(
        ...,
        description=(
            "Human-readable location description from USGS, "
            "e.g. '12 km NE of Chamoli, India'. "
            "Preserved verbatim — NEVER altered."
        ),
    )
    event_time: datetime = Field(
        ...,
        description="UTC datetime of the seismic event.",
    )
    url: str = Field(
        ...,
        description="Canonical USGS event URL. Preserved verbatim from source.",
    )
    geographic_scope: GeographicScope = Field(
        default=GeographicScope.other,
        description=(
            "Geographic relevance classification appended by the ingestion layer. "
            "Does NOT modify the original USGS place or coordinates."
        ),
    )

    model_config = {"str_strip_whitespace": True}

    @field_validator("event_time", mode="before")
    @classmethod
    def parse_usgs_epoch_ms(cls, v: object) -> datetime:
        """USGS provides epoch time in milliseconds; convert if necessary."""
        if isinstance(v, (int, float)):
            return datetime.utcfromtimestamp(v / 1000.0)
        return v  # type: ignore[return-value]

    @field_validator("magnitude_type", mode="before")
    @classmethod
    def coerce_magnitude_type(cls, v: object) -> MagnitudeType:
        if isinstance(v, str):
            try:
                return MagnitudeType(v.lower())
            except ValueError:
                return MagnitudeType.unknown
        return v  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# RawReport
# ---------------------------------------------------------------------------


class RawReport(BaseModel):
    """
    A single, un-normalised report ingested from any source.

    This is the primary output of the ingestion layer.  All fields from the
    original source that could be useful downstream are preserved here.

    INTEGRITY RULE: is_synthetic MUST be True for synthetic records and MUST
    be False for records ingested from verified external feeds.
    """

    report_id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        description="Internally generated UUID for this report.",
    )
    source: ReportSource = Field(
        ...,
        description="Origin data source.",
    )
    source_record_id: Optional[str] = Field(
        default=None,
        description=(
            "Original record identifier in the source system "
            "(e.g. Reddit post ID, citizen API submission ID). "
            "None if the source does not provide one."
        ),
    )
    submitted_at: datetime = Field(
        ...,
        description="UTC datetime when the report was submitted/scraped.",
    )
    latitude: Optional[float] = Field(
        default=None,
        ge=-90.0,
        le=90.0,
        description="WGS-84 latitude of the reported location.",
    )
    longitude: Optional[float] = Field(
        default=None,
        ge=-180.0,
        le=180.0,
        description="WGS-84 longitude of the reported location.",
    )
    location_text: Optional[str] = Field(
        default=None,
        description="Free-text location description as provided by the reporter.",
    )
    text: Optional[str] = Field(
        default=None,
        description="Full text of the report (tweet, post body, SMS text, etc.).",
    )
    image_reference: Optional[str] = Field(
        default=None,
        description=(
            "Path or URL to the associated image. "
            "May be a local demo path (data/sample_dataset/images/<name>.jpg) "
            "or a remote URL.  CLIP processing is deferred to Phase 3."
        ),
    )
    earthquake_event_id: Optional[str] = Field(
        default=None,
        description=(
            "USGS event_id of the associated earthquake. "
            "Must reference a real USGS event (live or cached)."
        ),
    )
    is_synthetic: bool = Field(
        ...,
        description=(
            "True if and only if this record was generated by the synthetic "
            "report generator.  Must NEVER be False for synthetic records."
        ),
    )

    model_config = {"str_strip_whitespace": True}

    @model_validator(mode="after")
    def validate_location_present(self) -> "RawReport":
        """At least one of (latitude+longitude) or location_text must be provided."""
        has_coords = self.latitude is not None and self.longitude is not None
        has_text = self.location_text is not None and self.location_text.strip() != ""
        if not has_coords and not has_text:
            raise ValueError(
                "A RawReport must have either (latitude, longitude) or location_text."
            )
        return self

    @model_validator(mode="after")
    def synthetic_source_consistency(self) -> "RawReport":
        """Synthetic reports must use ReportSource.synthetic."""
        if self.is_synthetic and self.source != ReportSource.synthetic:
            raise ValueError(
                f"is_synthetic=True but source='{self.source}'. "
                "Synthetic records must use source=ReportSource.synthetic."
            )
        return self


# ---------------------------------------------------------------------------
# NormalizedReport
# ---------------------------------------------------------------------------


class NormalizedReport(BaseModel):
    """
    A fully-processed report after normalisation, deduplication, and ML scoring.

    This model is the primary input to the PostGIS storage layer and the
    FastAPI response models.

    Fields added by later phases (dedup, CLIP, trust scoring) are present here
    with appropriate defaults so that Phase-0/1 generators can produce valid
    records before those phases exist.
    """

    report_id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        description="UUID of this normalized report (may differ from raw report_id after merge).",
    )
    source: ReportSource = Field(..., description="Origin data source.")
    timestamp: datetime = Field(
        ...,
        description="UTC datetime of the original event/submission.",
    )
    latitude: float = Field(
        ...,
        ge=-90.0,
        le=90.0,
        description="Best-known WGS-84 latitude after geocoding / GPS jitter correction.",
    )
    longitude: float = Field(
        ...,
        ge=-180.0,
        le=180.0,
        description="Best-known WGS-84 longitude.",
    )
    location_text: Optional[str] = Field(
        default=None,
        description="Normalised location description.",
    )
    text: Optional[str] = Field(
        default=None,
        description="Cleaned report text.",
    )
    image_reference: Optional[str] = Field(
        default=None,
        description="Path or URL to associated image, if any.",
    )
    earthquake_event_id: Optional[str] = Field(
        default=None,
        description="USGS event_id of the associated earthquake.",
    )

    # --- ML / classification fields (populated by Phase 3) ---
    damage_type: DamageType = Field(
        default=DamageType.unknown,
        description="Structural damage category from CLIP classifier (Phase 3).",
    )
    severity: DamageSeverity = Field(
        default=DamageSeverity.unknown,
        description="Damage severity from CLIP classifier (Phase 3).",
    )

    # --- Verification fields (populated by Phase 4 / 6) ---
    verification_status: VerificationStatus = Field(
        default=VerificationStatus.pending,
        description="Human verification lifecycle status.",
    )
    trust_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Algorithmically computed trust/confidence score [0, 1]. "
            "Must be None until the trust-scoring module has run. "
            "NEVER hardcode or randomly assign this value."
        ),
    )

    # --- Deduplication fields (populated by Phase 2) ---
    duplicate_of: Optional[uuid.UUID] = Field(
        default=None,
        description=(
            "If this report is a duplicate, the UUID of the canonical record "
            "it was merged into.  None if this is the canonical record."
        ),
    )

    # --- Provenance ---
    is_synthetic: bool = Field(
        ...,
        description="True if originated from the synthetic report generator.",
    )

    model_config = {"str_strip_whitespace": True}

    @model_validator(mode="after")
    def synthetic_must_be_labelled(self) -> "NormalizedReport":
        """Synthetic records must always retain their is_synthetic flag."""
        if self.is_synthetic and self.source != ReportSource.synthetic:
            raise ValueError(
                "NormalizedReport: is_synthetic=True but source is not 'synthetic'. "
                "Source attribution must be preserved through normalisation."
            )
        return self


# ---------------------------------------------------------------------------
# Utility: USGSFeature (raw GeoJSON shape, for parsing before conversion)
# ---------------------------------------------------------------------------


class USGSFeatureProperties(BaseModel):
    """Subset of USGS GeoJSON feature properties used by ingestion."""

    mag: float
    magType: Optional[str] = None
    place: str
    time: int  # epoch ms
    url: str
    title: Optional[str] = None

    model_config = {"extra": "allow"}  # USGS adds many more fields; allow them


class USGSFeatureGeometry(BaseModel):
    """USGS GeoJSON geometry (always Point)."""

    type: str = "Point"
    coordinates: list[float]  # [lon, lat, depth_km]

    @field_validator("coordinates")
    @classmethod
    def must_have_three_elements(cls, v: list[float]) -> list[float]:
        if len(v) < 3:  # noqa: PLR2004
            raise ValueError("USGS coordinates must be [longitude, latitude, depth_km]")
        return v


class USGSFeature(BaseModel):
    """Single USGS GeoJSON feature."""

    type: str = "Feature"
    id: str  # USGS event ID, e.g. "us7000mkwb"
    properties: USGSFeatureProperties
    geometry: USGSFeatureGeometry

    def to_earthquake_event(self, geographic_scope: GeographicScope = GeographicScope.other) -> EarthquakeEvent:
        """Convert a raw USGS feature into the canonical EarthquakeEvent model."""
        lon, lat, depth = self.geometry.coordinates
        return EarthquakeEvent(
            event_id=self.id,
            source="usgs",
            magnitude=self.properties.mag,
            magnitude_type=self.properties.magType or "unknown",
            latitude=lat,
            longitude=lon,
            depth_km=depth,
            place=self.properties.place,
            event_time=self.properties.time,  # validator handles epoch-ms conversion
            url=self.properties.url,
            geographic_scope=geographic_scope,
        )


class USGSFeatureCollection(BaseModel):
    """Root USGS GeoJSON FeatureCollection."""

    type: str = "FeatureCollection"
    features: list[USGSFeature]
    metadata: dict = Field(default_factory=dict)

    model_config = {"extra": "allow"}
