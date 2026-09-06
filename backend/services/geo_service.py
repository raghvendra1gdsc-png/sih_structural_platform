"""
backend/services/geo_service.py — PostGIS spatial query helpers & GeoJSON formatting
"""

from __future__ import annotations

from typing import Any
from geoalchemy2 import Geography
from geoalchemy2.functions import ST_Distance, ST_DWithin, ST_MakePoint, ST_SetSRID
from sqlalchemy import cast, func
from sqlalchemy.orm import Session

from backend.db.models import ReportORM
from backend.schemas.common import GeoJSONFeature, GeoJSONFeatureCollection, PointGeometry


def build_geography_point(longitude: float, latitude: float):
    """
    Constructs a PostGIS geography point in WGS-84 (SRID 4326) for meter-accurate calculations.
    """
    point_geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
    return cast(point_geom, Geography)


def reports_to_geojson_feature_collection(reports: list[ReportORM]) -> GeoJSONFeatureCollection:
    """
    Converts a list of ReportORM objects to a lightweight GeoJSON FeatureCollection
    optimized for fast map rendering in the future dashboard.
    """
    features: list[GeoJSONFeature] = []

    for r in reports:
        feature = GeoJSONFeature(
            type="Feature",
            geometry=PointGeometry(
                type="Point",
                coordinates=[r.longitude, r.latitude],
            ),
            properties={
                "id": str(r.report_id),
                "damage_type": r.damage_type.value if hasattr(r.damage_type, "value") else str(r.damage_type),
                "severity": r.severity.value if hasattr(r.severity, "value") else str(r.severity),
                "verification_status": r.verification_status.value if hasattr(r.verification_status, "value") else str(r.verification_status),
                "source": r.source.value if hasattr(r.source, "value") else str(r.source),
                "submitted_at": r.submitted_at.isoformat(),
                "is_synthetic": r.is_synthetic,
                "is_canonical": r.duplicate_of is None,
                "duplicate_of": str(r.duplicate_of) if r.duplicate_of else None,
                "classification_score": r.classification_score,
                "has_image": bool(r.image_reference and r.image_reference.strip()),
                "location_text": r.location_text,
            },
        )
        features.append(feature)

    return GeoJSONFeatureCollection(type="FeatureCollection", features=features)
