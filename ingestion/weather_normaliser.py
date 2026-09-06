"""
ingestion/weather_normaliser.py
===============================
Standardizes and validates raw weather observations.
Ensures coordinate precision, UTC timestamps, provenance preservation,
and initial normalization prior to AI classification and deduplication.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from ingestion.weather_provider import INDIAN_CITIES
from ingestion.weather_schemas import (
    NormalizedWeatherReport,
    RawWeatherReport,
    WeatherEventCategory,
    WeatherReportSource,
)

logger = logging.getLogger(__name__)


def resolve_coordinates(
    latitude: Optional[float],
    longitude: Optional[float],
    city: Optional[str],
    state: Optional[str],
) -> tuple[float, float, str, str]:
    """
    Ensure lat/lon are valid. If missing, look up standard Indian city coordinates.
    """
    if latitude is not None and longitude is not None:
        c_name = city or "Unknown"
        s_name = state or "India"
        return latitude, longitude, c_name, s_name

    # Try matching city in known dictionary
    if city:
        for known_city, info in INDIAN_CITIES.items():
            if known_city.lower() in city.lower():
                return info["lat"], info["lon"], known_city, info["state"]

    # Fallback to Delhi default
    default = INDIAN_CITIES["Delhi"]
    return default["lat"], default["lon"], city or "Delhi", state or "Delhi"


def normalise_weather_report(
    raw: RawWeatherReport | dict[str, Any],
) -> NormalizedWeatherReport:
    """
    Normalise a single RawWeatherReport into a canonical NormalizedWeatherReport.
    """
    if isinstance(raw, dict):
        raw_obj = RawWeatherReport.model_validate(raw)
    else:
        raw_obj = raw

    lat, lon, city, state = resolve_coordinates(
        raw_obj.latitude,
        raw_obj.longitude,
        raw_obj.city,
        raw_obj.state,
    )

    now_utc = datetime.now(timezone.utc)
    sub_at = raw_obj.submitted_at
    if sub_at.tzinfo is None:
        sub_at = sub_at.replace(tzinfo=timezone.utc)

    evt_at = raw_obj.event_time or sub_at
    if evt_at.tzinfo is None:
        evt_at = evt_at.replace(tzinfo=timezone.utc)

    # Initial category inference from raw string if given
    category = WeatherEventCategory.other
    if raw_obj.raw_category:
        try:
            category = WeatherEventCategory(raw_obj.raw_category)
        except Exception:
            category = WeatherEventCategory.other

    cleaned_text = (raw_obj.text or "").strip()

    return NormalizedWeatherReport(
        report_id=raw_obj.report_id,
        source=raw_obj.source,
        source_report_id=raw_obj.source_report_id,
        submitted_at=sub_at,
        event_time=evt_at,
        city=city,
        state=state,
        district=raw_obj.district,
        country=raw_obj.country,
        latitude=lat,
        longitude=lon,
        text=cleaned_text,
        media_urls=raw_obj.media_urls,
        hashtags=raw_obj.hashtags,
        event_category=category,
        event_confidence=0.0,
        is_synthetic=raw_obj.is_synthetic,
        processing_status="normalized",
        created_at=now_utc,
        updated_at=now_utc,
    )


def normalise_batch(
    reports: list[RawWeatherReport | dict[str, Any]],
) -> list[NormalizedWeatherReport]:
    """Normalise a batch of raw weather reports."""
    results: list[NormalizedWeatherReport] = []
    for r in reports:
        try:
            results.append(normalise_weather_report(r))
        except Exception as err:
            logger.warning("Failed to normalise report: %s", err)
    return results
