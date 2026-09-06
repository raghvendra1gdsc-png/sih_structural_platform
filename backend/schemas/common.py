"""
backend/schemas/common.py — Common API models, pagination, and GeoJSON structures
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    limit: int = Field(default=50, ge=1, le=500, description="Number of records to return (1-500)")
    offset: int = Field(default=0, ge=0, description="Offset for pagination")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class PointGeometry(BaseModel):
    type: str = Field(default="Point", literal=True)
    coordinates: list[float] = Field(..., description="[longitude, latitude]")


class GeoJSONFeature(BaseModel):
    type: str = Field(default="Feature", literal=True)
    geometry: PointGeometry
    properties: dict[str, Any]


class GeoJSONFeatureCollection(BaseModel):
    type: str = Field(default="FeatureCollection", literal=True)
    features: list[GeoJSONFeature]
