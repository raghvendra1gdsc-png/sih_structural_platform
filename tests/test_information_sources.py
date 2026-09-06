"""
tests/test_information_sources.py
=================================
Unit tests for external unstructured information sources:
- GDELT 2.0 News Intelligence
- Reddit via PRAW
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from ingestion.sources.gdelt import GDELTSource, _extract_city as gdelt_extract_city
from ingestion.sources.reddit import RedditSource, _is_weather_related, _extract_city as reddit_extract_city


class TestGDELTSource:
    def test_availability(self):
        source = GDELTSource()
        assert source.name == "gdelt"
        assert source.is_available() is True

    def test_city_extraction(self):
        city, lat, lon, state = gdelt_extract_city("Heavy rains lashed Jaipur this morning causing traffic delays.")
        assert city == "Jaipur"
        assert state == "Rajasthan"
        assert round(lat, 2) == 26.91
        assert round(lon, 2) == 75.79

        # Fallback to Delhi
        fallback_city, _, _, _ = gdelt_extract_city("A general economic update was released today.")
        assert fallback_city == "Delhi"

    @patch("requests.get")
    def test_fetch_query_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "articles": [
                {
                    "url": "https://example.com/news/1",
                    "title": "Severe cloudburst near Guwahati causes waterlogging",
                    "seendate": "20260905T060000Z",
                    "sourcecountry": "IN",
                }
            ]
        }
        mock_get.return_value = mock_resp

        source = GDELTSource()
        articles = source._fetch_query("India rain flood storm", max_records=5)
        assert len(articles) == 1
        assert "Guwahati" in articles[0]["title"]

    @patch("requests.get")
    def test_fetch_query_error_handled(self, mock_get):
        mock_get.side_effect = Exception("Connection timeout")
        source = GDELTSource()
        articles = source._fetch_query("India rain", max_records=5)
        assert articles == []


class TestRedditSource:
    def test_unconfigured_without_credentials(self):
        source = RedditSource()
        source._client_id = ""
        source._client_secret = ""
        assert not source.is_available()

    def test_configured_with_credentials(self):
        source = RedditSource()
        source._client_id = "test_id"
        source._client_secret = "test_secret"
        assert source.is_available()

    def test_weather_keyword_detection(self):
        assert _is_weather_related("Crazy baarish in Mumbai today, waterlogging everywhere!") is True
        assert _is_weather_related("Severe heat wave warnings issued for Delhi") is True
        assert _is_weather_related("Cloudburst reported in Himalayan foothills") is True
        assert _is_weather_related("Who will win the cricket match this weekend?") is False

    def test_city_extraction(self):
        city, lat, lon, state = reddit_extract_city("Heavy storms observed around Bangalore airport today")
        assert city == "Bengaluru"
        assert state == "Karnataka"

    def test_fetch_recent_graceful_when_empty_creds(self):
        source = RedditSource()
        source._client_id = ""
        records = source.fetch_recent(limit=10)
        assert records == []
