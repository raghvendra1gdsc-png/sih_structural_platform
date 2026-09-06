"""
backend/llm/openai_provider.py
================================
OpenAI GPT-4o-mini provider.
Uses requests (not httpx) to avoid DNS resolution issues in some environments.
Key stays server-side — never exposed in responses or logs.
"""
from __future__ import annotations
import logging
import time
from typing import Optional

import requests

from backend.llm.base import (
    LLMAuthError, LLMProvider, LLMQuotaError, LLMResult, LLMUnavailableError
)

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    API_URL = "https://api.openai.com/v1/chat/completions"

    @property
    def name(self) -> str:
        return "openai"

    @property
    def model(self) -> str:
        from backend.core.config import settings
        return settings.OPENAI_MODEL

    def _get_api_key(self) -> str:
        from backend.core.config import settings
        return settings.OPENAI_API_KEY

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> LLMResult:
        key = self._get_api_key()
        if not key:
            raise LLMAuthError("OPENAI_API_KEY not configured")

        t0 = time.time()
        try:
            resp = requests.post(
                self.API_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
                timeout=20,
            )
        except requests.exceptions.ConnectionError as e:
            raise LLMUnavailableError(f"OpenAI unreachable: {type(e).__name__}") from e
        except requests.exceptions.Timeout:
            raise LLMUnavailableError("OpenAI request timed out") from None

        latency_ms = int((time.time() - t0) * 1000)

        if resp.status_code == 401:
            raise LLMAuthError("OpenAI: invalid API key")
        if resp.status_code == 429:
            raise LLMQuotaError("OpenAI: quota exhausted or rate limited")
        if resp.status_code >= 500:
            raise LLMUnavailableError(f"OpenAI server error: {resp.status_code}")
        if resp.status_code != 200:
            raise LLMUnavailableError(f"OpenAI unexpected status {resp.status_code}")

        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        return LLMResult(text=text, provider=self.name, model=self.model, latency_ms=latency_ms)
