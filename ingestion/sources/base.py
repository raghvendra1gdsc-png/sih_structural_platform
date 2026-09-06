"""
ingestion/sources/base.py
==========================
Abstract base for all information sources (Reddit, GDELT, etc.).
"""
from __future__ import annotations
import abc
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class SourceHealth:
    source_name: str
    is_up: bool = True
    consecutive_failures: int = 0
    last_success_at: Optional[datetime] = None
    last_error: Optional[str] = None
    total_fetched: int = 0

    def record_success(self, count: int = 0) -> None:
        self.is_up = True
        self.consecutive_failures = 0
        self.last_success_at = datetime.now(timezone.utc)
        self.total_fetched += count

    def record_failure(self, error: str) -> None:
        self.consecutive_failures += 1
        self.last_error = error
        if self.consecutive_failures >= 3:
            self.is_up = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source_name,
            "is_up": self.is_up,
            "consecutive_failures": self.consecutive_failures,
            "last_success_at": self.last_success_at.isoformat() if self.last_success_at else None,
            "last_error": self.last_error,
            "total_fetched": self.total_fetched,
        }


class InformationSource(abc.ABC):
    """Abstract base for all unverified information sources."""

    def __init__(self) -> None:
        self.health = SourceHealth(source_name=self.name)

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Stable source slug."""

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Returns True if source credentials / access are configured."""

    @abc.abstractmethod
    def fetch_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """
        Fetch recent raw records from this source.
        Returns list of dicts compatible with RawWeatherReport fields.
        Never raises — returns empty list on failure.
        """

    def safe_fetch(self, limit: int = 50) -> list[dict[str, Any]]:
        """Public entry point with health tracking and graceful degradation."""
        if not self.is_available():
            logger.info("[%s] source not available (credentials not configured)", self.name)
            return []
        try:
            records = self.fetch_recent(limit=limit)
            self.health.record_success(len(records))
            return records
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            logger.warning("[%s] fetch_recent failed: %s", self.name, err)
            self.health.record_failure(err)
            return []
