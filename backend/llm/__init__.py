"""backend/llm — LLM provider abstraction for WeatherGPT."""
from backend.llm.base import LLMProvider, LLMResult, LLMError, LLMQuotaError, LLMAuthError, LLMUnavailableError
from backend.llm.openai_provider import OpenAIProvider
from backend.llm.gemini_provider import GeminiProvider

__all__ = [
    "LLMProvider", "LLMResult", "LLMError",
    "LLMQuotaError", "LLMAuthError", "LLMUnavailableError",
    "OpenAIProvider", "GeminiProvider",
]


def get_llm_chain() -> list[LLMProvider]:
    """
    Returns the ordered LLM fallback chain based on LLM_BACKEND setting.
    Primary provider is tried first, secondary is the fallback.
    """
    from backend.core.config import settings
    backend = settings.LLM_BACKEND.lower()

    openai = OpenAIProvider()
    gemini = GeminiProvider()

    if backend == "openai":
        return [openai, gemini]
    elif backend == "gemini":
        return [gemini, openai]
    else:
        return []  # "none" — WeatherGPT operates without LLM
