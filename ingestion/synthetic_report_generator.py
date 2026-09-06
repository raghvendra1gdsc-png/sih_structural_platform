"""
ingestion/synthetic_report_generator.py
========================================
Generates realistic, deterministic citizen reports of weather events across Indian cities.

Rules & Integrity:
- Every generated record has is_synthetic = True
- Deterministic when --seed is supplied
- Labels demo data clearly
- Generates realistic Indian locations, timestamps, GPS jitter, hashtags, and text

Usage:
    python -m ingestion.synthetic_report_generator --count 500 --seed 42
    python -m ingestion.synthetic_report_generator --count 50 --output data/sample_dataset/synthetic_weather.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from ingestion.weather_provider import INDIAN_CITIES
from ingestion.weather_schemas import (
    RawWeatherReport,
    WeatherEventCategory,
    WeatherReportSource,
)

logger = logging.getLogger(__name__)

# Weather text templates tailored for Indian cities
WEATHER_TEMPLATES: dict[WeatherEventCategory, list[str]] = {
    WeatherEventCategory.rainfall: [
        "Heavy rain since 6:30 PM near {area}, roads are beginning to flood with knee-deep water.",
        "Continuous torrential downpour here in {area}. Waterlogging on main road, traffic stalled.",
        "Intense monsoon showers pounding {city} for the last 2 hours. Drains overflowing in {area}.",
        "Moderate rain with overcast sky near {area}. Commuters taking shelter under flyovers.",
        "Sudden cloudburst-like rain in {area}. Visibility dropped significantly.",
    ],
    WeatherEventCategory.thunderstorm: [
        "Violent thunderstorm with deafening lightning strikes near {area}. Power grid tripped.",
        "Massive thunder and continuous lightning flashes across {city} skyline. Stay indoors!",
        "Severe squall and thunder shaking window panes in {area}. Strong downdrafts.",
        "Thunderstorm accompanied by heavy gale force winds near {area}. Several trees uprooted.",
    ],
    WeatherEventCategory.flooding: [
        "Severe waterlogging and urban flooding in {area}. Vehicles submerged up to bonnet level.",
        "Basements getting flooded in residential society near {area}. Municipal pumps needed urgently.",
        "River overflowing near low-lying pockets of {city}. Water entering ground floor houses.",
        "Underpass in {area} completely submerged. Police barricades placed, traffic diverted.",
    ],
    WeatherEventCategory.heatwave: [
        "Extreme scorching heatwave in {city}. Temperature display at junction showing 46.5°C.",
        "Severe heatwave condition, hot loo winds blowing across {area}. Streets deserted this afternoon.",
        "Unbearable heat in {area}. Heat index feels well above 48°C. Stay hydrated everyone.",
        "Government issued red alert for heatwave in {city}. Hospital ER reporting heat exhaustion cases.",
    ],
    WeatherEventCategory.dust_storm: [
        "Massive wall of dust storm engulfing {area}. Visibility zero, headlights barely visible.",
        "Severe andhi / dust storm swept across {city}. Blinding dust and debris flying everywhere.",
        "High-velocity dust squall hit {area}. Billboard collapsed on service lane.",
    ],
    WeatherEventCategory.strong_winds: [
        "Gale-force gusty winds blowing over {area}. Tin roofs rattling and branches snapping.",
        "Extremely strong winds uprooting roadside hoardings in {city}. Wind gusts over 65 km/h.",
        "Winds howling through high-rise balconies in {area}. Power cables sparking.",
    ],
    WeatherEventCategory.cyclone: [
        "Outer bands of cyclonic storm hitting coastal {city}. Roaring winds and relentless storm surge.",
        "Cyclone alert sirens sounding along coastal {area}. Heavy sea wave intrusion reported.",
        "Destructive cyclonic squall battering {area}. Trees down across arterial avenues.",
    ],
    WeatherEventCategory.hailstorm: [
        "Intense hailstorm striking {area}! Golf-ball sized hailstones damaging car windshields.",
        "Sudden heavy hail shower whiteout in {city}. Streets covered in white ice pellets.",
        "Severe hailstones pelting crops and tin roofs in outskirts of {city}.",
    ],
    WeatherEventCategory.fog: [
        "Dense fog sheet blanketing {area}. Visibility under 25 meters on highway.",
        "Zero visibility dense smog/fog at airport and ring road in {city}. Flights delayed.",
        "Thick pea-soup fog morning in {area}. Vehicles moving in slow crawl with hazard lights.",
    ],
    WeatherEventCategory.lightning: [
        "Intense continuous cloud-to-ground lightning near {area}. Transformer exploded nearby.",
        "Dangerous lightning strikes observed in open fields near {city}. Warning issued for farmers.",
    ],
    WeatherEventCategory.cold_wave: [
        "Severe cold wave condition in {city}. Dense fog and piercing cold winds, temp dropped to 3°C.",
        "Record-breaking chill in {area}. People lighting bonfires on pavements to survive the night.",
    ],
    WeatherEventCategory.landslide: [
        "Mudslide and rockfall triggered by torrential rain blocking bypass near {area}.",
        "Debris flow and landslide washing out road stretch in hilly sector of {city}.",
    ],
    WeatherEventCategory.other: [
        "Rapid weather shift in {city}. Sky turned dark within minutes over {area}.",
        "Unusual barometric pressure drop and sudden weather turmoil reported in {area}.",
    ],
}

LOCAL_AREAS: dict[str, list[str]] = {
    "Jaipur": ["Civil Lines", "Malviya Nagar", "Vaishali Nagar", "C-Scheme", "Mansarovar", "Amer Road", "Tonk Road"],
    "Jodhpur": ["Ratanada", "Sardarpura", "Shastri Nagar", "Paota", "Mandore", "Pal Road"],
    "Delhi": ["Connaught Place", "Ring Road", "Rohini", "Saket", "Dwarka", "Lajpat Nagar", "Karol Bagh"],
    "Mumbai": ["Andheri Subway", "Dadar TT", "Bandra Kurla Complex", "Colaba", "Borivali West", "Kurla"],
    "Chennai": ["T. Nagar", "Velachery", "Adyar", "Anna Nagar", "Marina Beach Road", "Tambaram"],
    "Kolkata": ["Park Street", "Salt Lake Sector V", "Howrah Bridge", "Ballygunge", "New Town", "Esplanade"],
    "Bengaluru": ["Koramangala", "Indiranagar", "Silk Board", "Whitefield", "Hebbal", "MG Road"],
    "Hyderabad": ["Hitec City", "Banjara Hills", "Secunderabad", "Gachibowli", "Charminar", "Jubilee Hills"],
    "Guwahati": ["Paltan Bazaar", "GS Road", "Khanapara", "Dispur", "Ulubari", "Fancy Bazaar"],
    "Ahmedabad": ["SG Highway", "Navrangpura", "Maninagar", "Vastrapur", "Ashram Road", "Satellite"],
    "Lucknow": ["Hazratganj", "Gomti Nagar", "Alambagh", "Indira Nagar", "Charbagh", "Aminabad"],
    "Kochi": ["Marine Drive", "MG Road", "Edappally", "Kakkanad", "Fort Kochi", "Palarivattom"],
}

DEMO_HASHTAGS = [
    "#WeatherAlert", "#Monsoon", "#IndiaWeather", "#HeavyRain", "#Alert",
    "#TrafficAlert", "#Waterlogging", "#Thunderstorm", "#UrbanFlood",
]


def generate_synthetic_reports(
    count: int = 500,
    seed: int = 42,
    base_time: Optional[datetime] = None,
) -> list[RawWeatherReport]:
    """
    Generate a deterministic list of synthetic citizen weather reports.
    """
    rng = random.Random(seed)
    if base_time is None:
        base_time = datetime(2026, 9, 4, 18, 30, tzinfo=timezone.utc)

    city_names = list(INDIAN_CITIES.keys())
    categories = list(WEATHER_TEMPLATES.keys())
    
    # Weight rainfall, thunderstorm, and flooding higher for monsoon demo
    cat_weights = [
        30 if c in (WeatherEventCategory.rainfall, WeatherEventCategory.thunderstorm, WeatherEventCategory.flooding)
        else 8 if c in (WeatherEventCategory.dust_storm, WeatherEventCategory.strong_winds, WeatherEventCategory.heatwave)
        else 4
        for c in categories
    ]

    reports: list[RawWeatherReport] = []

    for i in range(count):
        # Pick city
        # Give Jaipur and Jodhpur slightly higher frequency for demo scenario
        if i % 5 == 0:
            city = "Jaipur"
        elif i % 7 == 0:
            city = "Jodhpur"
        else:
            city = rng.choice(city_names)

        city_info = INDIAN_CITIES[city]
        state = city_info["state"]
        areas = LOCAL_AREAS.get(city, ["Central District", "Station Road", "Market Area"])
        area = rng.choice(areas)

        category = rng.choices(categories, weights=cat_weights, k=1)[0]
        template = rng.choice(WEATHER_TEMPLATES[category])
        text = template.format(city=city, area=area)

        # Apply realistic GPS jitter (~500m to 3km)
        jitter_lat = rng.uniform(-0.025, 0.025)
        jitter_lon = rng.uniform(-0.025, 0.025)
        lat = round(city_info["lat"] + jitter_lat, 5)
        lon = round(city_info["lon"] + jitter_lon, 5)

        # Time within past 6 hours
        offset_minutes = rng.randint(0, 360)
        report_time = base_time - timedelta(minutes=offset_minutes)

        # Media and hashtags
        has_media = rng.random() < 0.4
        media_urls = [f"data/sample_dataset/images/weather_{city.lower()}_{i%10}.jpg"] if has_media else []
        tags = rng.sample(DEMO_HASHTAGS, k=rng.randint(1, 3))

        source = rng.choices(
            [WeatherReportSource.synthetic, WeatherReportSource.citizen, WeatherReportSource.community_feed],
            weights=[60, 25, 15],
            k=1,
        )[0]

        report = RawWeatherReport(
            report_id=uuid.UUID(int=rng.getrandbits(128)),
            source=source,
            source_report_id=f"syn_{city[:3].lower()}_{seed}_{i:04d}",
            submitted_at=report_time,
            event_time=report_time,
            city=city,
            state=state,
            district=area,
            country="India",
            latitude=lat,
            longitude=lon,
            text=text,
            media_urls=media_urls,
            hashtags=tags,
            raw_category=category.value,
            is_synthetic=True,  # ALWAYS True for synthetic records
        )
        reports.append(report)

    # Sort deterministically by event time descending
    reports.sort(key=lambda r: r.submitted_at, reverse=True)
    return reports


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic Weather Citizen Report Generator")
    parser.add_argument("--count", type=int, default=500, help="Number of reports to generate")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for reproducibility")
    parser.add_argument("--output", type=str, default=None, help="Optional output JSONL file path")
    args = parser.parse_args()

    reports = generate_synthetic_reports(count=args.count, seed=args.seed)
    logger.info("Generated %d synthetic weather reports with seed %d", len(reports), args.seed)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            for r in reports:
                f.write(r.model_dump_json() + "\n")
        print(f"Wrote {len(reports)} records to {args.output}")
    else:
        for r in reports[:5]:
            print(r.model_dump_json())
        print(f"... ({len(reports) - 5} more records generated)")


if __name__ == "__main__":
    main()
