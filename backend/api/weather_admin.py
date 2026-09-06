"""
backend/api/weather_admin.py
============================
REST API endpoints for admin verification, human-in-the-loop review, and audit trails.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.db.models import VerificationAuditORM
from backend.db.session import get_db
from backend.schemas.weather_api_schemas import (
    MergeReportsPayload,
    VerificationUpdatePayload,
    WeatherReportListResponse,
    WeatherReportResponse,
)
from backend.services.weather_report_service import WeatherReportService

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/reports/pending", response_model=WeatherReportListResponse)
def list_pending_reports(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> WeatherReportListResponse:
    """Retrieve queue of unverified / pending reports needing human verification."""
    service = WeatherReportService(db)
    items, total = service.get_reports(
        verification_status="pending",
        limit=limit,
        offset=offset,
    )
    return WeatherReportListResponse(
        items=[WeatherReportResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch("/reports/{report_id}/verification", response_model=WeatherReportResponse)
@router.patch("/reports/{report_id}/verify", response_model=WeatherReportResponse)
def update_verification_status(
    report_id: uuid.UUID,
    payload: VerificationUpdatePayload,
    db: Session = Depends(get_db),
) -> WeatherReportResponse:
    """Approve, reject, or mark report as needs_review with non-repudiable audit log."""
    valid_statuses = {"verified", "rejected", "pending", "needs_review"}
    if payload.status.lower() not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status '{payload.status}'. Must be one of {valid_statuses}",
        )

    service = WeatherReportService(db)
    try:
        updated = service.update_verification(
            report_id=report_id,
            new_status=payload.status,
            reason=payload.reason,
            reviewer=payload.reviewer,
        )
        return WeatherReportResponse.model_validate(updated)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/reports/{report_id}/merge", response_model=WeatherReportResponse)
def merge_duplicate_report(
    report_id: uuid.UUID,
    payload: MergeReportsPayload,
    db: Session = Depends(get_db),
) -> WeatherReportResponse:
    """Merge a duplicate report into a canonical record and record audit entry."""
    service = WeatherReportService(db)
    try:
        merged = service.merge_report(
            report_id=report_id,
            canonical_id=payload.canonical_report_id,
            reason=payload.reason,
        )
        return WeatherReportResponse.model_validate(merged)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/audits")
def get_audit_trail(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Retrieve full history of administrative verification decisions."""
    stmt = (
        select(VerificationAuditORM)
        .order_by(desc(VerificationAuditORM.created_at))
        .limit(limit)
        .offset(offset)
    )
    rows = list(db.scalars(stmt).all())
    return [
        {
            "id": str(r.id),
            "report_id": str(r.report_id),
            "previous_status": r.previous_status,
            "new_status": r.new_status,
            "action": r.action,
            "reason": r.reason,
            "reviewer": "duty_officer",
            "merged_into": str(r.merged_into) if r.merged_into else None,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
