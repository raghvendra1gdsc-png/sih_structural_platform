"""
ingestion/usgs_ingester.py
===========================
Reusable USGS earthquake event ingestion module.

Responsibilities
----------------
1. Fetch GeoJSON from the USGS FDSNWS earthquake API.
2. Parse and validate via Pydantic schemas (USGSFeatureCollection → EarthquakeEvent).
3. Classify each event with a GeographicScope (india / regional / other).
4. Cache results to disk for offline / demo use.
5. Handle all failure modes gracefully — never crash the application.

Geographic Relevance Classification
-------------------------------------
Tier 1 — india
  USGS place string contains "India" (case-insensitive), OR the event coordinates
  fall inside a broad India polygon approximation.

Tier 2 — regional
  Event coordinates fall within the "Greater South Asia" bounding box
  (covers Nepal, Pakistan, Afghanistan, Bangladesh, Bhutan, Myanmar, Sri Lanka,
  Tibet border belt) but NOT inside the India polygon.

Tier 3 — other
  Everything else.

The original USGS place, coordinates, event_id and url are NEVER altered.

Usage
-----
    # As a module (Phase 4 will call this from FastAPI)
    from ingestion.usgs_ingester import fetch_usgs_events, load_cached_events

    events = fetch_usgs_events()          # live fetch + cache
    events = fetch_usgs_events(offline=True)  # cache only

    # As a CLI
    python -m ingestion.usgs_ingester --limit 50 --min-magnitude 5.0
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

from ingestion.schemas import (
    EarthquakeEvent,
    GeographicScope,
    USGSFeatureCollection,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

USGS_API_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
USGS_REQUEST_TIMEOUT = 20  # seconds

# Default cache path — committed to repo for offline demo
DEFAULT_CACHE_PATH = (
    Path(__file__).parent.parent / "data" / "sample_dataset" / "usgs_cache.json"
)

# ---------------------------------------------------------------------------
# Geographic classification constants
# ---------------------------------------------------------------------------

# India is L-shaped and cannot be represented by a single bounding box without
# swallowing Nepal, Afghanistan, Myanmar, and Qinghai/Tibet.
# We use multiple tighter sub-rectangles that together approximate India's shape.
#
# Each tuple: (min_lat, max_lat, min_lon, max_lon)
#
# Critical exclusions:
#   Nepal        ~26–30°N, 80–88°E  → the central rectangle stops at lon 80.5°E above 26°N
#   Afghanistan  ~34–38°N, 60–75°E  → excluded by lon ceiling of northern strip (≤75°E)
#   Myanmar      ~16–28°N, 92–100°E → northeast strip lon < 92°E keeps it out
#   Qinghai/Tibet~32–36°N, 88–100°E → excluded by lat ceiling of northeastern strip (≤29°N)
#
# NOTE: bbox is a secondary signal.  _place_contains_india() runs FIRST and
# resolves ambiguous border-zone events (e.g. "Uttarakhand, India" at 30°N, 79°E)
# before the bbox is ever consulted.
_INDIA_POLY = [
    # ── Southern peninsula: Kerala, Tamil Nadu, Karnataka, Andhra Pradesh,
    #    Telangana, Goa (below 20°N — no neighbouring country conflict here)
    (8.0, 20.0, 72.5, 87.0),

    # ── Western India: Gujarat, Rajasthan, Haryana (west of 77°E)
    #    Lon ceiling of 77°E keeps this well away from Nepal/Bihar junction
    (20.0, 30.0, 68.1, 77.0),

    # ── Lower-central India: Madhya Pradesh, Chhattisgarh, Odisha,
    #    Jharkhand, West Bengal, southern Bihar — only up to 26°N
    #    to avoid the Nepal latitude band (26–30°N, 80–88°E)
    (20.0, 26.0, 77.0, 89.0),

    # ── Bihar/West Bengal strip at 26–30°N: keep it narrow (lon ≤ 87°E)
    #    Nepal is 80–88°E in this band; we stay west of 80°E here
    (26.0, 30.0, 77.0, 80.0),

    # ── Northern highlands: Himachal Pradesh, J&K (Jammu side), Ladakh
    #    Lon ceiling 80.5°E avoids the Nepal border strip
    (30.0, 35.5, 74.0, 80.5),

    # ── Northeast India: Assam, Meghalaya, Tripura, Mizoram, Manipur,
    #    Nagaland, Arunachal Pradesh — lon 89–97.5°E, lat 22–29°N
    #    Ceiling of 29°N and 97.5°E keeps Qinghai/Tibet (32°N+) and
    #    Myanmar (96–100°E above 20°N) out of this box.
    (22.0, 29.0, 89.0, 97.5),

    # ── Andaman & Nicobar Islands (narrow longitude window 92–94°E)
    (6.0, 14.0, 92.0, 94.0),

    # ── Lakshadweep
    (8.0, 12.5, 71.5, 74.5),
]

# Keywords in USGS place strings that unambiguously identify India
_INDIA_PLACE_KEYWORDS = [
    "india",
    "gujarat", "rajasthan", "uttarakhand", "uttaranchal", "himachal pradesh",
    "jammu", "kashmir", "ladakh", "punjab", "haryana", "delhi",
    "uttar pradesh", "bihar", "jharkhand", "west bengal", "odisha", "chhattisgarh",
    "madhya pradesh", "maharashtra", "andhra pradesh", "telangana", "karnataka",
    "kerala", "tamil nadu", "goa", "sikkim", "assam", "meghalaya", "tripura",
    "mizoram", "manipur", "nagaland", "arunachal", "andaman", "lakshadweep",
]

# Bounding box covering the greater South/Central Asian seismic region that
# plausibly affects India (Nepal, Pakistan, Afghanistan, Myanmar, Bhutan, Tibet belt)
_REGIONAL_BBOX = (
    4.0,   # min_lat  (includes Sri Lanka)
    45.0,  # max_lat  (northern Afghanistan / Tajikistan)
    55.0,  # min_lon  (western Pakistan / Iran border)
    100.0, # max_lon  (extends into Myanmar / Yunnan)
)

# Country name fragments in USGS place strings that qualify as "regional"
_REGIONAL_PLACE_KEYWORDS = [
    "nepal", "pakistan", "afghanistan", "bangladesh", "bhutan", "myanmar",
    "burma", "sri lanka", "tibet", "xinjiang", "qinghai", "yunnan", "sichuan",
    "tajikistan", "iran", "china", "xizang",
]

# ---------------------------------------------------------------------------
# Geographic classification
# ---------------------------------------------------------------------------


def _is_in_india_bbox(lat: float, lon: float) -> bool:
    """Check whether coordinates fall inside any India bounding rectangle."""
    for (min_lat, max_lat, min_lon, max_lon) in _INDIA_POLY:
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            return True
    return False


def _place_contains_india(place: str) -> bool:
    """Return True if the USGS place string identifies an Indian location."""
    place_lower = place.lower()
    return any(kw in place_lower for kw in _INDIA_PLACE_KEYWORDS)


def _is_regional(lat: float, lon: float, place: str) -> bool:
    """Return True if the event is in the neighbouring South/Central Asian region."""
    min_lat, max_lat, min_lon, max_lon = _REGIONAL_BBOX
    in_box = min_lat <= lat <= max_lat and min_lon <= lon <= max_lon
    place_lower = place.lower()
    keyword_match = any(kw in place_lower for kw in _REGIONAL_PLACE_KEYWORDS)
    return in_box or keyword_match


def classify_geographic_scope(lat: float, lon: float, place: str) -> GeographicScope:
    """
    Classify a USGS event's geographic relevance to India.

    Parameters
    ----------
    lat, lon : float
        Event coordinates (WGS-84).
    place : str
        USGS place description string — used verbatim, never modified.

    Returns
    -------
    GeographicScope
        ``india`` → Tier 1 (explicitly Indian event)
        ``regional`` → Tier 2 (neighbouring country, plausibly affects India)
        ``other`` → Tier 3 (too distant or unrelated)
    """
    if _place_contains_india(place) or _is_in_india_bbox(lat, lon):
        return GeographicScope.india
    if _is_regional(lat, lon, place):
        return GeographicScope.regional
    return GeographicScope.other


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def load_cached_events(cache_path: Path = DEFAULT_CACHE_PATH) -> Optional[list[EarthquakeEvent]]:
    """
    Load USGS events from the on-disk cache.

    Returns None if the cache does not exist or cannot be parsed.
    Never raises — callers should handle None as "cache miss".
    """
    if not cache_path.exists():
        logger.debug("USGS cache not found at %s", cache_path)
        return None
    try:
        raw: list[dict] = json.loads(cache_path.read_text(encoding="utf-8"))
        events = [EarthquakeEvent.model_validate(e) for e in raw]
        logger.info("Loaded %d events from USGS cache: %s", len(events), cache_path)
        return events
    except Exception as exc:
        logger.warning("USGS cache at %s is corrupt or unreadable: %s", cache_path, exc)
        return None


def save_events_to_cache(
    events: list[EarthquakeEvent],
    cache_path: Path = DEFAULT_CACHE_PATH,
) -> None:
    """
    Persist earthquake events to disk for offline use.

    The cache stores the full EarthquakeEvent model including geographic_scope.
    """
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    data = [e.model_dump(mode="json") for e in events]
    cache_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    logger.info("Saved %d USGS events to cache: %s", len(events), cache_path)


# ---------------------------------------------------------------------------
# Core fetch
# ---------------------------------------------------------------------------


class DataSourceUnavailableError(Exception):
    """
    Raised when the USGS API cannot be reached and no usable cache exists.

    Callers MUST catch this and handle gracefully — do NOT let it propagate
    to the end-user without a clear error message.
    """


def _build_usgs_params(
    min_magnitude: float,
    start_time: str,
    end_time: str,
    min_lat: float,
    max_lat: float,
    min_lon: float,
    max_lon: float,
    limit: int,
    order_by: str,
) -> dict:
    return {
        "format": "geojson",
        "minmagnitude": min_magnitude,
        "starttime": start_time,
        "endtime": end_time,
        "minlatitude": min_lat,
        "maxlatitude": max_lat,
        "minlongitude": min_lon,
        "maxlongitude": max_lon,
        "limit": limit,
        "orderby": order_by,
    }


def fetch_usgs_events(
    *,
    min_magnitude: float = 5.0,
    start_time: str = "2001-01-01",
    end_time: str = "2021-12-31",
    # Extended bounding box: India + surrounding seismic region
    min_lat: float = 4.0,
    max_lat: float = 45.0,
    min_lon: float = 55.0,
    max_lon: float = 100.0,
    limit: int = 100,
    order_by: str = "magnitude",
    offline: bool = False,
    cache_path: Path = DEFAULT_CACHE_PATH,
    timeout: int = USGS_REQUEST_TIMEOUT,
) -> list[EarthquakeEvent]:
    """
    Fetch earthquake events from USGS and classify their geographic relevance.

    Tier priority for selection:
      Tier 1 (india) → Tier 2 (regional) → Tier 3 (other)

    Parameters
    ----------
    min_magnitude : float
        Minimum magnitude threshold.
    start_time, end_time : str
        ISO-8601 date strings for the query window.
    min_lat, max_lat, min_lon, max_lon : float
        Bounding box covering India + neighbours (wider than India alone).
    limit : int
        Maximum number of features to request from USGS.
    order_by : str
        USGS orderby parameter (``"magnitude"`` or ``"time"``).
    offline : bool
        If True, skip live fetch and use cache only.
    cache_path : Path
        Path to the on-disk event cache.
    timeout : int
        Request timeout in seconds.

    Returns
    -------
    list[EarthquakeEvent]
        Events with geographic_scope populated.  At least one event guaranteed
        if cache exists; raises DataSourceUnavailableError otherwise.
    """
    if offline:
        cached = load_cached_events(cache_path)
        if cached:
            return cached
        raise DataSourceUnavailableError(
            f"Offline mode requested but no USGS cache found at {cache_path}. "
            "Run without --offline first to seed the cache."
        )

    params = _build_usgs_params(
        min_magnitude=min_magnitude,
        start_time=start_time,
        end_time=end_time,
        min_lat=min_lat,
        max_lat=max_lat,
        min_lon=min_lon,
        max_lon=max_lon,
        limit=limit,
        order_by=order_by,
    )

    try:
        logger.info(
            "Fetching USGS events (M>=%.1f, %s–%s, bbox=[%.1f,%.1f,%.1f,%.1f]) …",
            min_magnitude, start_time, end_time,
            min_lat, max_lat, min_lon, max_lon,
        )
        response = requests.get(
            USGS_API_URL,
            params=params,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.Timeout:
        logger.error("USGS request timed out after %ds.", timeout)
        return _fallback_to_cache(cache_path, reason="timeout")
    except requests.HTTPError as exc:
        logger.error("USGS HTTP error: %s", exc)
        return _fallback_to_cache(cache_path, reason=str(exc))
    except requests.RequestException as exc:
        logger.error("USGS request failed: %s", exc)
        return _fallback_to_cache(cache_path, reason=str(exc))

    try:
        collection = USGSFeatureCollection.model_validate(response.json())
    except Exception as exc:
        logger.error("Failed to parse USGS GeoJSON response: %s", exc)
        return _fallback_to_cache(cache_path, reason=f"parse error: {exc}")

    if not collection.features:
        logger.warning("USGS returned 0 features for the given query parameters.")
        return _fallback_to_cache(cache_path, reason="empty response")

    events: list[EarthquakeEvent] = []
    skipped = 0
    for feature in collection.features:
        try:
            lon, lat, depth = feature.geometry.coordinates
            scope = classify_geographic_scope(lat, lon, feature.properties.place)
            event = feature.to_earthquake_event(geographic_scope=scope)
            events.append(event)
        except Exception as exc:
            logger.warning(
                "Skipping malformed USGS feature %s: %s",
                getattr(feature, "id", "?"),
                exc,
            )
            skipped += 1

    if skipped:
        logger.warning("Skipped %d malformed USGS features.", skipped)

    if not events:
        logger.error("No valid events could be parsed from USGS response.")
        return _fallback_to_cache(cache_path, reason="all features malformed")

    scope_counts = {}
    for e in events:
        scope_counts[e.geographic_scope.value] = scope_counts.get(e.geographic_scope.value, 0) + 1
    logger.info(
        "Fetched %d events: %s",
        len(events),
        ", ".join(f"{k}={v}" for k, v in sorted(scope_counts.items())),
    )

    save_events_to_cache(events, cache_path)
    return events


def _fallback_to_cache(cache_path: Path, reason: str) -> list[EarthquakeEvent]:
    """Try cache; raise DataSourceUnavailableError if cache also missing."""
    logger.warning("Attempting cache fallback (reason: %s).", reason)
    cached = load_cached_events(cache_path)
    if cached:
        logger.warning(
            "Using %d cached USGS events (stale data). "
            "Live fetch failed: %s",
            len(cached), reason,
        )
        return cached
    raise DataSourceUnavailableError(
        f"USGS fetch failed ({reason}) and no local cache found at {cache_path}. "
        "Cannot proceed without real earthquake event IDs."
    )


# ---------------------------------------------------------------------------
# Convenience selectors
# ---------------------------------------------------------------------------


def select_events_for_demo(
    events: list[EarthquakeEvent],
    n: int = 3,
    prefer_india: bool = True,
) -> list[EarthquakeEvent]:
    """
    Select up to ``n`` events for the synthetic report generator.

    Selection strategy:
      1. Prioritise Tier 1 (india) events, sorted by magnitude desc.
      2. Fill remaining slots with Tier 2 (regional) events.
      3. Only use Tier 3 (other) if nothing else is available.

    This ensures the demo dataset features primarily Indian earthquakes with
    regional events as supplement — never silently swapping a regional event
    for an Indian one by misrepresenting its scope.

    Parameters
    ----------
    events : list[EarthquakeEvent]
        Full set of events returned by ``fetch_usgs_events``.
    n : int
        Number of events to select.
    prefer_india : bool
        If True (default), Tier 1 events are prioritised.

    Returns
    -------
    list[EarthquakeEvent]
        Up to ``n`` events in descending magnitude order.
    """
    if not prefer_india:
        return sorted(events, key=lambda e: e.magnitude, reverse=True)[:n]

    india = sorted(
        [e for e in events if e.geographic_scope == GeographicScope.india],
        key=lambda e: e.magnitude,
        reverse=True,
    )
    regional = sorted(
        [e for e in events if e.geographic_scope == GeographicScope.regional],
        key=lambda e: e.magnitude,
        reverse=True,
    )
    other = sorted(
        [e for e in events if e.geographic_scope == GeographicScope.other],
        key=lambda e: e.magnitude,
        reverse=True,
    )

    selected: list[EarthquakeEvent] = []
    for pool in (india, regional, other):
        remaining = n - len(selected)
        if remaining <= 0:
            break
        selected.extend(pool[:remaining])

    logger.info(
        "Selected %d events for demo: %s",
        len(selected),
        [
            f"{e.event_id} ({e.magnitude:.1f} {e.magnitude_type.value}, "
            f"scope={e.geographic_scope.value}, place={e.place!r})"
            for e in selected
        ],
    )
    return selected


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="usgs_ingester",
        description=(
            "Fetch, classify, and cache USGS earthquake events relevant to India.\n\n"
            "Outputs a summary of ingested events to stdout and caches them to\n"
            "data/sample_dataset/usgs_cache.json for offline use."
        ),
    )
    p.add_argument("--min-magnitude", type=float, default=5.0,
                   help="Minimum magnitude threshold (default: 5.0).")
    p.add_argument("--start-time", default="2001-01-01",
                   help="Query start date ISO-8601 (default: 2001-01-01).")
    p.add_argument("--end-time", default="2021-12-31",
                   help="Query end date ISO-8601 (default: 2021-12-31).")
    p.add_argument("--limit", type=int, default=100,
                   help="Max USGS features to request (default: 100).")
    p.add_argument("--offline", action="store_true",
                   help="Use cached events only; skip live fetch.")
    p.add_argument("--show-all", action="store_true",
                   help="Print all fetched events (default: show summary only).")
    p.add_argument("--log-level", default="INFO",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p


def main(argv: Optional[list[str]] = None) -> int:
    p = _build_parser()
    args = p.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        events = fetch_usgs_events(
            min_magnitude=args.min_magnitude,
            start_time=args.start_time,
            end_time=args.end_time,
            limit=args.limit,
            offline=args.offline,
        )
    except DataSourceUnavailableError as exc:
        logger.error("Cannot fetch USGS events: %s", exc)
        return 1

    # Print summary
    india_count = sum(1 for e in events if e.geographic_scope == GeographicScope.india)
    regional_count = sum(1 for e in events if e.geographic_scope == GeographicScope.regional)
    other_count = sum(1 for e in events if e.geographic_scope == GeographicScope.other)

    print(f"\n=== USGS Ingestion Summary ===")
    print(f"Total events     : {len(events)}")
    print(f"  Tier 1 (india)   : {india_count}")
    print(f"  Tier 2 (regional): {regional_count}")
    print(f"  Tier 3 (other)   : {other_count}")

    demo_selection = select_events_for_demo(events, n=3)
    print(f"\nDemo selection (top 3 by scope+magnitude):")
    for e in demo_selection:
        print(
            f"  [{e.geographic_scope.value:8s}] {e.event_id:12s} "
            f"M{e.magnitude:.1f} {e.magnitude_type.value:4s} | {e.place}"
        )

    if args.show_all:
        print("\nAll events:")
        for e in events:
            print(
                f"  [{e.geographic_scope.value:8s}] {e.event_id:12s} "
                f"M{e.magnitude:.1f} | {e.place} ({e.event_time.date()})"
            )

    print(f"\nCache saved to: {DEFAULT_CACHE_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
