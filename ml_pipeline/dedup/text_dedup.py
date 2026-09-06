"""
ml_pipeline/dedup/text_dedup.py — Semantic Text Similarity for Deduplication

Provides lightweight sentence embedding using Sentence-Transformers (all-MiniLM-L6-v2)
and cosine similarity to detect identical, paraphrased, and near-duplicate damage reports.
Keeps model loading separate from individual comparisons via a singleton manager.
Includes a deterministic lexical/n-gram fallback for offline/air-gapped environments.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Global singleton cache for the embedding model
_EMBEDDING_MODEL: Optional[object] = None
_MODEL_LOAD_FAILED: bool = False
DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"


def get_sentence_transformer_model(
    model_name: str = DEFAULT_MODEL_NAME,
    force_reload: bool = False,
) -> Optional[object]:
    """
    Get or lazily load the SentenceTransformer embedding model.

    Keeps the model cached in memory so subsequent comparisons do not
    repeatedly initialize or load weights.

    Returns:
        SentenceTransformer instance, or None if unavailable.
    """
    global _EMBEDDING_MODEL, _MODEL_LOAD_FAILED

    if force_reload:
        _EMBEDDING_MODEL = None
        _MODEL_LOAD_FAILED = False

    if _EMBEDDING_MODEL is not None:
        return _EMBEDDING_MODEL

    if _MODEL_LOAD_FAILED and not force_reload:
        return None

    try:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading sentence-transformers model %r...", model_name)
        try:
            # Fast-path: use cached weights directly without making network requests
            model = SentenceTransformer(model_name, local_files_only=True)
        except Exception:
            # Fallback to normal loading if not yet downloaded
            model = SentenceTransformer(model_name)

        _EMBEDDING_MODEL = model
        logger.info("Sentence-transformers model %r successfully loaded.", model_name)
        return _EMBEDDING_MODEL
    except Exception as exc:
        logger.warning(
            "Failed to load sentence-transformers model %r (%s). "
            "Falling back to built-in lexical/n-gram cosine similarity.",
            model_name,
            exc,
        )
        _MODEL_LOAD_FAILED = True
        return None


def _lexical_n_gram_cosine_similarity(text1: str, text2: str, n: int = 3) -> float:
    """
    Fallback deterministic character n-gram and token cosine similarity.
    Used when sentence-transformers is offline or unavailable.
    """
    t1 = text1.lower().strip()
    t2 = text2.lower().strip()

    if not t1 or not t2:
        return 0.0
    if t1 == t2:
        return 1.0

    # Token-level tokens
    words1 = re.findall(r"\w+", t1)
    words2 = re.findall(r"\w+", t2)

    # Word set Jaccard
    s1, s2 = set(words1), set(words2)
    jaccard = len(s1 & s2) / max(len(s1 | s2), 1)

    # Character n-grams for typo & morphological tolerance
    def get_ngrams(s: str) -> Counter[str]:
        return Counter(s[i : i + n] for i in range(max(len(s) - n + 1, 0)))

    ng1, ng2 = get_ngrams(t1), get_ngrams(t2)
    dot = sum(count * ng2.get(gram, 0) for gram, count in ng1.items())
    mag1 = math.sqrt(sum(c * c for c in ng1.values()))
    mag2 = math.sqrt(sum(c * c for c in ng2.values()))
    ngram_cos = dot / (mag1 * mag2) if (mag1 > 0 and mag2 > 0) else 0.0

    # Combine token overlap and character n-gram cosine
    combined = 0.5 * jaccard + 0.5 * ngram_cos
    return float(max(0.0, min(1.0, combined)))


def embed_texts(
    texts: list[str],
    model_name: str = DEFAULT_MODEL_NAME,
) -> np.ndarray:
    """
    Embed a list of text strings into normalized feature vectors.

    Args:
        texts: List of input strings.
        model_name: Model identifier.

    Returns:
        np.ndarray of shape (len(texts), embedding_dim) with L2-normalized rows,
        or synthetic fallback vectors if model is unavailable.
    """
    if not texts:
        return np.empty((0, 384), dtype=np.float32)

    model = get_sentence_transformer_model(model_name)
    if model is not None:
        try:
            embeddings = model.encode(
                texts,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            return embeddings.astype(np.float32)
        except Exception as exc:
            logger.warning("Error during model.encode(): %s. Using fallback.", exc)

    # Fallback pseudo-embedding if model fails
    # Produces consistent vectors where similar texts have high dot products
    vectors = []
    for text in texts:
        # 384-dim hash projection
        vec = np.zeros(384, dtype=np.float32)
        words = re.findall(r"\w+", text.lower().strip())
        for w in words:
            idx = hash(w) % 384
            vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        vectors.append(vec)
    return np.stack(vectors, axis=0)


def text_similarity(
    text1: str | None,
    text2: str | None,
    model_name: str = DEFAULT_MODEL_NAME,
) -> float:
    """
    Compute semantic similarity between two texts in the range [0.0, 1.0].

    Edge cases:
    - If either text is None or empty/whitespace -> returns 0.0.
    - If texts are identical (after normalization) -> returns 1.0.
    - Minor wording changes / paraphrasing -> high similarity (>0.75-0.80).
    - Substantially different descriptions -> low similarity (<0.40).

    Args:
        text1: First report text description.
        text2: Second report text description.
        model_name: Sentence-transformer model identifier.

    Returns:
        float similarity score in [0.0, 1.0].
    """
    if text1 is None or text2 is None:
        return 0.0

    t1 = text1.strip()
    t2 = text2.strip()

    if not t1 or not t2:
        return 0.0

    # Exact match fast path
    if t1.lower() == t2.lower():
        return 1.0

    model = get_sentence_transformer_model(model_name)
    if model is not None:
        try:
            embeddings = embed_texts([t1, t2], model_name=model_name)
            sim = float(np.dot(embeddings[0], embeddings[1]))
            # Bound within [0.0, 1.0]
            return float(max(0.0, min(1.0, round(sim, 4))))
        except Exception as exc:
            logger.warning("Embedding cosine similarity failed: %s", exc)

    # Fallback lexical cosine similarity
    return round(_lexical_n_gram_cosine_similarity(t1, t2), 4)


def batch_text_similarity(
    pairs: list[tuple[str | None, str | None]],
    model_name: str = DEFAULT_MODEL_NAME,
) -> list[float]:
    """
    Compute similarities for a batch of text pairs efficiently.
    """
    return [text_similarity(t1, t2, model_name=model_name) for t1, t2 in pairs]
