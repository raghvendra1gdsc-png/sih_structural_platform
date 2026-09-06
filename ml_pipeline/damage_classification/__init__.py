"""
ml_pipeline/damage_classification — Zero-Shot Damage Classification Package

Modules:
- clip_classifier: Zero-shot classifier using OpenCLIP.
- prompts: Natural-language templates for damage types and severities.
- schemas: Output result models (DamageClassificationResult).
- run: Service runner to classify database canonical reports.
- validate_xbd: Validation harness against labeled xBD benchmark dataset.
"""

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

__all__ = [
    "CLIPDamageClassifier",
    "get_clip_classifier",
    "DamageClassificationResult",
    "get_default_device",
    "DAMAGE_TYPE_PROMPTS",
    "DAMAGE_SEVERITY_PROMPTS",
    "XBD_SEVERITY_MAP",
    "XBD_DAMAGE_TYPE_MAP",
]
