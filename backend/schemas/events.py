"""
backend/schemas/events.py — Earthquake event request/response Pydantic models
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

from ingestion.schemas import GeographicScope, MagnitudeType


class EventResponse(BaseModel):
    """Public representation of a USGS seismic event."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_id: str
    source: str
    magnitude: float
    magnitude_type: MagnitudeType
    latitude: float
    longitude: float
    depth_km: float
    place: str
    event_time: datetime
    url: str
    geographic_scope: GeographicScope
    created_at: datetime


class EventListResponse(BaseModel):
    items: list[EventResponse]
    total: int
    limit: int
    offset: int


class EventImpactSummary(BaseModel):
    event_id: str
    place: str
    magnitude: float
    event_time: datetime
    geographic_scope: str
    total_reports: int
    canonical_reports: int
    duplicate_reports: int
    verified_reports: int
    pending_reports: int
    rejected_reports: int
    severity_distribution: dict[str, int]
    damage_type_distribution: dict[str, int]
    source_distribution: dict[str, int]
    bounding_box: Optional[dict[str, float]] = Field(
        None,
        description="Bounding box of associated reports: min_lat, max_lat, min_lon, max_lon"
    )
