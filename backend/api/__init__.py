"""
backend/api — FastAPI router package for National Weather Big Data Platform
"""

from backend.api.health import router as health_router
from backend.api.weather_reports import router as weather_reports_router
from backend.api.weather_incidents import router as weather_incidents_router
from backend.api.weather_map import router as weather_map_router
from backend.api.weather_stats import router as weather_stats_router
from backend.api.weather_forecast import router as weather_forecast_router
from backend.api.weather_admin import router as weather_admin_router
from backend.api.weather_gpt import router as weather_gpt_router
from backend.api.alerts import router as alerts_router
from backend.api.provider_health import router as provider_health_router
from backend.api.system_health import router as system_health_router

__all__ = [
    "health_router",
    "weather_reports_router",
    "weather_incidents_router",
    "weather_map_router",
    "weather_stats_router",
    "weather_forecast_router",
    "weather_admin_router",
    "weather_gpt_router",
    "alerts_router",
    "provider_health_router",
    "system_health_router",
]

