"""
demo/seed.py
============
Deterministic Database Seeder for National Weather Big Data Analytics Platform.

Populates PostgreSQL / PostGIS with:
- 500+ realistic weather reports across 12 Indian cities
- AI classification tags and confidence
- Multimodal deduplication relationships (duplicate_of links)
- Auditable trust scores and breakdown reasons
- Clustered WeatherIncidents with Platform Impact Scores
- Admin verification states (verified, pending, needs_review)
- Caches forecast data to disk for offline demo reliability

Usage:
    python -m demo.seed [--count 500] [--seed 42] [--reset]
"""

from __future__ import annotations

import argparse
import logging
import sys
from sqlalchemy import delete

from backend.db.models import VerificationAuditORM, WeatherIncidentORM, WeatherReportORM
from backend.db.session import get_session
from backend.services.weather_incident_service import WeatherIncidentService
from backend.services.weather_report_service import WeatherReportService
from ingestion.synthetic_report_generator import generate_synthetic_reports
from ingestion.weather_provider import INDIAN_CITIES, OpenMeteoWeatherProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("demo.seed")


def seed_database(count: int = 500, seed: int = 42, reset: bool = True) -> None:
    """Execute complete deterministic seeding of the platform."""
    logger.info("==================================================================")
    logger.info("NATIONAL WEATHER BIG DATA ANALYTICS PLATFORM — SEEDING DEMO DATA")
    logger.info("==================================================================")
    logger.info("Generating %d deterministic weather reports (seed=%d)...", count, seed)

    raw_reports = generate_synthetic_reports(count=count, seed=seed)
    logger.info("Generated %d raw synthetic reports across %d Indian cities.", len(raw_reports), len(INDIAN_CITIES))

    # Pre-cache forecasts for all 12 cities
    provider = OpenMeteoWeatherProvider()
    logger.info("Caching meteorological forecasts for Indian cities...")
    for city_name, data in INDIAN_CITIES.items():
        try:
            provider.get_forecast(data["lat"], data["lon"])
        except Exception as e:
            logger.warning("Could not pre-cache forecast for %s: %s", city_name, e)

    with get_session() as session:
        if reset:
            logger.info("Reset requested. Clearing existing demo records for idempotent seeding...")
            session.execute(delete(VerificationAuditORM))
            session.execute(delete(WeatherIncidentORM))
            session.execute(delete(WeatherReportORM))
            session.commit()
            logger.info("Database reset complete.")

        report_service = WeatherReportService(session)
        incident_service = WeatherIncidentService(session)

        logger.info("Ingesting reports through normalization, classification, dedup & trust pipeline...")
        ingested_count = 0
        for i, raw in enumerate(raw_reports):
            try:
                orm = report_service.ingest_report(raw)
                # Mark a calibrated subset of high-confidence reports as verified for realistic operations metrics
                if i % 3 == 0 and orm.source_trust_score >= 70:
                    orm.verification_status = "verified"
                elif i % 11 == 0:
                    orm.verification_status = "needs_review"
                ingested_count += 1
            except Exception as e:
                logger.warning("Failed to ingest report #%d: %s", i, e)

        session.commit()
        logger.info("Successfully ingested and persisted %d weather reports into PostGIS.", ingested_count)

        # Cluster reports into WeatherIncidents
        logger.info("Running geospatial spatiotemporal clustering into weather incidents...")
        incident_count = incident_service.sync_incidents_from_reports()
        logger.info("Created %d clustered weather incidents with platform impact scores.", incident_count)

        logger.info("==================================================================")
        logger.info("SEEDING COMPLETE: Platform is demo-ready and offline-capable!")
        logger.info("==================================================================")


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic Database Seeder for Weather Platform")
    parser.add_argument("--count", type=int, default=500, help="Number of reports to seed (default: 500)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic generation (default: 42)")
    parser.add_argument("--no-reset", dest="reset", action="store_false", help="Do not clear existing reports before seeding")
    args = parser.parse_args()

    seed_database(count=args.count, seed=args.seed, reset=args.reset)


if __name__ == "__main__":
    main()
