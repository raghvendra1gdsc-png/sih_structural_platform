"""
backend/db/seed.py
===================
End-to-end pipeline seed script.

Workflow
--------
    USGS
      ↓  fetch_usgs_events()
    EarthquakeEvents (classified by geographic scope)
      ↓  generate_synthetic_reports()
    RawReports (is_synthetic=True)
      ↓  normalise_batch()
    NormalizedReports
      ↓  seed_database()
    PostGIS (earthquake_events + reports tables)

Usage
-----
    # Full pipeline (live USGS + PostGIS seed)
    python -m backend.db.seed

    # Offline (use cached USGS events, still seeds PostGIS)
    python -m backend.db.seed --offline

    # Skip DB (dry run — generate + normalise only)
    python -m backend.db.seed --no-db

    # Custom count and seed
    python -m backend.db.seed --count 100 --seed 42
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import uuid
from datetime import timezone

from geoalchemy2 import WKTElement
from sqlalchemy import select

from backend.db.models import Base, EarthquakeEventORM, ReportORM
from backend.db.session import engine_from_url, get_session, verify_postgis
from ingestion.normaliser import normalise_batch
from ingestion.schemas import EarthquakeEvent, NormalizedReport
from ingestion.synthetic_report_generator import generate_synthetic_reports
from ingestion.usgs_ingester import (
    DataSourceUnavailableError,
    fetch_usgs_events,
    select_events_for_demo,
)

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://sih_user:sih_password@localhost:5432/weather_db",
)


# ---------------------------------------------------------------------------
# ORM conversion helpers
# ---------------------------------------------------------------------------


def _event_to_orm(event: EarthquakeEvent) -> EarthquakeEventORM:
    """Convert a Pydantic EarthquakeEvent to the ORM model."""
    point_wkt = f"POINT({event.longitude} {event.latitude})"
    return EarthquakeEventORM(
        id=uuid.uuid4(),
        event_id=event.event_id,
        source=event.source,
        magnitude=event.magnitude,
        magnitude_type=event.magnitude_type.value,
        latitude=event.latitude,
        longitude=event.longitude,
        depth_km=event.depth_km,
        geometry=WKTElement(point_wkt, srid=4326),
        place=event.place,
        event_time=event.event_time.replace(tzinfo=timezone.utc)
        if event.event_time.tzinfo is None
        else event.event_time,
        url=event.url,
        geographic_scope=event.geographic_scope.value,
    )


def _report_to_orm(report: NormalizedReport) -> ReportORM:
    """Convert a Pydantic NormalizedReport to the ORM model."""
    point_wkt = f"POINT({report.longitude} {report.latitude})"
    return ReportORM(
        id=uuid.uuid4(),
        report_id=report.report_id,
        source=report.source.value,
        source_record_id=None,
        submitted_at=report.timestamp,
        latitude=report.latitude,
        longitude=report.longitude,
        geometry=WKTElement(point_wkt, srid=4326),
        location_text=report.location_text,
        text=report.text,
        image_reference=report.image_reference,
        earthquake_event_id=report.earthquake_event_id,
        damage_type=report.damage_type.value,
        severity=report.severity.value,
        verification_status=report.verification_status.value,
        trust_score=report.trust_score,
        duplicate_of=report.duplicate_of,
        is_synthetic=report.is_synthetic,
    )


# ---------------------------------------------------------------------------
# Database seed
# ---------------------------------------------------------------------------


def seed_database(
    events: list[EarthquakeEvent],
    reports: list[NormalizedReport],
    database_url: str = DATABASE_URL,
    skip_existing_events: bool = True,
) -> dict:
    """
    Insert earthquake events and normalised reports into PostGIS.

    Parameters
    ----------
    events : list[EarthquakeEvent]
        Classified USGS events to store.
    reports : list[NormalizedReport]
        Normalised reports to store.
    database_url : str
        PostgreSQL connection string.
    skip_existing_events : bool
        If True (default), events with existing event_id are skipped rather
        than raising a duplicate-key error.

    Returns
    -------
    dict
        Summary with counts of inserted events and reports.
    """
    engine = engine_from_url(database_url)

    # Ensure tables exist (idempotent in development; Alembic owns this in prod)
    Base.metadata.create_all(engine)
    logger.info("Schema ready (create_all complete).")

    events_inserted = 0
    events_skipped = 0
    reports_inserted = 0
    reports_skipped = 0

    with get_session(database_url) as session:
        # ---- Insert earthquake events ----
        for event in events:
            if skip_existing_events:
                existing = session.execute(
                    select(EarthquakeEventORM).where(
                        EarthquakeEventORM.event_id == event.event_id
                    )
                ).scalar_one_or_none()
                if existing:
                    logger.debug("Event %s already exists; skipping.", event.event_id)
                    events_skipped += 1
                    continue

            orm_event = _event_to_orm(event)
            session.add(orm_event)
            events_inserted += 1
            logger.debug("Inserted event %s.", event.event_id)

        # ---- Insert reports ----
        for report in reports:
            if skip_existing_events:
                existing = session.execute(
                    select(ReportORM).where(
                        ReportORM.report_id == report.report_id
                    )
                ).scalar_one_or_none()
                if existing:
                    logger.debug("Report %s already exists; skipping.", report.report_id)
                    reports_skipped += 1
                    continue

            try:
                orm_report = _report_to_orm(report)
                session.add(orm_report)
                reports_inserted += 1
            except Exception as exc:
                logger.warning("Failed to insert report %s: %s", report.report_id, exc)
                reports_skipped += 1

    summary = {
        "events_inserted": events_inserted,
        "events_skipped": events_skipped,
        "reports_inserted": reports_inserted,
        "reports_skipped": reports_skipped,
    }
    logger.info("Seed complete: %s", summary)
    return summary


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


def run_pipeline(
    count: int = 50,
    seed: int | None = 42,
    offline: bool = False,
    skip_db: bool = False,
    database_url: str = DATABASE_URL,
) -> dict:
    """
    Execute the full Phase 1 ingestion pipeline:
    USGS → Events → Synthetic Reports → Normalisation → PostGIS.

    Returns a summary dict with counts at each stage.
    """
    # Step 1: Fetch USGS events
    logger.info("Step 1/4 — Fetching USGS events …")
    try:
        all_events = fetch_usgs_events(offline=offline)
    except DataSourceUnavailableError as exc:
        logger.error("USGS fetch failed: %s", exc)
        return {"error": str(exc)}

    demo_events = select_events_for_demo(all_events, n=3)

    # Step 2: Generate synthetic reports
    logger.info("Step 2/4 — Generating %d synthetic reports …", count)
    raw_reports = generate_synthetic_reports(
        count=count,
        seed=seed,
        offline=offline,
    )

    # Step 3: Normalise
    logger.info("Step 3/4 — Normalising reports …")
    known_ids = {e.event_id for e in all_events}
    normalised, failures = normalise_batch(raw_reports, known_event_ids=known_ids)
    if failures:
        logger.warning("%d reports failed normalisation.", len(failures))

    # Step 4: Seed database
    db_summary: dict = {}
    if not skip_db:
        logger.info("Step 4/4 — Seeding PostGIS …")
        if not verify_postgis(database_url):
            logger.error(
                "PostGIS not available at %s. "
                "Start the database with: docker compose up db -d",
                database_url.split("@")[-1],
            )
            db_summary = {"error": "PostGIS not available"}
        else:
            db_summary = seed_database(demo_events, normalised, database_url)
    else:
        logger.info("Step 4/4 — Skipping database seed (--no-db).")
        db_summary = {"skipped": True}

    return {
        "usgs_events_fetched": len(all_events),
        "demo_events_selected": len(demo_events),
        "raw_reports_generated": len(raw_reports),
        "normalised_ok": len(normalised),
        "normalised_failed": len(failures),
        **db_summary,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="seed",
        description=(
            "Run the Phase 1 end-to-end ingestion pipeline:\n"
            "  USGS → Events → Synthetic Reports → Normalise → PostGIS\n\n"
            "All synthetic records have is_synthetic=True."
        ),
    )
    p.add_argument("--count", type=int, default=50,
                   help="Number of synthetic reports to generate (default: 50).")
    p.add_argument("--seed", type=int, default=42,
                   help="Random seed for deterministic output (default: 42).")
    p.add_argument("--offline", action="store_true",
                   help="Use cached USGS events; skip live fetch.")
    p.add_argument("--no-db", action="store_true",
                   help="Skip database seeding (dry run).")
    p.add_argument("--database-url", default=DATABASE_URL,
                   help="PostgreSQL connection string.")
    p.add_argument("--log-level", default="INFO",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p


def main(argv: list[str] | None = None) -> int:
    p = _build_parser()
    args = p.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    summary = run_pipeline(
        count=args.count,
        seed=args.seed,
        offline=args.offline,
        skip_db=args.no_db,
        database_url=args.database_url,
    )

    print("\n=== Phase 1 Pipeline Summary ===")
    for k, v in summary.items():
        print(f"  {k:<30}: {v}")

    if "error" in summary:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
