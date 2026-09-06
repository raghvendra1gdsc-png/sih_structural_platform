# System Architecture & Technical Specifications

## 1. Architectural Overview

The **National Weather Big Data Analytics Platform** operates as a distributed, stream-oriented intelligence platform designed to process high-velocity weather observations across India. It bridges the gap between official meteorological instruments and crowdsourced citizen reports.

```
                  ┌────────────────────────────────────────┐
                  │          External Data Sources         │
                  │  ┌──────────────┐    ┌──────────────┐  │
                  │  │ Open-Meteo   │    │ Citizen Apps │  │
                  │  │ Weather Feed │    │ & Feeds      │  │
                  │  └──────┬───────┘    └──────┬───────┘  │
                  └─────────┼───────────────────┼──────────┘
                            │                   │
                            ▼                   ▼
                  ┌────────────────────────────────────────┐
                  │       Ingestion & Normalizer           │
                  │  - Coordinate validation               │
                  │  - UTC timestamp normalization         │
                  │  - Regional geocoding                  │
                  └───────────────────┬────────────────────┘
                                      │ NormalizedWeatherReport
                                      ▼
                  ┌────────────────────────────────────────┐
                  │       Asynchronous Worker Pipeline     │
                  │  (Celery + Redis Task Queue)           │
                  │                                        │
                  │  ┌──────────────────────────────────┐  │
                  │  │ Step 1: AI Category Classifier   │  │
                  │  ├──────────────────────────────────┤  │
                  │  │ Step 2: Spatiotemporal Dedup     │  │
                  │  ├──────────────────────────────────┤  │
                  │  │ Step 3: Source Trust Triage      │  │
                  │  ├──────────────────────────────────┤  │
                  │  │ Step 4: Incident Clustering      │  │
                  │  └──────────────────────────────────┘  │
                  └───────────────────┬────────────────────┘
                                      │
                                      ▼
                  ┌────────────────────────────────────────┐
                  │       PostgreSQL 15 + PostGIS 3.4      │
                  │  - Spatial indexes (GIST, SRID 4326)   │
                  │  - WeatherReportORM & IncidentORM      │
                  │  - Audit logs & deduplication graph    │
                  └───────────────────┬────────────────────┘
                                      │
                                      ▼
                  ┌────────────────────────────────────────┐
                  │             FastAPI REST API           │
                  │  - /api/reports, /api/incidents        │
                  │  - /api/stats/summary                  │
                  │  - /api/map/* (GeoJSON streams)        │
                  │  - /api/chat/weathergpt                │
                  └───────────┬────────────────┬───────────┘
                              │                │
            ┌─────────────────┘                └─────────────────┐
            ▼                                                    ▼
┌───────────────────────────────────────┐            ┌───────────────────────────────────────┐
│         Next.js 14 Dashboard          │            │            WeatherGPT Engine          │
│  - Real-time India Operations Map     │            │  - Grounded intent reasoning          │
│  - Live Hotspot Monitoring            │            │  - Numerical forecast synthesis       │
│  - Admin Verification Workbench       │            │  - IMD safety notices & citations     │
└───────────────────────────────────────┘            └───────────────────────────────────────┘
```

---

## 2. Core Subsystems

### 2.1 Ingestion & Normalization Layer
- **`ingestion/weather_provider.py`**: Interacts with Open-Meteo APIs for real-time and 7-day numerical forecasts. Uses an in-memory TTL cache and local persistent fallback cache (`data/sample_dataset/weather_cache.json`) for zero-dependency offline demo operations.
- **`ingestion/weather_normaliser.py`**: Validates report boundaries within Indian territorial extents (Lat 6°N–37.5°N, Lon 68°E–98°E). Standardizes ISO 8601 timestamps to UTC and resolves missing coordinates using district/city centroids.
- **`ingestion/synthetic_report_generator.py`**: Deterministic citizen report generator supporting customizable counts and seeds for repeatable demonstrations.

### 2.2 Machine Learning & Analytics Layer
- **AI Weather Event Classifier (`ml_pipeline/weather_classifier.py`)**: Calibrated NLP semantic classifier mapping observations into 12 weather categories:
  `rainfall`, `thunderstorm`, `flooding`, `heatwave`, `fog`, `dust_storm`, `strong_winds`, `cyclone`, `hailstorm`, `lightning`, `cold_wave`, `landslide`, and `other`.
- **Deduplication Engine (`ml_pipeline/weather_dedup.py`)**:
  - Uses Haversine spatial distance ($\le 3.5\text{ km}$).
  - Uses temporal delta window ($\le 90\text{ minutes}$).
  - Uses Jaccard word token similarity ($\ge 0.55$).
  - Links duplicate reports by setting `duplicate_of = canonical_report_id` while preserving original metadata.
- **Explainable Source Trust Engine (`ml_pipeline/trust_engine.py`)**: Computes a multi-factor score $[0, 100]$:
  $$\text{Score} = w_{\text{source}} + w_{\text{weather}} + w_{\text{geo}} + w_{\text{temp}} + w_{\text{corroboration}} + w_{\text{media}}$$
  Outputs clear human-readable verification rationales (`✓` checks, `⚠` warnings).
- **Incident Clustering Engine (`ml_pipeline/incident_clustering.py`)**:
  - Clusters canonical reports into geospatial hotspots within $12\text{ km}$ and $240\text{ minutes}$.
  - Calculates dynamic centroid and bounding radius.
  - Computes the **Platform-Derived Weather Impact Score** $[0, 100]$ mapping to `LOW`, `MODERATE`, `HIGH`, or `SEVERE`.

### 2.3 Persistence & Storage
- **PostgreSQL 15 + PostGIS 3.4**:
  - PostGIS geometry column `geometry = Column(Geometry("POINT", srid=4326), nullable=False)`.
  - Spatial indexes (`GIST`) for accelerated bounding box and radius queries using `ST_DWithin`.
  - Foreign key constraints connecting duplicates and audit records.

### 2.4 API & User Interface
- **FastAPI Backend (`backend/api/`)**: REST endpoints serving GeoJSON features, paginated reports, aggregated KPI statistics, and verification actions.
- **Next.js 14 Dashboard (`frontend/`)**: Modern React interface using Server-Side Rendering (SSR) and client-side map rendering via Leaflet.

---

## 3. Resilience & Offline Guarantee

The system is designed for high resilience:
1. **Network Fault Tolerance**: When external meteorological APIs are unreachable, the provider automatically falls back to cached data without throwing unhandled exceptions.
2. **Deterministic Demo Seeding**: `python -m demo.seed` seeds 500 reports, links duplicates, and generates clustered incidents in seconds.
3. **Container Isolation**: Docker Compose encapsulates all database, Redis, backend, worker, and frontend services in a dedicated bridge network.
