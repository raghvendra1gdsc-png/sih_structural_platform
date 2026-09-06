"""
ml_pipeline/damage_classification/schemas.py — Structured Classification Schemas

Defines the output schemas and data structures for the zero-shot damage
and severity classification pipeline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from ingestion.schemas import DamageSeverity, DamageType


class DamageClassificationResult(BaseModel):
    """
    Structured outcome of zero-shot damage classification on an image.

    IMPORTANT / DATA INTEGRITY NOTE:
    `confidence` represents the model's top softmax score across zero-shot text
    prompts in [0.0, 1.0]. It is a model heuristic score and must NOT be
    represented as a calibrated statistical probability of structural collapse.
    """

    image_id: Optional[str] = Field(
        default=None,
        description="Identifier or path of the classified image.",
    )
    predicted_damage_type: DamageType = Field(
        default=DamageType.unknown,
        description="Predicted primary structural damage category from the taxonomy.",
    )
    predicted_severity: DamageSeverity = Field(
        default=DamageSeverity.unknown,
        description="Predicted coarse damage severity level.",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Top softmax score of the predicted damage type class [0.0, 1.0].",
    )
    severity_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Top softmax score of the predicted severity class [0.0, 1.0].",
    )
    damage_type_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Softmax probability distribution across all evaluated damage types.",
    )
    severity_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Softmax probability distribution across all evaluated severity levels.",
    )
    model_name: str = Field(
        ...,
        description="Pretrained CLIP model architecture identifier.",
    )
    device: str = Field(
        ...,
        description="Compute device used for inference ('cpu', 'mps', 'cuda').",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when classification was performed.",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error description if image reading or classification failed.",
    )
    is_success: bool = Field(
        default=True,
        description="True if image was successfully parsed and classified.",
    )

    model_config = {"use_enum_values": False}
