"""
backend/api/health.py — System health & PostGIS connectivity probes
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ops"])


@router.get("/healthz")
def health_check(db: Session = Depends(get_db)):
    """
    Liveness and readiness probe for Docker / Kubernetes.
    Directly tests PostgreSQL connection and PostGIS spatial extension.
    """
    try:
        # 1. Verify DB connection
        db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("Health probe database error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "error", "database": "disconnected", "error": str(exc)},
        )

    try:
        # 2. Verify PostGIS extension
        result = db.execute(text("SELECT PostGIS_Version()"))
        postgis_version = result.scalar()
    except Exception as exc:
        logger.error("Health probe PostGIS error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "error",
                "database": "connected",
                "postgis": False,
                "error": str(exc),
            },
        )

    return {
        "status": "ok",
        "database": "connected",
        "postgis": True,
        "postgis_version": postgis_version,
    }
