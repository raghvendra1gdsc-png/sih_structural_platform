"""
backend/llm/gemini_provider.py
================================
Google Gemini provider (gemini-3.6-flash — verified working).
Uses requests. Key stays server-side.
"""
from __future__ import annotations
import logging
import time

import requests

from backend.llm.base import (
    LLMAuthError, LLMProvider, LLMQuotaError, LLMResult, LLMUnavailableError
)

logger = logging.getLogger(__name__)

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiProvider(LLMProvider):
    @property
    def name(self) -> str:
        return "gemini"

    @property
    def model(self) -> str:
        from backend.core.config import settings
        return settings.GEMINI_MODEL

    def _get_api_key(self) -> str:
        from backend.core.config import settings
        return settings.GOOGLE_AI_STUDIO_KEY

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2500,
        temperature: float = 0.2,
    ) -> LLMResult:
        key = self._get_api_key()
        if not key:
            raise LLMAuthError("GOOGLE_AI_STUDIO_KEY not configured")

        url = BASE_URL.format(model=self.model)
        t0 = time.time()
        try:
            resp = requests.post(
                url,
                params={"key": key},
                json={
                    "contents": [{"parts": [{"text": user_prompt}]}],
                    "systemInstruction": {"parts": [{"text": system_prompt}]},
                    "generationConfig": {
                        "maxOutputTokens": max_tokens,
                        "temperature": temperature,
                    },
                },
                timeout=40,
            )
        except requests.exceptions.ConnectionError as e:
            raise LLMUnavailableError(f"Gemini unreachable: {type(e).__name__}") from e
        except requests.exceptions.Timeout:
            raise LLMUnavailableError("Gemini request timed out") from None

        latency_ms = int((time.time() - t0) * 1000)

        if resp.status_code == 400:
            body = resp.json()
            msg = body.get("error", {}).get("message", "")
            if "no longer available" in msg or "not found" in msg:
                raise LLMUnavailableError(f"Gemini model unavailable: {msg}")
        if resp.status_code == 403:
            raise LLMAuthError("Gemini: invalid API key")
        if resp.status_code == 429:
            raise LLMQuotaError("Gemini: quota/rate limit exceeded")
        if resp.status_code >= 500:
            raise LLMUnavailableError(f"Gemini server error: {resp.status_code}")
        if resp.status_code != 200:
            raise LLMUnavailableError(f"Gemini unexpected status {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise LLMUnavailableError("Gemini returned no candidates")
        parts = candidates[0].get("content", {}).get("parts", [])
        # Filter out pure thought parts if marked
        text_parts = [p["text"] for p in parts if "text" in p and not p.get("thought")]
        if not text_parts:
            text_parts = [p["text"] for p in parts if "text" in p]
        text = "".join(text_parts).strip()
        return LLMResult(text=text, provider=self.name, model=self.model, latency_ms=latency_ms)

