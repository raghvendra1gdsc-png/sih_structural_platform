# 🌦️ National Weather Big Data Analytics Platform

> **Smart India Hackathon (SIH) 2026 — Disaster & Meteorological Intelligence MVP**  
> A high-throughput, AI-driven weather big data analytics platform for real-time ingestion, multimodal NLP classification, spatial deduplication, explainable misinformation triage, geospatial incident clustering, and grounded conversational intelligence.

---

## 📌 Executive Summary

India experiences extreme and localized meteorological events across vast geographic terrains — ranging from urban monsoon cloudbursts and flash floods in Mumbai and Delhi, to convective dust storms (*andhi*) across Rajasthan, and severe cyclonic storms along coastal belts. 

Traditional meteorological monitoring faces severe operational bottlenecks during rapid weather events:
1. **Sensor Sparsity & Latency**: Doppler radar and Automatic Weather Stations (AWS) have spatial blind spots and delayed reporting cycles.
2. **Citizen Data Overload & Duplication**: Social media and emergency hotlines are inundated with thousands of redundant, unverified reports of the same localized waterlogging or fallen tree.
3. **Misinformation & Fake Outrage**: Outdated storm footage or fabricated panic posts circulate during weather crises without transparent verification.
4. **Actionability Gap**: Citizen observations are rarely converted into clustered geospatial incident hotspots with quantitative impact scores.

The **National Weather Big Data Analytics Platform** resolves these challenges through a unified real-time architecture:
- **Multi-Source Ingestion**: Ingests automated meteorological observations (Open-Meteo zero-key API, cached for offline resilience) and citizen/community eyewitness feeds.
- **AI Weather Event Classification**: Triages reports into 12 canonical Indian weather categories using a calibrated NLP semantic parser and zero-shot model.
- **Spatial-Temporal Multimodal Deduplication**: Identifies redundant reports within a 3.5 km and 90-minute spatiotemporal window, linking duplicates to a canonical report (`duplicate_of`).
- **Explainable Trust & Misinformation Triage Engine**: Computes transparent 0–100 credibility scores with human-readable rationale tags (`✓` corroborations, `⚠` warnings).
- **Geospatial Incident Clustering & Platform Impact Scoring**: Aggregates canonical reports into spatial hotspots, calculating bounding radius, centroid, and a 0–100 Platform-Derived Weather Impact Score (`LOW`, `MODERATE`, `HIGH`, `SEVERE`).
- **Next.js Command Operations Dashboard**: Real-time Leaflet India map, live event stream, administrative verification workbench, and analytics charts consuming **100% live database data** (zero hardcoded numbers).
- **Grounded WeatherGPT**: Conversational weather assistant strictly anchored in numerical forecast models and PostGIS database records, with citation references, safety notices, and an explainable evidence drawer.

---

## 🏗️ System Architecture

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                DATA INGESTION LAYER                                    │
│  ┌──────────────────────────────┐        ┌──────────────────────────────────────────┐  │
│  │   Automated Weather API      │        │  Citizen & Community Multi-Stream Feeds  │  │
│  │   (Open-Meteo zero-key feed) │        │  (Deterministic synthetic generator)     │  │
│  │   Offline cache fallback     │        │  (is_synthetic=True, 12 Indian metros)   │  │
│  └──────────────┬───────────────┘        └────────────────────┬─────────────────────┘  │
└─────────────────┼─────────────────────────────────────────────┼────────────────────────┘
                  │ RawWeatherReport                            │ RawWeatherReport
                  └──────────────────────┬──────────────────────┘
                                         ▼
                   ┌───────────────────────────────────────────┐
                   │    Canonical Weather Normalizer Layer     │
                   │    (UTC timestamps, Geocoding, Bounds)    │
                   └─────────────────────┬─────────────────────┘
                                         │ NormalizedWeatherReport
                                         ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                           AI & ANALYTICS PIPELINE                                      │
│  ┌────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐  │
│  │  AI Weather Classifier │  │ Spatial-Temporal Dedup  │  │  Explainable Trust &    │  │
│  │  12 Weather Categories │  │ Haversine dist <= 3.5km │  │  Misinformation Engine  │  │
│  │  Confidence calibration│  │ Time window <= 90 mins  │  │  0-100 Score + Reasons  │  │
│  │  Regional dialect terms│  │ Links duplicate_of FK   │  │  ✓ Endorsements, ⚠ Warns│  │
│  └───────────┬────────────┘  └────────────┬────────────┘  └────────────┬────────────┘  │
└──────────────┼────────────────────────────┼────────────────────────────┼───────────────┘
               └────────────────────────────┼────────────────────────────┘
                                            ▼
                      ┌───────────────────────────────────────────┐
                      │    Geospatial Incident Clustering Engine  │
                      │    (Hotspot grouping, Centroid, Radius)   │
                      │    Platform Impact Score [0–100]          │
                      │    (LOW, MODERATE, HIGH, SEVERE)          │
                      └─────────────────────┬─────────────────────┘
                                            │
                                            ▼
                      ┌───────────────────────────────────────────┐
                      │       PostgreSQL 15 + PostGIS 3.4         │
                      │       (Spatial indexes GIST, SRID 4326)   │
                      │       WeatherReportORM, IncidentORM       │
                      └─────────────────────┬─────────────────────┘
                                            │
                                            ▼
                      ┌───────────────────────────────────────────┐
                      │          FastAPI REST API Layer           │
                      │          Pydantic v2 Schemas, Docs        │
                      └─────────────┬───────────────┬─────────────┘
                                    │               │
            ┌───────────────────────┘               └───────────────────────┐
            ▼                                                               ▼
┌───────────────────────────────────────┐               ┌───────────────────────────────────────┐
│       Next.js 14 Web Dashboard        │               │       Grounded WeatherGPT Engine      │
│  - Real-time India Leaflet Map        │               │  - Intent & Location Extraction       │
│  - Live Clustered Weather Hotspots    │               │  - Verified DB Ground Truth           │
│  - Admin Verification Workbench       │               │  - Citation References & Disclaimers  │
│  - Big Data Analytics & KPIs          │               │  - Explainable Evidence Drawer        │
└───────────────────────────────────────┘               └───────────────────────────────────────┘
```

---

## 🛠️ Technology Stack

| Layer | Technology | Purpose / Specification |
|---|---|---|
| **Backend Framework** | FastAPI 0.115+ | High-performance asynchronous REST API with automatic OpenAPI docs |
| **Data Validation** | Pydantic v2 | Canonical data schemas (`RawWeatherReport`, `NormalizedWeatherReport`, `WeatherIncidentSchema`) |
| **Geospatial Database** | PostgreSQL 15 + PostGIS 3.4 | Geospatial indexing (`GIST`), `ST_DWithin`, centroid calculations (SRID 4326) |
| **ORM & Migrations** | SQLAlchemy 2.0 + GeoAlchemy2 + Alembic | Type-safe database persistence with idempotent Alembic migrations |
| **Task Queue & Cache**| Celery + Redis 7 | Asynchronous batch ingestion and distributed task scheduling |
| **AI / NLP Engine** | Zero-Shot NLP Classifier + OpenCLIP | 12 weather categories, confidence scoring, Indian dialect support (*andhi*, *loo*, *barish*) |
| **Deduplication** | Haversine + Token Jaccard | 3.5 km spatial radius, 90-min temporal window, token overlap threshold |
| **Trust Triage** | Multi-Factor Algorithmic Scorer | Transparent 0–100 trust scoring with human-readable rationale tags |
| **Frontend Framework**| Next.js 14 (App Router) + React 18 | Production SSR dashboard, Dark mode glassmorphism UI |
| **Geospatial Map** | Leaflet + React-Leaflet | Custom dark cartographic tiles, incident ripple markers, severity circles |
| **Data Visualization**| Recharts + Lucide Icons | Category distribution bar charts, 24h timeline velocity, source reliability |
| **Containerization** | Docker Compose | Single-command multi-container stack (`db`, `redis`, `backend`, `worker`, `frontend`) |

---

## 🚀 Quick Start Guide

### Prerequisites
- Docker & Docker Compose
- Python 3.10+ (for local host test runner)
- Node.js 18+ (for local frontend development)

### 1. Clone & Configure
```bash
git clone https://github.com/your-org/sih_structural_platform.git
cd sih_structural_platform
cp .env.example .env
```

### 2. Start Full Stack with Docker Compose
```bash
docker compose up --build
```
This builds and starts:
- **PostgreSQL + PostGIS**: `localhost:5432`
- **Redis**: `localhost:6379`
- **FastAPI Backend**: `http://localhost:8000` (Swagger UI at `/docs`)
- **Next.js Dashboard**: `http://localhost:3000`

### 3. Seed Realistic Indian Weather Dataset
In a separate terminal, seed 500 reports across 12 Indian metropolitan hubs:
```bash
python -m demo.seed --count 500 --seed 42
```
This automatically runs the end-to-end pipeline:
1. Simulates multi-source citizen submissions across Delhi, Mumbai, Jaipur, Jodhpur, Chennai, Kolkata, Bengaluru, Hyderabad, Guwahati, Ahmedabad, Lucknow, and Kochi.
2. Ingests real meteorological forecasts from Open-Meteo.
3. Classifies reports with AI into canonical categories.
4. Identifies duplicate submissions and links `duplicate_of`.
5. Evaluates trust and generates explainability reasons.
6. Clusters canonical reports into geospatial `WeatherIncident` hotspots with Platform Impact Scores.

---

## 🎬 Live SIH Demo Scenarios

### Scenario A: Jaipur Rapid Monsoon Cloudburst
Simulates a live rapid-onset flash flood event in Jaipur with sudden report surges:
```bash
python -m demo.scenario_monsoon
```
**What Happens**:
1. **Burst Ingestion**: Ingests 6 clustered eyewitness reports from MI Road, Ajmer Road, and Sindhi Camp reporting flash flooding.
2. **AI Classification**: Reports are classified as `flooding` and `rainfall` with >85% confidence.
3. **Deduplication**: Secondary reports from adjacent coordinates within 15 minutes are linked as duplicates.
4. **Hotspot Clustering**: Centroid computed around `[26.9124°N, 75.7873°E]`, impact score reaches `HIGH (74/100)`.
5. **Admin Review**: Shows pending review status, then simulates administrator one-click approval with audit log.
6. **WeatherGPT Q&A**: Queries WeatherGPT: *"Should I carry an umbrella in Jaipur tomorrow?"* — returns grounded advice citing active ground incidents.

### Scenario B: Offline Demonstration Mode
The platform is **100% offline runnable** for presentations where conference Wi-Fi is unreliable.
All meteorological feeds for the 12 target cities are pre-cached in `data/sample_dataset/weather_cache.json`.
When offline, the system gracefully reads the local cache without network timeouts or crashes.

---

## 🖥️ Command Operations Dashboard

Access the web interface at **`http://localhost:3000`**:

| Route | Feature | Key Capabilities |
|---|---|---|
| **`/dashboard`** | **National Command Center** | - Real-time KPI metrics (Total Reports, Verified, Active Hotspots, States)<br>- Interactive dark Leaflet map of India with severity rings and pulsing incident clusters<br>- Live incoming observation stream with trust badges (`High Trust`, `Suspect`)<br>- Recharts category distribution and 24h event volume timeline |
| **`/admin`** | **Verification Workbench** | - Human-in-the-loop review queue for pending citizen reports<br>- Detailed transparent trust breakdown (Source reliability, Radar consistency, Spatial check, Corroboration)<br>- One-click actions: **Verify**, **Reject**, or **Flag for Review**<br>- Real-time non-repudiable audit trail with reviewer timestamps |
| **`/weathergpt`** | **Conversational Intelligence** | - Natural language query interface with suggested prompts<br>- Grounded answers synthesizing numerical forecast + active PostGIS incident data<br>- Mandatory IMD marine safety disclaimers<br>- Expandable *"Why this answer?"* context drawer revealing raw sensor values and citations |
| **`/analytics`** | **Big Data Telemetry** | - Data pipeline throughput and end-to-end latency benchmarks<br>- Source reliability audit table (API vs Citizen vs Community feeds)<br>- Deduplication efficiency and false-positive triage metrics |

---

## 🤖 Grounded WeatherGPT Engine

WeatherGPT is designed with **zero hallucination guardrails**:
- **Location & Intent Extraction**: Automatically resolves Indian cities (Mumbai, Jaipur, Delhi, Bengaluru, etc.) and question intents (`precipitation`, `wind`, `marine_safety`, `travel_advisory`).
- **Dual Grounding**: Combines physical meteorological model output (temperature, precipitation probability, gusts) with live PostGIS ground-truth incidents.
- **Explicit Safety Disclaimers**: Whenever marine safety is queried, prepends an official India Meteorological Department (IMD) / Port Authority advisory disclaimer.
- **Traceable Citations**: Cites the exact coordinates, sensor model, and verified incident counts backing every answer.

---

## 🧪 Comprehensive Automated Test Suite

The platform includes a robust suite of **50 automated tests** covering all schemas, ML engines, clustering algorithms, and REST APIs:

```bash
pytest tests/test_weather_*.py tests/test_trust_engine.py tests/test_incident_clustering.py -v
```

### Test Coverage Highlights:
- `tests/test_weather_schemas.py`: Pydantic v2 schema validations, boundary checks, and enum handling.
- `tests/test_weather_classifier.py`: 12 weather categories, confidence calibration, regional terminology (*andhi*, *loo*, *kohra*).
- `tests/test_weather_dedup.py`: Haversine distance, token similarity, spatial and temporal bounds.
- `tests/test_trust_engine.py`: 0–100 trust scoring, radar consistency checks, explainability tags (`✓`, `⚠`).
- `tests/test_incident_clustering.py`: Spatiotemporal clustering, centroid calculation, impact score thresholds.
- `tests/test_weather_gpt.py`: Grounding pipeline, location extraction, IMD marine safety notice.
- `tests/test_weather_api.py`: FastAPI integration tests for `/healthz`, `/api/reports`, `/api/incidents`, `/api/stats/summary`, `/api/map/*`, and admin verification.

---

## ⚖️ Scientific & Data Integrity Rules

1. **Synthetic Data Transparency**: All simulated citizen observations are explicitly flagged with `is_synthetic = True` and clearly labeled in the user interface.
2. **Deterministic Reproducibility**: The synthetic report generator produces identical datasets when executed with the same `--seed`.
3. **No Hardcoded Dashboard Statistics**: Every number, chart point, and metric rendered in the frontend originates from an active database query or API endpoint.
4. **Explainable Algorithmic Decisions**: All trust ratings and deduplication links record explicit, human-readable rationale logs for auditing.
5. **Strict Grounding**: Conversational intelligence answers only using verified database records and meteorological forecasts, never hallucinating unverified weather claims.

---

## 👥 Authors & Acknowledgments

- **Smart India Hackathon 2026 Team**
- Meteorological data provided by Open-Meteo under Creative Commons Attribution 4.0.
- Built with FastAPI, PostgreSQL, PostGIS, Next.js, Leaflet, and Tailwind CSS.
