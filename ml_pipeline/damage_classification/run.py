"""
ml_pipeline/damage_classification/run.py — Canonical Report Classification Runner

Executes zero-shot CLIP damage classification against canonical reports stored
in the PostGIS database. Populates damage_type, severity, and classification audit fields.

Usage:
    python -m ml_pipeline.damage_classification.run
    python -m ml_pipeline.damage_classification.run --dry-run
    python -m ml_pipeline.damage_classification.run --device cpu
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections import Counter
from datetime import datetime, timezone

from backend.db.models import ReportORM
from backend.db.session import get_session
from ml_pipeline.damage_classification.clip_classifier import CLIPDamageClassifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ml_pipeline.damage_classification.run")


def run_classification(
    database_url: str | None = None,
    dry_run: bool = False,
    device: str | None = None,
    model_name: str = "ViT-B-32",
    pretrained: str = "laion2b_s34b_b79k",
) -> int:
    """
    Run CLIP damage classification on canonical reports with images.
    """
    db_url = database_url or os.getenv(
        "DATABASE_URL",
        "postgresql://sih_user:sih_password@localhost:5432/disaster_db",
    )

    logger.info("Connecting to database: %s", db_url.split("@")[-1])

    try:
        classifier = CLIPDamageClassifier(
            model_name=model_name,
            pretrained=pretrained,
            device=device,
        )
    except Exception as exc:
        logger.error("Failed to initialize CLIPDamageClassifier: %s", exc, exc_info=True)
        return 1

    try:
        with get_session(db_url) as session:
            # 1. Load canonical reports (duplicate_of is NULL)
            canonical_reports = (
                session.query(ReportORM)
                .filter(ReportORM.duplicate_of.is_(None))
                .order_by(ReportORM.submitted_at.asc())
                .all()
            )

            total_canonical = len(canonical_reports)
            logger.info("Found %d canonical reports in database.", total_canonical)

            if total_canonical == 0:
                print("No canonical reports found in database to classify.")
                return 0

            # 2. Filter for reports with images
            reports_with_images = [
                r for r in canonical_reports if r.image_reference and r.image_reference.strip()
            ]
            n_images = len(reports_with_images)
            logger.info(
                "%d of %d canonical reports have image references.",
                n_images,
                total_canonical,
            )

            success_count = 0
            failed_count = 0
            damage_type_counts: Counter[str] = Counter()
            severity_counts: Counter[str] = Counter()

            # 3. Classify reports with images
            for report in reports_with_images:
                res = classifier.classify_image(
                    report.image_reference,
                    image_id=str(report.report_id),
                )

                if res.is_success:
                    success_count += 1
                    damage_type_counts[res.predicted_damage_type.value] += 1
                    severity_counts[res.predicted_severity.value] += 1

                    if not dry_run:
                        report.damage_type = res.predicted_damage_type
                        report.severity = res.predicted_severity
                        report.classification_score = res.confidence
                        report.classification_model = res.model_name
                        report.classified_at = res.timestamp
                else:
                    failed_count += 1
                    logger.warning(
                        "Failed to classify report %s (image %s): %s",
                        report.report_id,
                        report.image_reference,
                        res.error,
                    )

            if not dry_run and success_count > 0:
                session.commit()
                logger.info("Committed %d classifications to database.", success_count)
            elif dry_run:
                logger.info("Dry-run mode: no database changes committed.")

            # 4. Print clean, measured summary
            print("\n" + "=" * 60)
            print("CLIP ZERO-SHOT DAMAGE CLASSIFICATION SUMMARY")
            print("=" * 60)
            print(f"Reports processed: {total_canonical}")
            print(f"Images available: {n_images}")
            print(f"Successfully classified: {success_count}")
            print(f"Failed images: {failed_count}")
            print(f"Model used: {classifier.model_name} ({classifier.pretrained})")
            print(f"Device: {classifier.device}")

            if damage_type_counts:
                print("\nDamage types:")
                for dt, count in damage_type_counts.most_common():
                    print(f"  {dt}: {count}")

            if severity_counts:
                print("\nDamage severities:")
                for sev, count in severity_counts.most_common():
                    print(f"  {sev}: {count}")

            if dry_run:
                print("\nMode: DRY RUN (no DB changes persisted)")
            else:
                print(f"\nDatabase rows updated: {success_count}")
            print("=" * 60 + "\n")

            return 0

    except Exception as exc:
        logger.error("Error during report classification: %s", exc, exc_info=True)
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run CLIP zero-shot damage classification on canonical reports in DB.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="PostgreSQL connection string. Defaults to DATABASE_URL env var.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute inference without persisting to DB.",
    )
    parser.add_argument(
        "--device",
        choices=["cpu", "mps", "cuda"],
        default=None,
        help="Compute device override.",
    )
    parser.add_argument(
        "--model-name",
        default="ViT-B-32",
        help="OpenCLIP model name (default ViT-B-32).",
    )
    parser.add_argument(
        "--pretrained",
        default="laion2b_s34b_b79k",
        help="Pretrained weights tag (default laion2b_s34b_b79k).",
    )

    args = parser.parse_args()

    exit_code = run_classification(
        database_url=args.database_url,
        dry_run=args.dry_run,
        device=args.device,
        model_name=args.model_name,
        pretrained=args.pretrained,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
