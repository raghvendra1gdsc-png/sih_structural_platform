"""
backend/schemas/map.py — Lightweight GeoJSON schemas for map rendering
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

from backend.schemas.common import GeoJSONFeatureCollection, GeoJSONFeature, PointGeometry


class MapReportProperties(BaseModel):
    id: uuid.UUID
    damage_type: str
    severity: str
    verification_status: str
    source: str
    submitted_at: datetime
    is_synthetic: bool
    is_canonical: bool
    duplicate_of: Optional[uuid.UUID] = None
    classification_score: Optional[float] = None
    has_image: bool
