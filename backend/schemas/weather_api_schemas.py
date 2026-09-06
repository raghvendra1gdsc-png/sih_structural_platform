"""
backend/schemas/weather_api_schemas.py
======================================
FastAPI Pydantic request and response schemas for weather platform endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

from ingestion.weather_schemas import SeverityLevel, WeatherEventCategory, WeatherReportSource


class WeatherReportResponse(BaseModel):
    id: uuid.UUID
    report_id: uuid.UUID
    source: str
    source_report_id: Optional[str] = None
    submitted_at: datetime
    event_time: datetime
    city: str
    state: str
    district: Optional[str] = None
    country: str
    latitude: float
    longitude: float
    text: Optional[str] = None
    media_urls: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    event_category: str
    event_confidence: float
    classification_model: Optional[str] = None
    verification_status: str
    source_trust_score: float
    misinformation_score: float
    trust_reasons: list[str] = Field(default_factory=list)
    duplicate_of: Optional[uuid.UUID] = None
    is_synthetic: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class WeatherReportListResponse(BaseModel):
    items: list[WeatherReportResponse]
    total: int
    limit: int
    offset: int


class WeatherIncidentResponse(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    event_category: str
    latitude: float
    longitude: float
    radius_km: float
    start_time: datetime
    end_time: datetime
    report_count: int
    verified_count: int
    severity: str
    impact_score: float
    confidence: float
    city: str
    state: str
    summary: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class WeatherIncidentListResponse(BaseModel):
    items: list[WeatherIncidentResponse]
    total: int
    limit: int
    offset: int


class VerificationUpdatePayload(BaseModel):
    status: str = Field(..., description="verified, rejected, pending, or needs_review")
    reason: Optional[str] = Field(default=None, description="Reviewer justification notes")
    reviewer: str = Field(default="admin")


class MergeReportsPayload(BaseModel):
    canonical_report_id: uuid.UUID
    reason: Optional[str] = Field(default=None)


class WeatherGPTQueryPayload(BaseModel):
    query: str = Field(..., min_length=2, description="Natural language question about weather")


class WeatherGPTResponse(BaseModel):
    query: str
    city: str
    intent: str
    answer: str
    safety_notice: Optional[str] = None
    reasoning_engine: Optional[str] = None
    structured_context: dict[str, Any] = Field(default_factory=dict)
    evidence: Optional[dict[str, Any]] = None
    citations: list[str] = Field(default_factory=list)
    updated_at: str



class AlertItem(BaseModel):
    id: str
    alert_type: str
    severity: str
    title: str
    message: str
    city: str
    state: str
    impact_score: float
    timestamp: datetime
