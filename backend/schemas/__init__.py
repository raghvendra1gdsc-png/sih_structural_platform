"""
backend/schemas — Pydantic schema package for FastAPI REST API
"""

from backend.schemas.admin import (
    VerificationActionRequest,
    VerificationActionResponse,
    VerificationAuditItem,
    VerificationAuditListResponse,
)
from backend.schemas.common import (
    GeoJSONFeature,
    GeoJSONFeatureCollection,
    PaginatedResponse,
    PaginationParams,
    PointGeometry,
)
from backend.schemas.events import (
    EventImpactSummary,
    EventListResponse,
    EventResponse,
)
from backend.schemas.map import MapReportProperties
from backend.schemas.reports import (
    NearbyReportItem,
    NearbyReportListResponse,
    ReportListResponse,
    ReportResponse,
)
from backend.schemas.stats import (
    StatsSummaryResponse,
    TimelineDataPoint,
    TimelineResponse,
)

__all__ = [
    "PaginationParams",
    "PaginatedResponse",
    "PointGeometry",
    "GeoJSONFeature",
    "GeoJSONFeatureCollection",
    "ReportResponse",
    "ReportListResponse",
    "NearbyReportItem",
    "NearbyReportListResponse",
    "MapReportProperties",
    "EventResponse",
    "EventListResponse",
    "EventImpactSummary",
    "StatsSummaryResponse",
    "TimelineDataPoint",
    "TimelineResponse",
    "VerificationActionRequest",
    "VerificationActionResponse",
    "VerificationAuditItem",
    "VerificationAuditListResponse",
]
