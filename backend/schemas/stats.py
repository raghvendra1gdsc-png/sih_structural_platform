"""
backend/schemas/stats.py — Aggregated statistics & time-series Pydantic models
"""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class StatsSummaryResponse(BaseModel):
    """Overall platform summary statistics derived strictly from live DB queries."""
    total_reports: int
    canonical_reports: int
    duplicate_reports: int
    verified_reports: int
    pending_reports: int
    rejected_reports: int
    reports_with_images: int
    classified_reports: int
    synthetic_reports: int
    real_reports: int
    damage_type_counts: dict[str, int]
    severity_counts: dict[str, int]
    source_counts: dict[str, int]
    event_counts: dict[str, int]


class TimelineDataPoint(BaseModel):
    date: str
    count: int


class TimelineResponse(BaseModel):
    interval: Literal["hour", "day", "week"]
    total_reports: int
    data: list[TimelineDataPoint]
