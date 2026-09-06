"""
ingestion/weather_schemas.py
============================
Canonical Pydantic v2 schemas for the National Weather Big Data Analytics Platform.

Covers:
- Standardized weather event categories (rainfall, thunderstorm, flooding, etc.)
- Verification statuses and severity levels
- Raw and Normalized weather reports
- Weather incident schemas
- Open-Meteo API response representations
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Core Weather Enumerations
# ---------------------------------------------------------------------------


class WeatherEventCategory(str, Enum):
    """Extensible weather event categories for India domain."""

    rainfall = "rainfall"
    thunderstorm = "thunderstorm"
    flooding = "flooding"
    heatwave = "heatwave"
    fog = "fog"
    dust_storm = "dust_storm"
    strong_winds = "strong_winds"
    cyclone = "cyclone"
    hailstorm = "hailstorm"
    lightning = "lightning"
    cold_wave = "cold_wave"
    landslide = "landslide"
    other = "other"

    @classmethod
    def _missing_(cls, value: object) -> "WeatherEventCategory":
        """Gracefully handle variant casing or unknown categories."""
        if isinstance(value, str):
            val_norm = value.lower().replace("-", "_").replace(" ", "_")
            for member in cls:
                if member.value == val_norm:
                    return member
            # Also try stripped-separator match (e.g. "rain_fall" -> "rainfall")
            val_stripped = val_norm.replace("_", "")
            for member in cls:
                if member.value.replace("_", "") == val_stripped:
                    return member
        return cls.other


class WeatherReportSource(str, Enum):
    """Known origin sources for weather observations."""

    weather_api = "weather_api"
    citizen = "citizen"
    community_feed = "community_feed"
    public_dataset = "public_dataset"
    synthetic = "synthetic"
    other = "other"


class VerificationStatus(str, Enum):
    """Verification lifecycle of a weather report."""

    pending = "pending"
    verified = "verified"
    rejected = "rejected"
    duplicate = "duplicate"
    needs_review = "needs_review"
    merged = "merged"


class SeverityLevel(str, Enum):
    """Platform-derived impact severity categories."""

    low = "low"
    moderate = "moderate"
    high = "high"
    severe = "severe"


# ---------------------------------------------------------------------------
# Raw Ingestion Schema
# ---------------------------------------------------------------------------


class RawWeatherReport(BaseModel):
    """
    Un-normalized weather observation ingested from any stream.
    Preserves raw source metadata and textual/visual evidence.
    """

    report_id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        description="Internal UUID for tracking the raw submission.",
    )
    source: WeatherReportSource = Field(
        default=WeatherReportSource.citizen,
        description="Origin source of the report.",
    )
    source_report_id: Optional[str] = Field(
        default=None,
        description="Upstream ID from external API, RSS feed, or social payload.",
    )
    submitted_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp of ingestion.",
    )
    event_time: Optional[datetime] = Field(
        default=None,
        description="Observed time of the weather event (UTC). Defaults to submitted_at.",
    )
    city: Optional[str] = Field(default=None, description="Reported city name.")
    state: Optional[str] = Field(default=None, description="Reported Indian state.")
    district: Optional[str] = Field(default=None, description="Reported district.")
    country: str = Field(default="India", description="Country name.")
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    text: Optional[str] = Field(
        default=None,
        description="Eyewitness text, tweet content, or automated report snippet.",
    )
    media_urls: list[str] = Field(
        default_factory=list,
        description="URLs or local asset references for photos/videos.",
    )
    hashtags: list[str] = Field(
        default_factory=list,
        description="Social tags or descriptive labels.",
    )
    raw_category: Optional[str] = Field(
        default=None,
        description="Category asserted by reporter before AI classification.",
    )
    is_synthetic: bool = Field(
        default=False,
        description="Must be True for deterministically generated demo data.",
    )

    model_config = {"str_strip_whitespace": True}

    @model_validator(mode="after")
    def validate_geolocation_present(self) -> "RawWeatherReport":
        has_coords = self.latitude is not None and self.longitude is not None
        has_text_loc = bool(self.city or self.district or self.state)
        if not has_coords and not has_text_loc:
            raise ValueError("Report must contain either coordinates or a recognizable location (city/state).")
        return self


# ---------------------------------------------------------------------------
# Normalized Weather Report Schema
# ---------------------------------------------------------------------------


class NormalizedWeatherReport(BaseModel):
    """
    Standardized, geocoded, classified, and deduplicated weather report
    ready for PostGIS persistence and real-time dashboard consumption.
    """

    report_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    source: WeatherReportSource
    source_report_id: Optional[str] = None
    submitted_at: datetime
    event_time: datetime

    city: str = Field(default="Unknown")
    state: str = Field(default="India")
    district: Optional[str] = None
    country: str = Field(default="India")

    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)

    text: str = Field(default="")
    media_urls: list[str] = Field(default_factory=list)
    image_hash: Optional[str] = None
    video_reference: Optional[str] = None
    hashtags: list[str] = Field(default_factory=list)

    event_category: WeatherEventCategory = Field(default=WeatherEventCategory.other)
    event_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    classification_model: Optional[str] = None

    verification_status: VerificationStatus = Field(default=VerificationStatus.pending)
    source_trust_score: float = Field(default=50.0, ge=0.0, le=100.0)
    misinformation_score: float = Field(default=0.0, ge=0.0, le=100.0)
    trust_reasons: list[str] = Field(default_factory=list)

    duplicate_of: Optional[uuid.UUID] = Field(
        default=None,
        description="Canonical report_id UUID if marked as duplicate.",
    )
    is_synthetic: bool = Field(default=False)
    processing_status: str = Field(default="processed")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"str_strip_whitespace": True}


# ---------------------------------------------------------------------------
# Clustered Weather Incident Schema
# ---------------------------------------------------------------------------


class WeatherIncidentSchema(BaseModel):
    """
    Represents a clustered multi-report geospatial weather incident/hotspot.
    """

    incident_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_category: WeatherEventCategory
    centroid_lat: float = Field(..., ge=-90.0, le=90.0)
    centroid_lon: float = Field(..., ge=-180.0, le=180.0)
    start_time: datetime
    end_time: datetime
    report_count: int = Field(default=1, ge=1)
    verified_count: int = Field(default=0, ge=0)
    severity: SeverityLevel = Field(default=SeverityLevel.moderate)
    impact_score: float = Field(default=50.0, ge=0.0, le=100.0)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    city: str
    state: str
    radius_km: float = Field(default=5.0, ge=0.1)
    summary: Optional[str] = None


# ---------------------------------------------------------------------------
# Open-Meteo API Schemas
# ---------------------------------------------------------------------------


class OpenMeteoCurrent(BaseModel):
    time: str
    interval: Optional[int] = None
    temperature_2m: Optional[float] = None
    relative_humidity_2m: Optional[float] = None
    apparent_temperature: Optional[float] = None
    precipitation: Optional[float] = None
    rain: Optional[float] = None
    weather_code: Optional[int] = None
    wind_speed_10m: Optional[float] = None
    wind_direction_10m: Optional[float] = None
    wind_gusts_10m: Optional[float] = None


class OpenMeteoHourly(BaseModel):
    time: list[str] = Field(default_factory=list)
    temperature_2m: list[float] = Field(default_factory=list)
    precipitation_probability: list[int] = Field(default_factory=list)
    precipitation: list[float] = Field(default_factory=list)
    weather_code: list[int] = Field(default_factory=list)
    wind_speed_10m: list[float] = Field(default_factory=list)
    wind_gusts_10m: list[float] = Field(default_factory=list)


class OpenMeteoDaily(BaseModel):
    time: list[str] = Field(default_factory=list)
    weather_code: list[int] = Field(default_factory=list)
    temperature_2m_max: list[float] = Field(default_factory=list)
    temperature_2m_min: list[float] = Field(default_factory=list)
    precipitation_sum: list[float] = Field(default_factory=list)
    precipitation_probability_max: list[int] = Field(default_factory=list)
    wind_speed_10m_max: list[float] = Field(default_factory=list)
    wind_gusts_10m_max: list[float] = Field(default_factory=list)


class OpenMeteoResponse(BaseModel):
    latitude: float
    longitude: float
    generationtime_ms: Optional[float] = None
    utc_offset_seconds: Optional[int] = None
    timezone: Optional[str] = None
    timezone_abbreviation: Optional[str] = None
    elevation: Optional[float] = None
    current: Optional[OpenMeteoCurrent] = None
    hourly: Optional[OpenMeteoHourly] = None
    daily: Optional[OpenMeteoDaily] = None
