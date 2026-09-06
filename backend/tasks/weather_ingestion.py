"""
backend/tasks/weather_ingestion.py
==================================
Asynchronous Celery tasks and helper functions for background ingestion:
- Periodic forecast refresh across major Indian cities
- Unverified news intelligence ingestion via GDELT 2.0
- Social community report ingestion via Reddit (PRAW)
- Spatiotemporal incident reclustering
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from backend.db.session import SessionLocal
from backend.services.weather_incident_service import WeatherIncidentService
from backend.services.weather_report_service import WeatherReportService
from backend.tasks.ingestion_worker import app
from ingestion.aggregator import INDIAN_CITIES, WeatherAggregationService
from ingestion.sources.gdelt import GDELTSource
from ingestion.sources.reddit import RedditSource
from ingestion.weather_schemas import RawWeatherReport

logger = logging.getLogger(__name__)

_aggregator = WeatherAggregationService()
_gdelt_source = GDELTSource()
_reddit_source = RedditSource()


@app.task(name="weather.refresh_forecasts")
def refresh_forecasts_task(cities: Optional[list[str]] = None) -> dict[str, Any]:
    """
    Refresh multi-provider weather forecasts for all or specified Indian cities.
    Pushes results into the unified cache.
    """
    target_cities = cities or list(INDIAN_CITIES.keys())
    success_count = 0
    failed_count = 0
    results_summary = {}

    for city in target_cities:
        try:
            ctx = _aggregator.get_unified_context(city)
            success_count += 1
            results_summary[city] = {
                "temp_c": ctx.temperature_c,
                "providers_ok": ctx.providers_ok,
                "agreement": ctx.agreement_score,
            }
        except Exception as exc:
            failed_count += 1
            logger.warning("[tasks.weather] Failed to refresh %s: %s", city, exc)
            results_summary[city] = {"error": str(exc)}

    return {
        "status": "completed",
        "refreshed_count": success_count,
        "failed_count": failed_count,
        "cities": results_summary,
    }


@app.task(name="weather.ingest_gdelt_news")
def ingest_gdelt_news_task(limit: int = 15) -> dict[str, Any]:
    """
    Poll GDELT 2.0 for recent Indian weather/disaster news,
    convert to RawWeatherReports, and ingest through the validation/dedup pipeline.
    """
    raw_dicts = _gdelt_source.safe_fetch(limit=limit)
    if not raw_dicts:
        return {"status": "ok", "ingested": 0, "message": "No new GDELT records"}

    ingested = 0
    db = SessionLocal()
    try:
        service = WeatherReportService(db)
        for d in raw_dicts:
            try:
                raw_report = RawWeatherReport(**d)
                service.ingest_report(raw_report)
                ingested += 1
            except Exception as e:
                logger.warning("[tasks.weather] GDELT item ingestion failed: %s", e)
    finally:
        db.close()

    return {"status": "completed", "ingested": ingested}


@app.task(name="weather.ingest_reddit_reports")
def ingest_reddit_reports_task(limit: int = 15) -> dict[str, Any]:
    """
    Poll Reddit (if configured) for unverified citizen weather observations,
    convert to RawWeatherReports, and run through the pipeline.
    """
    if not _reddit_source.is_available():
        return {"status": "skipped", "reason": "Reddit API credentials not configured"}

    raw_dicts = _reddit_source.safe_fetch(limit=limit)
    if not raw_dicts:
        return {"status": "ok", "ingested": 0}

    ingested = 0
    db = SessionLocal()
    try:
        service = WeatherReportService(db)
        for d in raw_dicts:
            try:
                raw_report = RawWeatherReport(**d)
                service.ingest_report(raw_report)
                ingested += 1
            except Exception as e:
                logger.warning("[tasks.weather] Reddit item ingestion failed: %s", e)
    finally:
        db.close()

    return {"status": "completed", "ingested": ingested}


@app.task(name="weather.recluster_incidents")
def recluster_incidents_task() -> dict[str, Any]:
    """
    Re-run spatiotemporal clustering across canonical reports to update incidents.
    """
    db = SessionLocal()
    try:
        service = WeatherIncidentService(db)
        created_count = service.sync_incidents_from_reports()
        return {"status": "completed", "incidents_created": created_count}
    except Exception as exc:
        logger.error("[tasks.weather] Incident clustering failed: %s", exc)
        return {"status": "error", "error": str(exc)}
    finally:
        db.close()
