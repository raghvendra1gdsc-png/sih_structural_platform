"""
backend/schemas/admin.py — Admin human verification request/response models
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class VerificationActionRequest(BaseModel):
    action: Literal["approve", "reject", "merge"]
    reason: Optional[str] = Field(None, max_length=1000, description="Optional justification for audit")
    canonical_report_id: Optional[uuid.UUID] = Field(
        None,
        description="Target canonical report UUID when action is 'merge'",
    )
    duplicate_of: Optional[uuid.UUID] = Field(
        None,
        description="Alias for canonical_report_id when action is 'merge'",
    )


class VerificationActionResponse(BaseModel):
    report_id: uuid.UUID
    previous_status: str
    new_status: str
    action: str
    duplicate_of: Optional[uuid.UUID] = None
    reason: Optional[str] = None
    audit_id: uuid.UUID
    updated_at: datetime


class VerificationAuditItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    report_id: uuid.UUID
    previous_status: str
    new_status: str
    action: str
    reason: Optional[str] = None
    merged_into: Optional[uuid.UUID] = None
    created_at: datetime


class VerificationAuditListResponse(BaseModel):
    items: list[VerificationAuditItem]
    total: int
    limit: int = 50
    offset: int = 0
