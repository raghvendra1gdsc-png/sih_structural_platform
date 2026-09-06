"""
tests/test_clip_classifier.py — Unit Tests for CLIP Zero-Shot Damage Classifier

Tests:
- Prompt template validity and enum coverage
- Taxonomy mapping (xBD to Platform)
- Classifier singleton caching and device handling
- In-memory image classification
- Grayscale image conversion
- Corrupt and missing image resilience
- Batch classification
- Validation metric calculations (precision, recall, F1, confusion matrix)
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from ingestion.schemas import DamageSeverity, DamageType
from ml_pipeline.damage_classification.clip_classifier import (
    CLIPDamageClassifier,
    get_clip_classifier,
    get_default_device,
)
from ml_pipeline.damage_classification.prompts import (
    DAMAGE_SEVERITY_PROMPTS,
    DAMAGE_TYPE_PROMPTS,
    XBD_DAMAGE_TYPE_MAP,
    XBD_SEVERITY_MAP,
)
from ml_pipeline.damage_classification.schemas import DamageClassificationResult
from ml_pipeline.damage_classification.validate_xbd import compute_classification_metrics


# ---------------------------------------------------------------------------
# 1. Prompt and Taxonomy Integrity Tests
# ---------------------------------------------------------------------------

def test_damage_type_prompts_coverage():
    """Ensure all DamageType enum members have non-empty prompt template lists."""
    for dt in DamageType:
        assert dt in DAMAGE_TYPE_PROMPTS, f"Missing prompts for DamageType.{dt.name}"
        prompts = DAMAGE_TYPE_PROMPTS[dt]
        assert isinstance(prompts, list) and len(prompts) > 0
        for p in prompts:
            assert isinstance(p, str) and len(p.strip()) > 10


def test_damage_severity_prompts_coverage():
    """Ensure all DamageSeverity enum members have non-empty prompt template lists."""
    for sev in DamageSeverity:
        assert sev in DAMAGE_SEVERITY_PROMPTS, f"Missing prompts for DamageSeverity.{sev.name}"
        prompts = DAMAGE_SEVERITY_PROMPTS[sev]
        assert isinstance(prompts, list) and len(prompts) > 0
        for p in prompts:
            assert isinstance(p, str) and len(p.strip()) > 10


def test_taxonomy_mapping():
    """Verify xBD 4-tier mappings map to valid platform enums."""
    for label in ["no-damage", "minor-damage", "major-damage", "destroyed"]:
        assert label in XBD_SEVERITY_MAP
        assert isinstance(XBD_SEVERITY_MAP[label], DamageSeverity)
        assert label in XBD_DAMAGE_TYPE_MAP
        assert isinstance(XBD_DAMAGE_TYPE_MAP[label], DamageType)


# ---------------------------------------------------------------------------
# 2. Classifier Initialization and Image Handling Tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def classifier() -> CLIPDamageClassifier:
    """Shared classifier fixture to avoid repeated model loading during test suite."""
    return get_clip_classifier()


def test_classifier_device_and_caching(classifier: CLIPDamageClassifier):
    """Verify device string and singleton caching."""
    device = get_default_device()
    assert device in ("mps", "cuda", "cpu")
    assert classifier.device in ("mps", "cuda", "cpu")

    # Second call returns cached model
    c2 = get_clip_classifier()
    assert c2.model is classifier.model


def test_classify_valid_pil_image(classifier: CLIPDamageClassifier):
    """Test classification on a synthesized PIL image."""
    img = Image.new("RGB", (224, 224), color=(200, 200, 200))
    draw = ImageDraw.Draw(img)
    draw.rectangle([40, 60, 180, 200], fill=(160, 150, 140), outline=(30, 30, 30), width=2)

    res = classifier.classify_image(img, image_id="test_pil_001")
    assert isinstance(res, DamageClassificationResult)
    assert res.is_success is True
    assert res.image_id == "test_pil_001"
    assert isinstance(res.predicted_damage_type, DamageType)
    assert isinstance(res.predicted_severity, DamageSeverity)
    assert 0.0 <= res.confidence <= 1.0
    assert 0.0 <= res.severity_confidence <= 1.0
    assert len(res.damage_type_scores) == len(DamageType)
    assert len(res.severity_scores) == len(DamageSeverity)
    assert res.error is None


def test_classify_grayscale_image(classifier: CLIPDamageClassifier):
    """Grayscale 'L' images must be converted to RGB without error."""
    gray_img = Image.new("L", (128, 128), color=128)
    res = classifier.classify_image(gray_img, image_id="test_gray")
    assert res.is_success is True
    assert res.predicted_severity != DamageSeverity.unknown or res.confidence > 0.0


def test_classify_image_bytes(classifier: CLIPDamageClassifier):
    """Verify classification from raw in-memory JPEG bytes."""
    img = Image.new("RGB", (100, 100), color=(150, 100, 80))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    raw_bytes = buf.getvalue()

    res = classifier.classify_image(raw_bytes, image_id="test_bytes")
    assert res.is_success is True
    assert res.error is None


def test_classify_missing_file(classifier: CLIPDamageClassifier):
    """Non-existent image file must return graceful error result without crashing."""
    res = classifier.classify_image(
        "/tmp/non_existent_file_123456789.jpg",
        image_id="missing_file",
    )
    assert res.is_success is False
    assert res.predicted_damage_type == DamageType.unknown
    assert res.predicted_severity == DamageSeverity.unknown
    assert res.confidence == 0.0
    assert res.error is not None
    assert "missing" in res.error.lower() or "not found" in res.error.lower()


def test_classify_corrupted_bytes(classifier: CLIPDamageClassifier):
    """Corrupted binary image data must return graceful error result."""
    corrupt_bytes = b"NOT_A_REAL_IMAGE_DATA_0000000000"
    res = classifier.classify_image(corrupt_bytes, image_id="corrupt")
    assert res.is_success is False
    assert res.error is not None


def test_batch_classification(classifier: CLIPDamageClassifier):
    """Batch classification returns matching number of valid results."""
    imgs = [
        Image.new("RGB", (64, 64), color=(100, 100, 100)),
        Image.new("RGB", (64, 64), color=(200, 200, 200)),
    ]
    ids = ["batch_1", "batch_2"]
    results = classifier.classify_images(imgs, image_ids=ids, batch_size=2)
    assert len(results) == 2
    assert results[0].image_id == "batch_1"
    assert results[1].image_id == "batch_2"
    assert all(r.is_success for r in results)


# ---------------------------------------------------------------------------
# 3. Validation Metrics Calculation Unit Tests
# ---------------------------------------------------------------------------

def test_compute_classification_metrics_perfect():
    """Check metrics calculation on perfect 100% agreement."""
    y_true = ["none", "minor", "severe", "destroyed"]
    y_pred = ["none", "minor", "severe", "destroyed"]
    classes = ["none", "minor", "severe", "destroyed"]

    metrics = compute_classification_metrics(y_true, y_pred, classes)
    assert metrics["accuracy"] == 1.0
    assert metrics["macro_f1"] == 1.0
    assert metrics["macro_precision"] == 1.0
    assert metrics["macro_recall"] == 1.0
    for c in classes:
        assert metrics["per_class"][c]["f1_score"] == 1.0
        assert metrics["per_class"][c]["support"] == 1


def test_compute_classification_metrics_partial():
    """Check metrics calculation on mixed agreement."""
    y_true = ["none", "none", "destroyed", "destroyed"]
    y_pred = ["none", "destroyed", "destroyed", "none"]
    classes = ["none", "destroyed"]

    metrics = compute_classification_metrics(y_true, y_pred, classes)
    assert metrics["accuracy"] == 0.5
    assert metrics["total_samples"] == 4
    # For each class: TP=1, FP=1, FN=1 -> Prec=0.5, Rec=0.5, F1=0.5
    assert metrics["macro_f1"] == 0.5
    assert metrics["confusion_matrix"]["none"]["none"] == 1
    assert metrics["confusion_matrix"]["none"]["destroyed"] == 1
