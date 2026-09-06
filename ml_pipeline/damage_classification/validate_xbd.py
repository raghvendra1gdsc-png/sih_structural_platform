"""
ml_pipeline/damage_classification/validate_xbd.py — xBD Benchmark Validation Harness

Evaluates the zero-shot OpenCLIP structural damage classifier against the labeled
xBD benchmark dataset (>= 50 samples). Computes precision, recall, macro F1, accuracy,
and confusion matrix, outputting a structured validation report.

SCIENTIFIC INTEGRITY RULE:
All metrics must be calculated from real model inference passes over real/sample image
files. Accuracy and F1 values are never mocked or fabricated.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from ingestion.schemas import DamageSeverity, DamageType
from ml_pipeline.damage_classification.clip_classifier import (
    CLIPDamageClassifier,
    get_clip_classifier,
)
from ml_pipeline.damage_classification.prompts import (
    XBD_DAMAGE_TYPE_MAP,
    XBD_SEVERITY_MAP,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("validate_xbd")


def compute_classification_metrics(
    y_true: list[str],
    y_pred: list[str],
    classes: list[str],
) -> dict[str, Any]:
    """
    Computes accuracy, per-class precision, recall, f1, support, and macro averages.
    No scikit-learn dependency required.
    """
    n = len(y_true)
    if n == 0:
        return {
            "accuracy": 0.0,
            "macro_f1": 0.0,
            "macro_precision": 0.0,
            "macro_recall": 0.0,
            "per_class": {},
            "confusion_matrix": {},
        }

    correct = sum(1 for yt, yp in zip(y_true, y_pred) if yt == yp)
    accuracy = correct / n

    # Confusion matrix: cm[true_class][pred_class]
    confusion_matrix: dict[str, dict[str, int]] = {
        c_true: {c_pred: 0 for c_pred in classes}
        for c_true in classes
    }
    for yt, yp in zip(y_true, y_pred):
        if yt in confusion_matrix and yp in confusion_matrix[yt]:
            confusion_matrix[yt][yp] += 1

    per_class: dict[str, dict[str, float]] = {}
    f1s: list[float] = []
    precisions: list[float] = []
    recalls: list[float] = []

    for c in classes:
        tp = confusion_matrix.get(c, {}).get(c, 0)
        fp = sum(confusion_matrix.get(other_c, {}).get(c, 0) for other_c in classes if other_c != c)
        fn = sum(confusion_matrix.get(c, {}).get(other_c, 0) for other_c in classes if other_c != c)
        support = sum(confusion_matrix.get(c, {}).values())

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        per_class[c] = {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1_score": round(f1, 4),
            "support": support,
        }

        if support > 0:
            f1s.append(f1)
            precisions.append(prec)
            recalls.append(rec)

    macro_f1 = sum(f1s) / len(f1s) if f1s else 0.0
    macro_prec = sum(precisions) / len(precisions) if precisions else 0.0
    macro_rec = sum(recalls) / len(recalls) if recalls else 0.0

    return {
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "macro_precision": round(macro_prec, 4),
        "macro_recall": round(macro_rec, 4),
        "total_samples": n,
        "per_class": per_class,
        "confusion_matrix": confusion_matrix,
    }


def run_xbd_validation(
    dataset_dir: str | Path,
    manifest_path: str | Path | None = None,
    output_path: str | Path | None = None,
    device: str | None = None,
    batch_size: int = 16,
) -> dict[str, Any]:
    """
    Run full validation against the xBD benchmark dataset.
    """
    dataset_path = Path(dataset_dir)
    manifest_file = Path(manifest_path) if manifest_path else dataset_path / "xbd_manifest.json"

    if not manifest_file.exists():
        raise FileNotFoundError(f"Manifest file not found: {manifest_file}")

    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest: list[dict] = json.load(f)

    if len(manifest) < 50:
        logger.warning(
            "xBD validation dataset contains %d samples (minimum recommended: 50).",
            len(manifest),
        )

    logger.info("Initializing CLIP classifier on device: %s...", device or "auto")
    classifier = get_clip_classifier(device=device)

    start_time = time.time()
    results: list[dict] = []
    y_true_sev: list[str] = []
    y_pred_sev: list[str] = []
    y_true_type: list[str] = []
    y_pred_type: list[str] = []

    for item in manifest:
        filename = item["filename"]
        img_path = dataset_path / filename
        true_sev = item["damage_severity"]
        true_type = item["damage_type"]
        xbd_label = item.get("xbd_label", "")

        if not img_path.exists():
            logger.error("Image file missing: %s", img_path)
            continue

        pred = classifier.classify_image(img_path, image_id=filename)

        y_true_sev.append(true_sev)
        y_pred_sev.append(pred.predicted_severity.value)

        y_true_type.append(true_type)
        y_pred_type.append(pred.predicted_damage_type.value)

        is_sev_correct = (true_sev == pred.predicted_severity.value)
        is_type_correct = (true_type == pred.predicted_damage_type.value)

        results.append({
            "filename": filename,
            "xbd_label": xbd_label,
            "ground_truth_severity": true_sev,
            "predicted_severity": pred.predicted_severity.value,
            "severity_confidence": pred.severity_confidence,
            "severity_correct": is_sev_correct,
            "ground_truth_damage_type": true_type,
            "predicted_damage_type": pred.predicted_damage_type.value,
            "damage_type_confidence": pred.confidence,
            "damage_type_correct": is_type_correct,
            "source_event": item.get("source_event", ""),
            "description": item.get("description", ""),
        })

    inference_duration = time.time() - start_time

    # Severity metrics
    sev_classes = [DamageSeverity.none.value, DamageSeverity.minor.value, DamageSeverity.severe.value, DamageSeverity.destroyed.value]
    # Also include moderate/unknown if present
    all_sev_classes = sorted(list(set(y_true_sev + y_pred_sev)))
    sev_metrics = compute_classification_metrics(y_true_sev, y_pred_sev, all_sev_classes)

    # Damage type metrics
    all_type_classes = sorted(list(set(y_true_type + y_pred_type)))
    type_metrics = compute_classification_metrics(y_true_type, y_pred_type, all_type_classes)

    # Error analysis: collect misclassified items
    misclassified = [r for r in results if not r["severity_correct"] or not r["damage_type_correct"]]

    report: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model_name": classifier.model_name,
        "pretrained": classifier.pretrained,
        "device": classifier.device,
        "inference_duration_seconds": round(inference_duration, 2),
        "total_samples": len(results),
        "severity_evaluation": sev_metrics,
        "damage_type_evaluation": type_metrics,
        "misclassified_samples": misclassified[:15],
        "total_misclassified_count": len(misclassified),
        "scientific_integrity_disclaimer": (
            "This validation reflects empirical zero-shot OpenCLIP performance on the "
            "standardized xBD benchmark subset. This is an automated visual triage signal "
            "intended to prioritize reports for human verification, not a certified structural "
            "engineering safety determination."
        ),
    }

    if output_path:
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        logger.info("Saved validation report to: %s", out_file)

    return report


def print_summary_table(report: dict[str, Any]) -> None:
    """Prints a clean, formatted ASCII metrics table."""
    sev = report["severity_evaluation"]
    types = report["damage_type_evaluation"]

    print("\n" + "=" * 76)
    print("      ZERO-SHOT OpenCLIP (ViT-B-32) xBD BENCHMARK VALIDATION REPORT")
    print("=" * 76)
    print(f"Model: {report['model_name']} ({report['pretrained']}) | Device: {report['device']}")
    print(f"Total Samples Evaluated: {report['total_samples']} | Runtime: {report['inference_duration_seconds']}s")
    print("-" * 76)
    print("1. DAMAGE SEVERITY EVALUATION (4-Tier xBD Alignment)")
    print(f"   Accuracy: {sev['accuracy']*100:.1f}% | Macro F1: {sev['macro_f1']:.3f} | Macro Precision: {sev['macro_precision']:.3f} | Macro Recall: {sev['macro_recall']:.3f}")
    print("-" * 76)
    print(f"{'Class (Severity)':<18} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10} | {'Support':<8}")
    print("-" * 76)
    for cls_name, m in sev["per_class"].items():
        if m["support"] > 0:
            print(f"{cls_name:<18} | {m['precision']:<10.3f} | {m['recall']:<10.3f} | {m['f1_score']:<10.3f} | {m['support']:<8}")
    print("-" * 76)
    print("Confusion Matrix (Rows=True, Cols=Predicted):")
    cm = sev["confusion_matrix"]
    cols = sorted(list(cm.keys()))
    header = f"{'True \\ Pred':<14} | " + " | ".join(f"{c[:8]:<8}" for c in cols)
    print(header)
    print("-" * len(header))
    for r in cols:
        row_str = f"{r[:14]:<14} | " + " | ".join(f"{cm[r].get(c, 0):<8}" for c in cols)
        print(row_str)

    print("\n" + "-" * 76)
    print("2. STRUCTURAL DAMAGE TYPE EVALUATION")
    print(f"   Accuracy: {types['accuracy']*100:.1f}% | Macro F1: {types['macro_f1']:.3f}")
    print("-" * 76)
    for cls_name, m in types["per_class"].items():
        if m["support"] > 0:
            print(f"{cls_name:<24} | P: {m['precision']:.3f} | R: {m['recall']:.3f} | F1: {m['f1_score']:.3f} | (N={m['support']})")
    print("=" * 76)
    print(f"DISCLAIMER: {report['scientific_integrity_disclaimer']}")
    print("=" * 76 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate OpenCLIP damage classifier against xBD benchmark")
    parser.add_argument(
        "--dataset-dir",
        type=str,
        default="data/sample_dataset/xbd_sample",
        help="Path to xBD benchmark image directory",
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default=None,
        help="Path to xBD manifest file (defaults to <dataset-dir>/xbd_manifest.json)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/sample_dataset/xbd_sample/validation_results.json",
        help="Path to save validation JSON results",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Compute device (mps, cuda, cpu)",
    )
    args = parser.parse_args()

    try:
        report = run_xbd_validation(
            dataset_dir=args.dataset_dir,
            manifest_path=args.manifest,
            output_path=args.output,
            device=args.device,
        )
        print_summary_table(report)
    except Exception as exc:
        logger.error("Validation failed: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
