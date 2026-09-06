# PostGIS Data Models & Database Schema

## 1. Relational & Spatial Database Schema

The database runs on **PostgreSQL 15** with the **PostGIS 3.4** spatial extension enabled. All spatial coordinates are stored using the **WGS 84 (SRID 4326)** standard coordinate reference system.

```
┌──────────────────────────────────────┐       ┌──────────────────────────────────────┐
│           weather_reports            │       │          weather_incidents           │
├──────────────────────────────────────┤       ├──────────────────────────────────────┤
│ id: UUID (PK)                        │       │ id: UUID (PK)                        │
│ report_id: UUID (Unique)             │       │ incident_id: UUID (Unique)           │
│ source: VARCHAR                      │       │ event_category: VARCHAR              │
│ source_report_id: VARCHAR            │       │ geometry: GEOMETRY(POINT, 4326)      │
│ submitted_at: TIMESTAMPTZ            │       │ centroid_lat: DOUBLE PRECISION       │
│ event_time: TIMESTAMPTZ              │       │ centroid_lon: DOUBLE PRECISION       │
│ city: VARCHAR                        │       │ start_time: TIMESTAMPTZ              │
│ state: VARCHAR                       │       │ end_time: TIMESTAMPTZ                │
│ district: VARCHAR                    │       │ report_count: INTEGER                │
│ country: VARCHAR                     │       │ verified_count: INTEGER              │
│ geometry: GEOMETRY(POINT, 4326)      │       │ severity: VARCHAR                    │
│ latitude: DOUBLE PRECISION           │       │ impact_score: DOUBLE PRECISION       │
│ longitude: DOUBLE PRECISION          │       │ confidence: DOUBLE PRECISION         │
│ text: TEXT                           │       │ city: VARCHAR                        │
│ media_urls: JSONB                    │       │ state: VARCHAR                       │
│ event_category: VARCHAR              │       │ radius_km: DOUBLE PRECISION          │
│ event_confidence: DOUBLE PRECISION   │       │ summary: TEXT                        │
│ verification_status: VARCHAR         │       │ created_at: TIMESTAMPTZ              │
│ source_trust_score: DOUBLE PRECISION │       │ updated_at: TIMESTAMPTZ              │
│ misinformation_score: DOUBLE PREC    │       └──────────────────────────────────────┘
│ trust_reasons: JSONB                 │
│ duplicate_of: UUID (FK -> report_id) │
│ is_synthetic: BOOLEAN                │
│ created_at: TIMESTAMPTZ              │
│ updated_at: TIMESTAMPTZ              │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│         verification_audits          │
├──────────────────────────────────────┤
│ id: UUID (PK)                        │
│ report_id: UUID (FK -> report_id)    │
│ previous_status: VARCHAR             │
│ new_status: VARCHAR                  │
│ reviewer: VARCHAR                    │
│ reason: TEXT                         │
│ created_at: TIMESTAMPTZ              │
└──────────────────────────────────────┘
```

---

## 2. Table Definitions

### 2.1 `weather_reports`
Primary storage for all raw and normalized observations.
- **`geometry`**: PostGIS Point with spatial indexing:
  ```sql
  CREATE INDEX idx_weather_reports_geometry ON weather_reports USING gist (geometry);
  ```
- **`duplicate_of`**: Self-referencing foreign key linking duplicate observations to their parent canonical report. Canonical reports have `duplicate_of = NULL`.
- **`verification_status`**: Enum string (`pending`, `verified`, `rejected`, `needs_review`, `duplicate`).
- **`trust_reasons`**: JSONB array storing transparent algorithmic scoring justifications.

### 2.2 `weather_incidents`
Represents clustered multi-report spatiotemporal weather hotspots.
- **`geometry`**: Centroid Point representation of the incident.
- **`radius_km`**: Geospatial buffer bounding the cluster of reports.
- **`impact_score`**: 0–100 score computed from volume velocity, category hazard, verification ratio, and spread.
- **`severity`**: Categorical classification: `low` ($\le 25$), `moderate` ($26–50$), `high` ($51–75$), and `severe` ($> 75$).

### 2.3 `verification_audits`
Audit log recording every human administrative action on incoming reports:
- Preserves `previous_status`, `new_status`, `reviewer`, timestamp, and rationale notes.

---

## 3. High-Performance Spatial Query Patterns

### Geospatial Proximity Search
Queries reports within a given radius using the PostGIS `ST_DWithin` function cast to `geography` for true geodetic meter calculations:
```sql
SELECT report_id, city, event_category, latitude, longitude
FROM weather_reports
WHERE ST_DWithin(
    geometry::geography,
    ST_SetSRID(ST_MakePoint(75.7873, 26.9124), 4326)::geography,
    15000 -- 15 km radius in meters
);
```

### Incident Bounding Box Filtering
Optimized bounding box queries for viewport map rendering:
```sql
SELECT incident_id, city, event_category, impact_score, severity
FROM weather_incidents
WHERE geometry && ST_MakeEnvelope(68.0, 6.0, 98.0, 37.5, 4326);
```
