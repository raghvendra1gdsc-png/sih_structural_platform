"""
tests/test_llm_providers.py
===========================
Unit tests for LLM provider adapters:
- GeminiProvider (gemini-3.6-flash)
- OpenAIProvider (gpt-4o-mini)
- Error handling and fallback behaviors
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from backend.llm.base import (
    LLMAuthError,
    LLMQuotaError,
    LLMResult,
    LLMUnavailableError,
)
from backend.llm.gemini_provider import GeminiProvider
from backend.llm.openai_provider import OpenAIProvider


class TestGeminiProvider:
    def test_auth_error_when_key_missing(self):
        provider = GeminiProvider()
        with patch.object(provider, "_get_api_key", return_value=""):
            assert not provider.is_configured()
            with pytest.raises(LLMAuthError):
                provider.complete("sys", "user")

    @patch("requests.post")
    def test_successful_completion(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "It will remain sunny and pleasant in Jaipur."}]
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        provider = GeminiProvider()
        with patch.object(provider, "_get_api_key", return_value="valid_gemini_key"):
            assert provider.is_configured()
            res = provider.complete("System instruction", "Query")
            assert isinstance(res, LLMResult)
            assert "sunny and pleasant" in res.text
            assert res.provider == "gemini"

    @patch("requests.post")
    def test_quota_error(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_post.return_value = mock_resp

        provider = GeminiProvider()
        with patch.object(provider, "_get_api_key", return_value="valid_key"):
            with pytest.raises(LLMQuotaError):
                provider.complete("sys", "user")


class TestOpenAIProvider:
    def test_auth_error_when_key_missing(self):
        provider = OpenAIProvider()
        with patch.object(provider, "_get_api_key", return_value=""):
            assert not provider.is_configured()
            with pytest.raises(LLMAuthError):
                provider.complete("sys", "user")

    @patch("requests.post")
    def test_successful_completion(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "No rain is predicted for Mumbai tonight."
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        provider = OpenAIProvider()
        with patch.object(provider, "_get_api_key", return_value="valid_openai_key"):
            assert provider.is_configured()
            res = provider.complete("System prompt", "User query")
            assert isinstance(res, LLMResult)
            assert "No rain" in res.text
            assert res.provider == "openai"

    @patch("requests.post")
    def test_quota_error(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_post.return_value = mock_resp

        provider = OpenAIProvider()
        with patch.object(provider, "_get_api_key", return_value="valid_key"):
            with pytest.raises(LLMQuotaError):
                provider.complete("sys", "user")
