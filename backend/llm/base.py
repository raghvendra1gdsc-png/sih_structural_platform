"""
backend/llm/base.py
====================
LLM provider abstraction.
WeatherGPT uses this to talk to OpenAI or Gemini without caring which one.
"""
from __future__ import annotations
import abc
from dataclasses import dataclass
from typing import Optional


class LLMError(Exception):
    """Base LLM error."""


class LLMQuotaError(LLMError):
    """API quota / credits exhausted."""


class LLMAuthError(LLMError):
    """Invalid API key."""


class LLMUnavailableError(LLMError):
    """Provider unreachable (network/timeout)."""


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    latency_ms: int
    is_fallback: bool = False


class LLMProvider(abc.ABC):
    """Abstract base for LLM backends."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Provider slug (e.g. 'openai', 'gemini')."""

    @property
    @abc.abstractmethod
    def model(self) -> str:
        """Model identifier."""

    def is_configured(self) -> bool:
        """Returns True if the API key is set."""
        return bool(self._get_api_key())

    @abc.abstractmethod
    def _get_api_key(self) -> str:
        """Return the API key from settings."""

    @abc.abstractmethod
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> LLMResult:
        """
        Send a completion request. Returns LLMResult.
        Raises LLMError subclasses on failure.
        Never leaks API keys in exceptions or logs.
        """
