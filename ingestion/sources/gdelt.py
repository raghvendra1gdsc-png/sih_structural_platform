"""
ingestion/sources/gdelt.py
============================
GDELT 2.0 news intelligence source adapter.
Uses the free GDELT DOC 2.0 API — no API key required.
Searches for Indian weather events in recent news articles.
All results are treated as UNVERIFIED external news.
Records marked source="gdelt", is_synthetic=False.
Cache: 30 minutes (free API — avoid hammering).
"""
from __future__ import annotations
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import requests

from ingestion.sources.base import InformationSource

logger = logging.getLogger(__name__)

GDELT_API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

SEARCH_QUERIES = [
    "India rain flood storm",
    "India cyclone weather alert",
    "India heatwave drought",
    "India cloudburst monsoon",
]

CITY_PATTERNS = {
    "Jaipur":    (26.9124, 75.7873, "Rajasthan"),
    "Delhi":     (28.6139, 77.2090, "Delhi"),
    "Mumbai":    (19.0760, 72.8777, "Maharashtra"),
    "Chennai":   (13.0827, 80.2707, "Tamil Nadu"),
    "Kolkata":   (22.5726, 88.3639, "West Bengal"),
    "Bengaluru": (12.9716, 77.5946, "Karnataka"),
    "Hyderabad": (17.3850, 78.4867, "Telangana"),
    "Guwahati":  (26.1445, 91.7362, "Assam"),
    "Ahmedabad": (23.0225, 72.5714, "Gujarat"),
    "Lucknow":   (26.8467, 80.9462, "Uttar Pradesh"),
    "Kochi":     ( 9.9312, 76.2673, "Kerala"),
    "Jodhpur":   (26.2389, 73.0243, "Rajasthan"),
}


def _extract_city(text: str) -> tuple[str, float, float, str]:
    text_lower = text.lower()
    for city, (lat, lon, state) in CITY_PATTERNS.items():
        if city.lower() in text_lower:
            return city, lat, lon, state
    return "Delhi", 28.6139, 77.2090, "Delhi"


class GDELTSource(InformationSource):
    """
    Queries GDELT DOC 2.0 API for recent Indian weather-related news.
    Free, no key, but rate-limit friendly with 30-min cache.
    """

    def __init__(self) -> None:
        super().__init__()
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self._cache_ttl = 1800  # 30 minutes

    @property
    def name(self) -> str:
        return "gdelt"

    def is_available(self) -> bool:
        return True  # Free API, no credentials needed

    def _fetch_query(self, query: str, max_records: int = 15) -> list[dict[str, Any]]:
        """Fetch GDELT articles for a single query string."""
        cache_key = query
        now = time.time()
        if cache_key in self._cache:
            ts, cached = self._cache[cache_key]
            if now - ts < self._cache_ttl:
                return cached

        try:
            resp = requests.get(
                GDELT_API_URL,
                params={
                    "query": query,
                    "mode": "ArtList",
                    "maxrecords": max_records,
                    "format": "json",
                    "timespan": "24h",
                    "sourcelang": "english",
                    "sourcecountry": "IN",
                },
                timeout=12,
            )
            resp.raise_for_status()
            data = resp.json()
            articles = data.get("articles", []) or []
            self._cache[cache_key] = (now, articles)
            return articles
        except Exception as e:
            logger.warning("[gdelt] query '%s' failed: %s", query, e)
            return []

    def fetch_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """Fetch recent weather news from GDELT, deduplicated by URL."""
        seen_urls: set[str] = set()
        records: list[dict[str, Any]] = []
        per_query = max(5, limit // len(SEARCH_QUERIES))

        for query in SEARCH_QUERIES:
            articles = self._fetch_query(query, max_records=per_query)
            for article in articles:
                url = article.get("url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                title = article.get("title", "")
                seendatetime = article.get("seendatetime", "")
                try:
                    dt = datetime.strptime(seendatetime, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
                except Exception:
                    dt = datetime.now(timezone.utc)

                city, lat, lon, state = _extract_city(f"{title} {article.get('domain', '')}")
                text = f"[News via GDELT] {title}. Source: {article.get('domain', 'unknown')}. URL: {url}"

                records.append({
                    "report_id": str(uuid.uuid4()),
                    "source": "gdelt",
                    "source_report_id": url[:200],
                    "submitted_at": dt.isoformat(),
                    "event_time": dt.isoformat(),
                    "city": city,
                    "state": state,
                    "country": "India",
                    "latitude": lat,
                    "longitude": lon,
                    "text": text,
                    "is_synthetic": False,
                    # News articles start with moderate trust — pipeline will score
                    "source_trust_score": 40.0,
                    "hashtags": [],
                    "media_urls": [url] if url else [],
                })

                if len(records) >= limit:
                    break
            if len(records) >= limit:
                break

        return records
