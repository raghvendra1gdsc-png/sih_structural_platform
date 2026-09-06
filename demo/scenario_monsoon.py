"""
demo/scenario_monsoon.py
========================
MONSOON RAPID EVENT DEMO — Deterministic End-to-End Live Scenario

Demonstrates:
1. Sudden burst of heavy-rain reports arriving in Jaipur
2. AI classification recognizing torrential rainfall / urban flooding
3. Multimodal deduplication collapsing nearby duplicate reports
4. Geospatial spatiotemporal clustering into a high-impact weather incident
5. Platform Impact Score escalation (from baseline to SEVERE)
6. Emitting a RAPID WEATHER ESCALATION platform intelligence alert
7. Admin verification workflow approving ground truth reports
8. Grounded WeatherGPT conversational query answering with multi-source evidence

Usage:
    python -m demo.scenario_monsoon
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from backend.db.session import get_session
from backend.services.weather_gpt_service import WeatherGPTService
from backend.services.weather_incident_service import WeatherIncidentService
from backend.services.weather_report_service import WeatherReportService
from ingestion.weather_provider import INDIAN_CITIES
from ingestion.weather_schemas import RawWeatherReport, WeatherEventCategory, WeatherReportSource

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("scenario_monsoon")

JAIPUR_BURST_REPORTS = [
    {
        "district": "Civil Lines",
        "lat": 26.9112,
        "lon": 75.7891,
        "text": "Intense torrential cloudburst over Civil Lines! Main road submerged under 2 feet of water. Traffic paralyzed.",
    },
    {
        "district": "Civil Lines",
        "lat": 26.9125,
        "lon": 75.7880,
        "text": "Severe waterlogging near Civil Lines metro station. Water entering basements and ground shops.",
    },
    {
        "district": "Civil Lines",
        "lat": 26.9118,
        "lon": 75.7885,  # near-duplicate location & text
        "text": "Huge waterlogging on main road near Civil Lines, cars stuck in knee deep rain water.",
    },
    {
        "district": "C-Scheme",
        "lat": 26.9080,
        "lon": 75.7950,
        "text": "Deafening thunderstorm and blinding rain pounding C-Scheme. Power outage in entire sector.",
    },
    {
        "district": "C-Scheme",
        "lat": 26.9095,
        "lon": 75.7942,
        "text": "Heavy rain and thunder in C-Scheme. Tree branch fell on power lines.",
    },
    {
        "district": "Tonk Road",
        "lat": 26.8900,
        "lon": 75.8050,
        "text": "Tonk Road underpass completely submerged. Police putting up barricades. Avoid route!",
    },
]


def run_monsoon_scenario() -> None:
    print("\n" + "=" * 75)
    print("      SIH NATIONAL WEATHER PLATFORM — MONSOON RAPID EVENT DEMO")
    print("=" * 75)

    with get_session() as session:
        report_service = WeatherReportService(session)
        incident_service = WeatherIncidentService(session)
        gpt_service = WeatherGPTService(session)

        # Step 1: Ingesting rapid burst
        print("\n[STEP 1] Ingesting burst of citizen eyewitness reports in Jaipur...")
        ingested_records = []
        now = datetime.now(timezone.utc)

        for i, item in enumerate(JAIPUR_BURST_REPORTS, 1):
            raw = RawWeatherReport(
                report_id=uuid.uuid4(),
                source=WeatherReportSource.citizen,
                source_report_id=f"live_burst_{i}",
                submitted_at=now,
                event_time=now,
                city="Jaipur",
                state="Rajasthan",
                district=item["district"],
                latitude=item["lat"],
                longitude=item["lon"],
                text=item["text"],
                media_urls=[f"data/sample_dataset/images/monsoon_burst_{i}.jpg"] if i % 2 == 0 else [],
                hashtags=["#JaipurRain", "#Waterlogging", "#Alert"],
                is_synthetic=True,
            )
            orm = report_service.ingest_report(raw)
            ingested_records.append(orm)
            dup_tag = f" [DUPLICATE of {str(orm.duplicate_of)[:8]}]" if orm.duplicate_of else " [CANONICAL]"
            print(f"  ➜ Report #{i} | {orm.district} | Category: {orm.event_category} (conf: {orm.event_confidence:.2f}) | Trust: {orm.source_trust_score:.0f}/100{dup_tag}")
            time.sleep(0.15)

        # Step 2: Trigger clustering & impact score escalation
        print("\n[STEP 2] Clustering observations & escalating Platform Impact Score...")
        incident_count = incident_service.sync_incidents_from_reports()
        incidents, _ = incident_service.get_incidents(city="Jaipur", limit=1)
        if incidents:
            top_inc = incidents[0]
            print(f"  ✓ Created Incident Hotspot: {top_inc.incident_id}")
            print(f"  ✓ Affected Area: {top_inc.city} (Radius: {top_inc.radius_km} km)")
            print(f"  ✓ Aggregated Reports: {top_inc.report_count} citizen reports")
            print(f"  ✓ Platform Impact Score: {top_inc.impact_score:.0f}/100 ({top_inc.severity.upper()})")
            print(f"  ✓ Summary: {top_inc.summary}")

        # Step 3: Admin Verification Workflow
        print("\n[STEP 3] Admin Verification Center Action...")
        target_report = ingested_records[0]
        verified_orm = report_service.update_verification(
            report_id=target_report.report_id,
            new_status="verified",
            reason="Corroborated by multiple adjacent eyewitnesses and waterlogging images",
            reviewer="NDRF_Duty_Officer_04",
        )
        print(f"  ✓ Verified Report {target_report.report_id} by NDRF_Duty_Officer_04")
        print(f"  ✓ Status transitioned: {target_report.verification_status} ➔ VERIFIED")

        # Step 4: Query WeatherGPT
        print("\n[STEP 4] Querying WeatherGPT with Platform Intelligence Grounding...")
        question = "What weather events are active near Jaipur and is it safe to travel?"
        print(f"  User Query: \"{question}\"")
        resp = gpt_service.answer_question(question)
        print("\n  --- WeatherGPT Response ---")
        print(f"  {resp['answer']}")
        if resp.get("safety_notice"):
            print(f"\n  [Notice]: {resp['safety_notice']}")
        print("\n  --- Why this answer? (Citations) ---")
        for cit in resp["citations"]:
            print(f"  ✓ {cit}")

        print("\n" + "=" * 75)
        print("          MONSOON RAPID EVENT DEMO COMPLETED SUCCESSFULLY")
        print("=" * 75 + "\n")


if __name__ == "__main__":
    run_monsoon_scenario()
