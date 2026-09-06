"""
backend/services — Service layer for database queries, spatial search, and admin actions
"""

from backend.services.admin_service import (
    apply_verification_action,
    get_pending_reports,
    get_verification_audits,
)
from backend.services.event_service import (
    get_event_by_id,
    get_event_summary,
    get_events,
)
from backend.services.geo_service import (
    build_geography_point,
    reports_to_geojson_feature_collection,
)
from backend.services.report_service import (
    get_nearby_reports,
    get_report_by_id,
    get_reports,
)
from backend.services.stats_service import (
    get_platform_stats_summary,
    get_reports_timeline,
)

__all__ = [
    "build_geography_point",
    "reports_to_geojson_feature_collection",
    "get_reports",
    "get_report_by_id",
    "get_nearby_reports",
    "get_events",
    "get_event_by_id",
    "get_event_summary",
    "get_platform_stats_summary",
    "get_reports_timeline",
    "get_pending_reports",
    "apply_verification_action",
    "get_verification_audits",
]
