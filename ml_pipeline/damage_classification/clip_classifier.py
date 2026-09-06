"""
ml_pipeline/damage_classification/clip_classifier.py — CLIP Zero-Shot Damage Classifier

Implements zero-shot structural damage classification and severity estimation
using OpenCLIP (ViT-B-32). Pre-encodes prompt templates for fast inference,
supports CPU, MPS, and CUDA devices, and handles images robustly.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any, Optional, Union

import open_clip
import torch
from PIL import Image, UnidentifiedImageError

from ingestion.schemas import DamageSeverity, DamageType
from ml_pipeline.damage_classification.prompts import (
    DAMAGE_SEVERITY_PROMPTS,
    DAMAGE_TYPE_PROMPTS,
)
from ml_pipeline.damage_classification.schemas import DamageClassificationResult

logger = logging.getLogger(__name__)

ImageInput = Union[str, Path, bytes, Image.Image, None]

# Global singleton model cache: {(model_name, pretrained, device_str): (model, preprocess)}
_MODEL_CACHE: dict[tuple[str, str, str], tuple[Any, Any]] = {}


def get_default_device() -> str:
    """Detect the best available device for local execution."""
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


class CLIPDamageClassifier:
    """
    Zero-shot classifier for structural damage types and severity levels.

    Uses OpenCLIP to compare image embeddings against ensembled natural-language
    prompt templates without requiring fine-tuning or custom neural networks.
    """

    def __init__(
        self,
        model_name: str = "ViT-B-32",
        pretrained: str = "laion2b_s34b_b79k",
        device: str | None = None,
        force_reload: bool = False,
    ) -> None:
        self.model_name = model_name
        self.pretrained = pretrained
        self.device = device or get_default_device()

        cache_key = (self.model_name, self.pretrained, self.device)
        global _MODEL_CACHE

        if force_reload or cache_key not in _MODEL_CACHE:
            logger.info(
                "Initializing CLIP model %s (%s) on device %s...",
                self.model_name,
                self.pretrained,
                self.device,
            )
            model, _, preprocess = open_clip.create_model_and_transforms(
                self.model_name,
                pretrained=self.pretrained,
                device=self.device,
            )
            model.eval()
            _MODEL_CACHE[cache_key] = (model, preprocess)
            logger.info("CLIP model %s successfully loaded and cached.", self.model_name)

        self.model, self.preprocess = _MODEL_CACHE[cache_key]
        self.tokenizer = open_clip.get_tokenizer(self.model_name)

        # Pre-encode text prompt templates once into normalized feature tensors
        self._precompute_text_features()

    def _precompute_text_features(self) -> None:
        """Pre-encode all damage type and severity prompt templates."""
        with torch.no_grad():
            # 1. Damage Types
            self.damage_types: list[DamageType] = list(DAMAGE_TYPE_PROMPTS.keys())
            self.damage_type_template_counts: list[int] = []
            all_type_prompts: list[str] = []

            for dt in self.damage_types:
                prompts = DAMAGE_TYPE_PROMPTS[dt]
                self.damage_type_template_counts.append(len(prompts))
                all_type_prompts.extend(prompts)

            tokens_type = self.tokenizer(all_type_prompts).to(self.device)
            type_features = self.model.encode_text(tokens_type)
            self.type_features = type_features / type_features.norm(dim=-1, keepdim=True)

            # 2. Damage Severities
            self.severities: list[DamageSeverity] = list(DAMAGE_SEVERITY_PROMPTS.keys())
            self.severity_template_counts: list[int] = []
            all_sev_prompts: list[str] = []

            for ds in self.severities:
                prompts = DAMAGE_SEVERITY_PROMPTS[ds]
                self.severity_template_counts.append(len(prompts))
                all_sev_prompts.extend(prompts)

            tokens_sev = self.tokenizer(all_sev_prompts).to(self.device)
            sev_features = self.model.encode_text(tokens_sev)
            self.sev_features = sev_features / sev_features.norm(dim=-1, keepdim=True)

    def _load_image(self, image_input: ImageInput) -> Image.Image | None:
        """
        Safely load an image into RGB PIL format.
        Handles missing files, corrupt data, raw bytes, and path strings without crashing.
        """
        if image_input is None:
            return None

        try:
            if isinstance(image_input, str):
                image_input = image_input.strip()
                if not image_input:
                    return None
                path = Path(image_input)
                if not path.exists() or not path.is_file():
                    logger.debug("Image file not found: %s", image_input)
                    return None
                with Image.open(path) as img:
                    return img.convert("RGB")

            elif isinstance(image_input, Path):
                if not image_input.exists() or not image_input.is_file():
                    logger.debug("Image path not found: %s", image_input)
                    return None
                with Image.open(image_input) as img:
                    return img.convert("RGB")

            elif isinstance(image_input, (bytes, bytearray)):
                if len(image_input) == 0:
                    return None
                with Image.open(io.BytesIO(image_input)) as img:
                    return img.convert("RGB")

            elif isinstance(image_input, Image.Image):
                return image_input.convert("RGB")

        except (UnidentifiedImageError, OSError, ValueError) as exc:
            logger.warning("Failed to open image: %s", exc)
            return None
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Unexpected error opening image: %s", exc)
            return None

        return None

    def classify_image(
        self,
        image_input: ImageInput,
        image_id: str | None = None,
    ) -> DamageClassificationResult:
        """
        Classify a single image for damage type and severity.

        Args:
            image_input: Path, bytes, PIL Image, or None.
            image_id: Optional tracking identifier.

        Returns:
            DamageClassificationResult.
        """
        pil_img = self._load_image(image_input)
        if pil_img is None:
            return DamageClassificationResult(
                image_id=image_id or (str(image_input) if isinstance(image_input, (str, Path)) else None),
                predicted_damage_type=DamageType.unknown,
                predicted_severity=DamageSeverity.unknown,
                confidence=0.0,
                severity_confidence=0.0,
                damage_type_scores={},
                severity_scores={},
                model_name=self.model_name,
                device=self.device,
                error="Image missing, corrupt, or unreadable",
                is_success=False,
            )

        try:
            tensor = self.preprocess(pil_img).unsqueeze(0).to(self.device)

            with torch.no_grad():
                image_features = self.model.encode_image(tensor)
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)

                # 1. Damage Type Similarities
                type_sims = (100.0 * image_features @ self.type_features.T).squeeze(0)
                # Aggregate templates per class (mean similarity)
                class_type_sims = []
                idx = 0
                for count in self.damage_type_template_counts:
                    class_type_sims.append(type_sims[idx : idx + count].mean())
                    idx += count

                class_type_tensor = torch.stack(class_type_sims)
                type_probs = torch.softmax(class_type_tensor, dim=-1).cpu().numpy()

                best_type_idx = int(type_probs.argmax())
                best_type = self.damage_types[best_type_idx]
                type_conf = float(type_probs[best_type_idx])

                type_scores = {
                    self.damage_types[i].value: round(float(type_probs[i]), 4)
                    for i in range(len(self.damage_types))
                }

                # 2. Damage Severity Similarities
                sev_sims = (100.0 * image_features @ self.sev_features.T).squeeze(0)
                class_sev_sims = []
                idx = 0
                for count in self.severity_template_counts:
                    class_sev_sims.append(sev_sims[idx : idx + count].mean())
                    idx += count

                class_sev_tensor = torch.stack(class_sev_sims)
                sev_probs = torch.softmax(class_sev_tensor, dim=-1).cpu().numpy()

                best_sev_idx = int(sev_probs.argmax())
                best_sev = self.severities[best_sev_idx]
                sev_conf = float(sev_probs[best_sev_idx])

                sev_scores = {
                    self.severities[i].value: round(float(sev_probs[i]), 4)
                    for i in range(len(self.severities))
                }

            return DamageClassificationResult(
                image_id=image_id or (str(image_input) if isinstance(image_input, (str, Path)) else None),
                predicted_damage_type=best_type,
                predicted_severity=best_sev,
                confidence=round(type_conf, 4),
                severity_confidence=round(sev_conf, 4),
                damage_type_scores=type_scores,
                severity_scores=sev_scores,
                model_name=self.model_name,
                device=self.device,
                error=None,
                is_success=True,
            )

        except Exception as exc:
            logger.error("Error during CLIP image classification: %s", exc, exc_info=True)
            return DamageClassificationResult(
                image_id=image_id or (str(image_input) if isinstance(image_input, (str, Path)) else None),
                predicted_damage_type=DamageType.unknown,
                predicted_severity=DamageSeverity.unknown,
                confidence=0.0,
                severity_confidence=0.0,
                damage_type_scores={},
                severity_scores={},
                model_name=self.model_name,
                device=self.device,
                error=str(exc),
                is_success=False,
            )

    def classify_images(
        self,
        image_inputs: list[ImageInput],
        image_ids: list[str | None] | None = None,
        batch_size: int = 16,
    ) -> list[DamageClassificationResult]:
        """
        Classify a batch of images efficiently.
        """
        results: list[DamageClassificationResult] = []
        ids = image_ids or [None] * len(image_inputs)

        for i in range(0, len(image_inputs), batch_size):
            batch_inputs = image_inputs[i : i + batch_size]
            batch_ids = ids[i : i + batch_size]
            for img_in, img_id in zip(batch_inputs, batch_ids):
                results.append(self.classify_image(img_in, image_id=img_id))

        return results


def get_clip_classifier(
    model_name: str = "ViT-B-32",
    pretrained: str = "laion2b_s34b_b79k",
    device: str | None = None,
) -> CLIPDamageClassifier:
    """Convenience factory function for getting a CLIPDamageClassifier instance."""
    return CLIPDamageClassifier(model_name=model_name, pretrained=pretrained, device=device)

