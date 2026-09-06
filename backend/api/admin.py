"""
backend/api/admin.py — Admin human verification review and audit endpoints
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.schemas.admin import (
    VerificationActionRequest,
    VerificationActionResponse,
    VerificationAuditListResponse,
)
from backend.schemas.reports import ReportListResponse
from backend.services.admin_service import (
    apply_verification_action,
    get_pending_reports,
    get_verification_audits,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/reports/pending", response_model=ReportListResponse)
def list_pending_reports(
    limit: int = Query(50, ge=1, le=500, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
) -> ReportListResponse:
    """
    Retrieves reports currently in 'pending' status awaiting human inspection.
    """
    return get_pending_reports(session=db, limit=limit, offset=offset)


@router.patch("/reports/{report_id}/verification", response_model=VerificationActionResponse)
def update_report_verification(
    report_id: uuid.UUID,
    request: VerificationActionRequest,
    db: Session = Depends(get_db),
) -> VerificationActionResponse:
    """
    Applies an administrative human verification decision (approve, reject, or merge).
    Records an immutable audit entry in the verification_audit table.
    Never physically deletes reports.
    """
    return apply_verification_action(session=db, report_id=report_id, request=request)


@router.get("/audits", response_model=VerificationAuditListResponse)
def list_verification_audits(
    report_id: Optional[uuid.UUID] = Query(None, description="Filter audit trail for a specific report UUID"),
    limit: int = Query(50, ge=1, le=500, description="Max audit rows to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
) -> VerificationAuditListResponse:
    """
    Query the historical verification audit trail.
    """
    return get_verification_audits(session=db, report_id=report_id, limit=limit, offset=offset)
