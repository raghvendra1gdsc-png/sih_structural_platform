"""
backend/schemas/reports.py — Report request/response Pydantic models
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from ingestion.schemas import DamageSeverity, DamageType, ReportSource, VerificationStatus


class ReportResponse(BaseModel):
    """Clean, stable public representation of a disaster report."""
    model_config = ConfigDict(from_attributes=True)

    report_id: uuid.UUID
    source: ReportSource
    source_record_id: Optional[str] = None
    submitted_at: datetime
    latitude: float
    longitude: float
    location_text: Optional[str] = None
    text: Optional[str] = None
    image_reference: Optional[str] = None
    earthquake_event_id: Optional[str] = None
    damage_type: DamageType
    severity: DamageSeverity
    classification_score: Optional[float] = None
    classification_model: Optional[str] = None
    classified_at: Optional[datetime] = None
    verification_status: VerificationStatus
    trust_score: Optional[float] = None
    duplicate_of: Optional[uuid.UUID] = None
    is_synthetic: bool
    created_at: datetime


class ReportListResponse(BaseModel):
    items: list[ReportResponse]
    total: int
    limit: int
    offset: int


class NearbyReportItem(ReportResponse):
    distance_km: float = Field(..., description="Spherical geodesic distance in kilometers")


class NearbyReportListResponse(BaseModel):
    center_latitude: float
    center_longitude: float
    radius_km: float
    total: int
    items: list[NearbyReportItem]
