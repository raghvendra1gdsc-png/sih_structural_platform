"""
backend/services/report_service.py — Report retrieval & PostGIS geospatial query engine
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException, status
from geoalchemy2 import Geography
from geoalchemy2.functions import ST_Distance, ST_DWithin, ST_MakePoint, ST_SetSRID
from sqlalchemy import cast, desc, func, select
from sqlalchemy.orm import Session

from backend.db.models import ReportORM
from backend.schemas.reports import (
    NearbyReportItem,
    NearbyReportListResponse,
    ReportListResponse,
    ReportResponse,
)


def get_reports(
    session: Session,
    event_id: Optional[str] = None,
    verification_status: Optional[str] = None,
    damage_type: Optional[str] = None,
    damage_severity: Optional[str] = None,
    source: Optional[str] = None,
    is_synthetic: Optional[bool] = None,
    is_canonical: Optional[bool] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    radius_km: Optional[float] = None,
    limit: int = 50,
    offset: int = 0,
) -> ReportListResponse:
    """
    Search and filter reports in PostgreSQL/PostGIS with safe pagination.
    """
    query = session.query(ReportORM)

    if event_id:
        query = query.filter(ReportORM.earthquake_event_id == event_id)
    if verification_status:
        query = query.filter(ReportORM.verification_status == verification_status)
    if damage_type:
        query = query.filter(ReportORM.damage_type == damage_type)
    if damage_severity:
        query = query.filter(ReportORM.severity == damage_severity)
    if source:
        query = query.filter(ReportORM.source == source)
    if is_synthetic is not None:
        query = query.filter(ReportORM.is_synthetic == is_synthetic)
    if is_canonical is True:
        query = query.filter(ReportORM.duplicate_of.is_(None))
    elif is_canonical is False:
        query = query.filter(ReportORM.duplicate_of.is_not(None))
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_from must be before or equal to date_to",
        )
    if date_from:
        query = query.filter(ReportORM.submitted_at >= date_from)
    if date_to:
        query = query.filter(ReportORM.submitted_at <= date_to)

    # PostGIS spatial filter if lat/lon/radius_km provided
    if latitude is not None and longitude is not None and radius_km is not None:
        if radius_km <= 0 or radius_km > 1000.0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="radius_km must be greater than 0 and less than or equal to 1000",
            )
        center_geog = cast(ST_SetSRID(ST_MakePoint(longitude, latitude), 4326), Geography)
        report_geog = cast(ReportORM.geometry, Geography)
        query = query.filter(ST_DWithin(report_geog, center_geog, radius_km * 1000.0))

    total = query.count()
    items = query.order_by(desc(ReportORM.submitted_at)).offset(offset).limit(limit).all()

    return ReportListResponse(
        items=[ReportResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_report_by_id(session: Session, report_id: uuid.UUID) -> ReportORM:
    """
    Retrieve a single report by its canonical UUID, or raise 404.
    """
    report = session.query(ReportORM).filter(ReportORM.report_id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID '{report_id}' not found.",
        )
    return report


def get_nearby_reports(
    session: Session,
    latitude: float,
    longitude: float,
    radius_km: float = 50.0,
    limit: int = 50,
    offset: int = 0,
) -> NearbyReportListResponse:
    """
    Geospatial radius search using PostGIS ST_DWithin and ST_Distance.
    Calculates spherical geodesic distance in kilometers and orders by proximity.
    """
    if radius_km <= 0 or radius_km > 1000.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="radius_km must be greater than 0 and less than or equal to 1000.0",
        )
    if not (-90.0 <= latitude <= 90.0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="latitude must be between -90.0 and 90.0",
        )
    if not (-180.0 <= longitude <= 180.0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="longitude must be between -180.0 and 180.0",
        )

    center_geog = cast(ST_SetSRID(ST_MakePoint(longitude, latitude), 4326), Geography)
    report_geog = cast(ReportORM.geometry, Geography)

    # Compute distance in kilometers: ST_Distance returns meters on geography
    distance_km_expr = (ST_Distance(report_geog, center_geog) / 1000.0).label("distance_km")

    spatial_filter = ST_DWithin(report_geog, center_geog, radius_km * 1000.0)
    total = session.query(func.count(ReportORM.id)).filter(spatial_filter).scalar() or 0

    rows = (
        session.query(ReportORM, distance_km_expr)
        .filter(spatial_filter)
        .order_by(distance_km_expr.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items: list[NearbyReportItem] = []
    for report_orm, dist_km in rows:
        resp_dict = ReportResponse.model_validate(report_orm).model_dump()
        resp_dict["distance_km"] = round(float(dist_km), 3)
        items.append(NearbyReportItem(**resp_dict))

    return NearbyReportListResponse(
        center_latitude=latitude,
        center_longitude=longitude,
        radius_km=radius_km,
        total=total,
        items=items,
    )
