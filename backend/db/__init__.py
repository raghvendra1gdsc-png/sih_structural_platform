"""
backend/db/
===========
Database layer: SQLAlchemy models, session management, Alembic migrations.

Phase 1: Models and engine factory.
Phase 4: Session middleware and repository classes.
"""

from backend.db.models import (
    Base,
    EarthquakeEventORM,
    ReportORM,
    VerificationAuditORM,
    WeatherIncidentORM,
    WeatherReportORM,
)
from backend.db.session import engine_from_url, get_db, get_engine, get_session

__all__ = [
    "Base",
    "EarthquakeEventORM",
    "ReportORM",
    "VerificationAuditORM",
    "WeatherIncidentORM",
    "WeatherReportORM",
    "engine_from_url",
    "get_db",
    "get_engine",
    "get_session",
]

