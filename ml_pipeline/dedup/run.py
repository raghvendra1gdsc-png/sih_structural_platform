"""
ml_pipeline/dedup/run.py — Deduplication Runner CLI

Loads existing reports from the PostGIS database, generates candidate pairs,
evaluates multi-modal duplicate decisions, and updates reports.duplicate_of.

Usage:
    python -m ml_pipeline.dedup.run
    python -m ml_pipeline.dedup.run --dry-run
    python -m ml_pipeline.dedup.run --spatial-threshold 2.0 --text-threshold 0.75
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import uuid

from backend.db.models import ReportORM
from backend.db.session import get_session
from ml_pipeline.dedup.config import DedupConfig
from ml_pipeline.dedup.near_duplicate import deduplicate_reports

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ml_pipeline.dedup.run")


def run_deduplication(
    database_url: str | None = None,
    dry_run: bool = False,
    config: DedupConfig | None = None,
) -> int:
    """
    Execute deduplication against database reports and persist duplicate_of links.

    Returns:
        0 on success, non-zero on failure.
    """
    db_url = database_url or os.getenv(
        "DATABASE_URL",
        "postgresql://sih_user:sih_password@localhost:5432/disaster_db",
    )
    cfg = config or DedupConfig()

    logger.info("Connecting to database: %s", db_url.split("@")[-1])
    logger.info(
        "Deduplication config: spatial_threshold=%.1f km, temporal_window=%.1f min, "
        "text_threshold=%.2f, image_hash_threshold=%d",
        cfg.SPATIAL_DISTANCE_THRESHOLD_KM,
        cfg.TEMPORAL_WINDOW_MINUTES,
        cfg.TEXT_SIMILARITY_THRESHOLD,
        cfg.IMAGE_HASH_DISTANCE_THRESHOLD,
    )

    try:
        with get_session(db_url) as session:
            # 1. Load all reports ordered by submission time
            reports = (
                session.query(ReportORM)
                .order_by(ReportORM.submitted_at.asc())
                .all()
            )
            n_reports = len(reports)
            logger.info("Loaded %d reports from database.", n_reports)

            if n_reports == 0:
                print("No reports found in database to deduplicate.")
                return 0

            # 2. Run multi-modal deduplication pipeline
            summary, dup_map = deduplicate_reports(reports, config=cfg)

            # 3. Update duplicate_of in database
            updates_applied = 0
            if not dry_run:
                for report in reports:
                    rid_str = str(report.report_id)
                    new_dup_of = dup_map.get(rid_str)

                    # Update if changed
                    if report.duplicate_of != new_dup_of:
                        report.duplicate_of = new_dup_of
                        updates_applied += 1

                session.commit()
                logger.info(
                    "Database successfully updated: %d reports modified.",
                    updates_applied,
                )
            else:
                logger.info("Dry-run mode: no database writes performed.")

            # 4. Print clean summary
            print("\n" + "=" * 60)
            print("MULTI-MODAL DEDUPLICATION RUNNER SUMMARY")
            print("=" * 60)
            print(f"Reports processed: {summary.reports_processed}")
            print(f"Candidate pairs: {summary.candidate_pairs}")
            print(f"Duplicate pairs: {summary.duplicate_pairs}")
            print(f"Canonical reports: {summary.canonical_reports}")
            print(f"Duplicate reports: {summary.duplicate_reports}")
            if dry_run:
                print("Mode: DRY RUN (no DB changes persisted)")
            else:
                print(f"Database rows updated: {updates_applied}")
            print("=" * 60 + "\n")

            return 0

    except Exception as exc:
        logger.error("Failed to run deduplication: %s", exc, exc_info=True)
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run multi-modal deduplication on reports in the database.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="PostgreSQL connection string. Defaults to DATABASE_URL env var.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute similarity and clustering without persisting to DB.",
    )
    parser.add_argument(
        "--text-threshold",
        type=float,
        default=None,
        help="Cosine similarity threshold for text (default 0.78).",
    )
    parser.add_argument(
        "--image-threshold",
        type=int,
        default=None,
        help="Hamming distance threshold for image hash (default 10).",
    )
    parser.add_argument(
        "--spatial-threshold",
        type=float,
        default=None,
        help="Spatial distance threshold in km (default 1.0).",
    )
    parser.add_argument(
        "--temporal-window",
        type=float,
        default=None,
        help="Temporal window in minutes (default 180.0).",
    )

    args = parser.parse_args()

    custom_kwargs = {}
    if args.text_threshold is not None:
        custom_kwargs["TEXT_SIMILARITY_THRESHOLD"] = args.text_threshold
    if args.image_threshold is not None:
        custom_kwargs["IMAGE_HASH_DISTANCE_THRESHOLD"] = args.image_threshold
    if args.spatial_threshold is not None:
        custom_kwargs["SPATIAL_DISTANCE_THRESHOLD_KM"] = args.spatial_threshold
    if args.temporal_window is not None:
        custom_kwargs["TEMPORAL_WINDOW_MINUTES"] = args.temporal_window

    cfg = DedupConfig(**custom_kwargs) if custom_kwargs else DedupConfig()

    exit_code = run_deduplication(
        database_url=args.database_url,
        dry_run=args.dry_run,
        config=cfg,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
