"""
ingestion/sources/reddit.py
==============================
Reddit information source adapter using PRAW (official API only).
ALL Reddit content is treated as UNTRUSTED observation.
Records are marked source="reddit", is_synthetic=False, verification_status="pending".
Gracefully disabled when REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET are absent.
"""
from __future__ import annotations
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from ingestion.sources.base import InformationSource

logger = logging.getLogger(__name__)

WEATHER_KEYWORDS = [
    "rain", "flood", "cloudburst", "cyclone", "storm", "hail", "fog",
    "heat wave", "drought", "thunder", "lightning", "waterlogging",
    "barish", "aandhi", "toofan", "baarish", "baarish", "garmi", "loo",
    "monsoon", "rainfall", "heavy rain", "wind", "hurricane",
]

CITY_PATTERNS = {
    "Jaipur": r"\bjaipur\b",
    "Delhi": r"\b(delhi|ncr|new delhi)\b",
    "Mumbai": r"\b(mumbai|bombay)\b",
    "Chennai": r"\bchennai\b",
    "Kolkata": r"\bkolkata\b",
    "Bengaluru": r"\b(bengaluru|bangalore)\b",
    "Hyderabad": r"\bhyderabad\b",
    "Guwahati": r"\bguwahati\b",
    "Ahmedabad": r"\bahmedabad\b",
    "Lucknow": r"\blucknow\b",
    "Kochi": r"\b(kochi|cochin)\b",
    "Jodhpur": r"\bjodhpur\b",
}

CITY_COORDS = {
    "Jaipur":    (26.9124, 75.7873, "Rajasthan"),
    "Jodhpur":   (26.2389, 73.0243, "Rajasthan"),
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
}


def _extract_city(text: str) -> tuple[str, float, float, str]:
    """Extract city from post text. Defaults to Delhi if none found."""
    text_lower = text.lower()
    for city, pattern in CITY_PATTERNS.items():
        if re.search(pattern, text_lower):
            lat, lon, state = CITY_COORDS[city]
            return city, lat, lon, state
    return "Delhi", 28.6139, 77.2090, "Delhi"


def _is_weather_related(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in WEATHER_KEYWORDS)


class RedditSource(InformationSource):
    """
    Fetches weather-related Reddit posts from Indian subreddits.
    Uses PRAW (official Reddit API). Never scrapes web pages.
    """

    SUBREDDITS = ["india", "weather", "mumbai", "delhi", "bangalore", "hyderabad"]

    def __init__(self) -> None:
        super().__init__()
        from backend.core.config import settings
        self._client_id = settings.REDDIT_CLIENT_ID if hasattr(settings, "REDDIT_CLIENT_ID") else ""
        self._client_secret = settings.REDDIT_CLIENT_SECRET if hasattr(settings, "REDDIT_CLIENT_SECRET") else ""
        self._user_agent = "SIHWeatherPlatform/1.0"

    @property
    def name(self) -> str:
        return "reddit"

    def is_available(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def fetch_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """Fetch recent weather-related posts via PRAW."""
        try:
            import praw  # type: ignore
        except ImportError:
            logger.warning("[reddit] praw not installed — pip install praw")
            return []

        reddit = praw.Reddit(
            client_id=self._client_id,
            client_secret=self._client_secret,
            user_agent=self._user_agent,
        )

        records: list[dict[str, Any]] = []
        per_sub = max(1, limit // len(self.SUBREDDITS))

        for sub_name in self.SUBREDDITS:
            try:
                subreddit = reddit.subreddit(sub_name)
                for post in subreddit.new(limit=per_sub * 3):
                    combined = f"{post.title} {post.selftext or ''}"
                    if not _is_weather_related(combined):
                        continue
                    city, lat, lon, state = _extract_city(combined)
                    submitted_at = datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
                    records.append({
                        "report_id": str(uuid.uuid4()),
                        "source": "reddit",
                        "source_report_id": post.id,
                        "submitted_at": submitted_at.isoformat(),
                        "event_time": submitted_at.isoformat(),
                        "city": city,
                        "state": state,
                        "country": "India",
                        "latitude": lat,
                        "longitude": lon,
                        "text": f"[Reddit r/{sub_name}] {post.title}. {post.selftext[:500] if post.selftext else ''}".strip(),
                        "is_synthetic": False,
                        # Trust: Reddit posts start low — classified/verified by pipeline
                        "source_trust_score": 25.0,
                        "hashtags": [],
                        "media_urls": [],
                    })
                    if len(records) >= limit:
                        break
            except Exception as e:
                logger.warning("[reddit] subreddit r/%s error: %s", sub_name, e)

        return records[:limit]
