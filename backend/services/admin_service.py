"""
backend/services/admin_service.py — Admin human verification actions & audit trail service
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.db.models import ReportORM, VerificationAuditORM
from backend.schemas.admin import (
    VerificationActionRequest,
    VerificationActionResponse,
    VerificationAuditItem,
    VerificationAuditListResponse,
)
from backend.schemas.reports import ReportListResponse, ReportResponse


def get_pending_reports(session: Session, limit: int = 50, offset: int = 0) -> ReportListResponse:
    """Retrieve all reports pending human verification."""
    query = session.query(ReportORM).filter(ReportORM.verification_status == "pending")
    total = query.count()
    items = query.order_by(desc(ReportORM.submitted_at)).offset(offset).limit(limit).all()

    return ReportListResponse(
        items=[ReportResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


def apply_verification_action(
    session: Session,
    report_id: uuid.UUID,
    request: VerificationActionRequest,
) -> VerificationActionResponse:
    """
    Applies a human review decision (approve, reject, or merge) to a report.
    Creates an immutable audit log entry in verification_audit table.
    Never deletes original reports.
    """
    report = session.query(ReportORM).filter(ReportORM.report_id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID '{report_id}' not found.",
        )

    previous_status = report.verification_status.value if hasattr(report.verification_status, "value") else str(report.verification_status)
    action = request.action
    merged_into: Optional[uuid.UUID] = None

    if action == "approve":
        new_status = "verified"
        report.verification_status = "verified"

    elif action == "reject":
        new_status = "rejected"
        report.verification_status = "rejected"

    elif action == "merge":
        target_canonical = request.canonical_report_id or request.duplicate_of
        if not target_canonical:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="duplicate_of / canonical_report_id is required when action is 'merge'.",
            )
        if target_canonical == report_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot merge a report into itself.",
            )

        canonical_report = (
            session.query(ReportORM)
            .filter(ReportORM.report_id == target_canonical)
            .first()
        )
        if not canonical_report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target canonical report with ID '{target_canonical}' does not exist.",
            )

        # Set duplicate relationship
        report.duplicate_of = target_canonical
        # Mark as verified duplicate
        new_status = "verified"
        report.verification_status = "verified"
        merged_into = target_canonical

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported verification action: '{action}'.",
        )

    # Record audit entry
    now = datetime.now(timezone.utc)
    audit = VerificationAuditORM(
        id=uuid.uuid4(),
        report_id=report_id,
        previous_status=previous_status,
        new_status=new_status,
        action=action,
        reason=request.reason,
        merged_into=merged_into,
        created_at=now,
    )

    session.add(audit)
    session.commit()
    session.refresh(report)
    session.refresh(audit)

    return VerificationActionResponse(
        report_id=report.report_id,
        previous_status=previous_status,
        new_status=new_status,
        action=action,
        duplicate_of=report.duplicate_of,
        reason=request.reason,
        audit_id=audit.id,
        updated_at=now,
    )


def get_verification_audits(
    session: Session,
    report_id: Optional[uuid.UUID] = None,
    limit: int = 50,
    offset: int = 0,
) -> VerificationAuditListResponse:
    """Query verification audit history."""
    query = session.query(VerificationAuditORM)
    if report_id:
        query = query.filter(VerificationAuditORM.report_id == report_id)

    total = query.count()
    rows = query.order_by(desc(VerificationAuditORM.created_at)).offset(offset).limit(limit).all()

    return VerificationAuditListResponse(
        items=[VerificationAuditItem.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
