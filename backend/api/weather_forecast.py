"""
backend/api/weather_forecast.py
===============================
REST API endpoints providing live meteorological forecasts and multi-provider comparisons
via the unified WeatherAggregationService (Open-Meteo, OpenWeather, Tomorrow.io, WeatherAPI).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, status

from ingestion.aggregator import INDIAN_CITIES, WeatherAggregationService
from ingestion.weather_provider import OpenMeteoWeatherProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/weather", tags=["weather"])

_aggregator = WeatherAggregationService()
_legacy_provider = OpenMeteoWeatherProvider()


def resolve_coords(city: Optional[str], lat: Optional[float], lon: Optional[float]) -> tuple[float, float, str]:
    if lat is not None and lon is not None:
        return lat, lon, city or "Custom Location"
    if city:
        for c_name, data in INDIAN_CITIES.items():
            if c_name.lower() in city.lower() or city.lower() in c_name.lower():
                return data["lat"], data["lon"], c_name
    # Default to Jaipur
    d = INDIAN_CITIES["Jaipur"]
    return d["lat"], d["lon"], "Jaipur"


@router.get("/current")
def get_current_conditions(
    city: Optional[str] = Query(None, description="City name (e.g. Jaipur, Delhi)"),
    lat: Optional[float] = Query(None, description="Latitude"),
    lon: Optional[float] = Query(None, description="Longitude"),
) -> dict[str, Any]:
    """Fetch current meteorological conditions (temperature, rain, wind, condition)."""
    latitude, longitude, city_name = resolve_coords(city, lat, lon)
    try:
        ctx = _aggregator.get_unified_context(city_name, lat=latitude, lon=longitude)
        return {
            "city": ctx.city,
            "latitude": ctx.latitude,
            "longitude": ctx.longitude,
            "temperature": ctx.temperature_c,
            "temperature_c": ctx.temperature_c,
            "apparent_temperature_c": ctx.apparent_temperature_c,
            "precipitation_mm": ctx.precipitation_mm,
            "wind_kmh": ctx.wind_kmh,
            "wind_speed_10m": ctx.wind_kmh,
            "condition": ctx.condition_text,
            "condition_text": ctx.condition_text,
            "humidity_pct": ctx.humidity_pct,
            "pressure_hpa": ctx.pressure_hpa,
            "uv_index": ctx.uv_index,
            "agreement_score": ctx.agreement_score,
            "providers_ok": ctx.providers_ok,
            "source": "multi_provider_aggregator",
        }
    except Exception as exc:
        logger.warning("[weather_api] Aggregator fallback to legacy Open-Meteo: %s", exc)
        conditions = _legacy_provider.get_current_conditions(latitude, longitude)
        conditions["city"] = city_name
        conditions["latitude"] = latitude
        conditions["longitude"] = longitude
        return conditions


@router.get("/forecast")
def get_forecast(
    city: Optional[str] = Query(None, description="City name"),
    lat: Optional[float] = Query(None, description="Latitude"),
    lon: Optional[float] = Query(None, description="Longitude"),
) -> dict[str, Any]:
    """Fetch multi-day and hourly meteorological forecast."""
    latitude, longitude, city_name = resolve_coords(city, lat, lon)
    try:
        ctx = _aggregator.get_unified_context(city_name, lat=latitude, lon=longitude)
        return {
            "city": ctx.city,
            "state": ctx.state,
            "latitude": ctx.latitude,
            "longitude": ctx.longitude,
            "daily": ctx.forecast_days,
            "tomorrow_rain_prob": ctx.tomorrow_rain_prob,
            "tomorrow_temp_max": ctx.tomorrow_temp_max,
            "tomorrow_temp_min": ctx.tomorrow_temp_min,
            "agreement_score": ctx.agreement_score,
            "providers_ok": ctx.providers_ok,
        }
    except Exception as exc:
        logger.warning("[weather_api] Aggregator forecast fallback: %s", exc)
        forecast = _legacy_provider.get_forecast(latitude, longitude)
        resp = forecast.model_dump()
        resp["city"] = city_name
        return resp


@router.get("/current/multi")
def get_multi_provider_current(
    city: Optional[str] = Query("Jaipur", description="City name"),
    lat: Optional[float] = Query(None, description="Latitude"),
    lon: Optional[float] = Query(None, description="Longitude"),
) -> dict[str, Any]:
    """
    Returns full aggregated multi-provider comparison for a location:
    Primary values, agreement score, temperature spread, and individual provider snapshots.
    """
    latitude, longitude, city_name = resolve_coords(city, lat, lon)
    ctx = _aggregator.get_unified_context(city_name, lat=latitude, lon=longitude)
    return ctx.to_dict()


@router.get("/comparison")
def get_provider_comparison(
    city: Optional[str] = Query("Jaipur", description="City name"),
) -> dict[str, Any]:
    """Returns side-by-side comparison across all active meteorological providers."""
    latitude, longitude, city_name = resolve_coords(city, None, None)
    ctx = _aggregator.get_unified_context(city_name, lat=latitude, lon=longitude)
    return {
        "city": ctx.city,
        "state": ctx.state,
        "agreement_score": ctx.agreement_score,
        "temp_spread_c": ctx.temp_spread_c,
        "providers_ok": ctx.providers_ok,
        "providers_failed": ctx.providers_failed,
        "snapshots": [
            {
                "provider": s.provider_name,
                "is_up": s.is_up,
                "is_cached": s.is_cached,
                "fetched_at": s.fetched_at,
                "temperature_c": s.temperature_c,
                "precipitation_mm": s.precipitation_mm,
                "wind_kmh": s.wind_kmh,
                "condition_text": s.condition_text,
                "error": s.error,
            }
            for s in ctx.provider_snapshots
        ],
    }
