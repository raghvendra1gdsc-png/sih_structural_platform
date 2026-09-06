"""
ml_pipeline/damage_classification/prompts.py — Zero-Shot Prompt Templates & Taxonomy Mapping

Defines natural-language prompt templates for structural damage types and
severity levels, mapped directly onto the existing DamageType and DamageSeverity enums.

WHY PROMPT ENGINEERING IS USED FOR ZERO-SHOT CLASSIFICATION:
Pretrained CLIP models are trained on WebImageText (WIT) image-caption pairs where
concepts appear in complete natural language sentences. Evaluating single isolated words
like "crack" or "spalling" yields noisy embeddings due to lexical polysemy (e.g., "crack"
can mean an audio sound, a physical fissure, or an informal slang). Embedding descriptive
natural templates like "a photo of a building facade with severe structural cracks" activates
the model's structural and spatial visual concepts, significantly stabilizing zero-shot accuracy.
"""

from __future__ import annotations

from ingestion.schemas import DamageSeverity, DamageType

# ---------------------------------------------------------------------------
# Structural Damage Type Prompt Templates
# ---------------------------------------------------------------------------

DAMAGE_TYPE_PROMPTS: dict[DamageType, list[str]] = {
    DamageType.structural_crack: [
        "a photograph of a building wall with severe structural cracks",
        "a photograph of deep diagonal shear cracks on concrete columns",
        "a photograph of a damaged building with major cracks in brick masonry",
        "a close-up photo of severe fracture cracks running through a concrete wall",
    ],
    DamageType.partial_collapse: [
        "a photograph of a partially collapsed building with fallen upper floors",
        "a photograph of partial building structural failure and sagging roof",
        "a photograph of a damaged building where one section has collapsed",
        "a photo of heavy structural failure with half of the building collapsed",
    ],
    DamageType.complete_collapse: [
        "a photograph of a completely collapsed building flattened to the ground",
        "a photograph of total structural collapse of a building reduced to rubble",
        "a photograph of a building pancaked and totally destroyed by an earthquake",
        "a photo of a demolished building completely leveled to the ground",
    ],
    DamageType.facade_damage: [
        "a photograph of building facade damage with broken glass windows",
        "a photograph of peeling exterior plaster and chipped cladding on a building",
        "a photograph of exterior architectural facade damage with shattered glass",
        "a photo of cracked tiles and superficial plaster peeling off a building wall",
    ],
    DamageType.debris: [
        "a photograph of piles of concrete debris and broken bricks on the ground",
        "a photograph of building rubble, fallen stones, and masonry debris in the street",
        "a photo of shattered concrete blocks and earthquake debris scattered around",
        "a photograph of a street covered in fallen masonry debris and plaster dust",
    ],
    DamageType.non_structural_damage: [
        "a photograph of minor non-structural cosmetic damage inside a building",
        "a photograph of fallen ceiling tiles, broken light fixtures, and displaced furniture",
        "a photograph of superficial hairline plaster cracks with no structural danger",
        "a photo of minor non-structural architectural damage to building partitions",
    ],
    DamageType.unknown: [
        "a photograph of a completely normal intact building with no damage",
        "a photograph of an undamaged building standing sound and stable",
        "a photograph of a modern building in perfect condition with zero damage",
        "a photo of an undamaged structure with intact walls and windows",
    ],
}

# ---------------------------------------------------------------------------
# Structural Damage Severity Prompt Templates
# ---------------------------------------------------------------------------

DAMAGE_SEVERITY_PROMPTS: dict[DamageSeverity, list[str]] = {
    DamageSeverity.none: [
        "a photograph of a completely normal undamaged building",
        "a photograph of an intact building with no visible damage",
        "a photograph of a structurally sound and undamaged building",
        "a photograph of a standing building in perfect condition with zero damage",
    ],
    DamageSeverity.minor: [
        "a photograph of a building with minor cosmetic damage and hairline cracks",
        "a photograph of slight exterior damage with minimal cracks",
        "a photo of light superficial damage to building plaster",
    ],
    DamageSeverity.moderate: [
        "a photograph of a building with moderate structural damage and visible cracks",
        "a photograph of visible exterior wall cracking and broken windows",
        "a photo of noticeable structural damage requiring building repair",
    ],
    DamageSeverity.severe: [
        "a photograph of a building with severe structural damage and partial collapse",
        "a photograph of heavily buckled columns and extensive structural failure",
        "a photo of dangerous structural damage threatening building collapse",
    ],
    DamageSeverity.destroyed: [
        "a photograph of a completely destroyed and leveled building",
        "a photograph of a total structural collapse reduced to a heap of rubble",
        "a photo of a fully destroyed flattened building structure",
    ],
    DamageSeverity.unknown: [
        "a blurry unidentifiable picture not showing any building or damage",
        "a completely corrupted or blank image without any architecture",
        "an unreadable abstract image",
    ],
}

# ---------------------------------------------------------------------------
# Mapping between xBD 4-tier benchmark labels and Platform Enums
# ---------------------------------------------------------------------------

XBD_SEVERITY_MAP: dict[str, DamageSeverity] = {
    "no-damage": DamageSeverity.none,
    "minor-damage": DamageSeverity.minor,
    "major-damage": DamageSeverity.severe,
    "destroyed": DamageSeverity.destroyed,
}

XBD_DAMAGE_TYPE_MAP: dict[str, DamageType] = {
    "no-damage": DamageType.unknown,
    "minor-damage": DamageType.facade_damage,
    "major-damage": DamageType.structural_crack,
    "destroyed": DamageType.complete_collapse,
}
