# National Weather Big Data Analytics Platform — REST API Reference

Base URL: `http://localhost:8000`  
Interactive OpenAPI Documentation: `http://localhost:8000/docs`

---

## 1. System Health & Diagnostics

### `GET /healthz`
Returns basic service and database readiness.
```json
{
  "status": "ok",
  "database": "connected",
  "postgis": true,
  "postgis_version": "3.4 USE_GEOS=1 USE_PROJ=1 USE_STATS=1"
}
```

### `GET /api/system/health`
Returns comprehensive subsystem telemetry for the dashboard navbar and monitoring.
```json
{
  "status": "healthy",
  "api": "online",
  "version": "1.0.0-sih-weather",
  "database": "connected",
  "postgis": "3.4 USE_GEOS=1 USE_PROJ=1 USE_STATS=1",
  "redis": "connected",
  "open_meteo_provider": "operational",
  "total_reports": 506,
  "active_incidents": 119
}
```

---

## 2. Weather Reports Ingestion & Querying

### `GET /api/reports`
Retrieve paginated weather reports with filtering.
- **Query Parameters**:
  - `city`: Filter by city name (e.g. `Jaipur`, `Mumbai`)
  - `state`: Filter by Indian state
  - `category`: Filter by `WeatherEventCategory` (`rainfall`, `flooding`, `thunderstorm`, etc.)
  - `verification_status`: `pending`, `verified`, `rejected`, `duplicate`, `needs_review`
  - `is_synthetic`: Filter by synthetic flag (`true`/`false`)
  - `limit`: Default `50` (1–100)
  - `offset`: Default `0`

### `POST /api/reports`
Ingest a new raw citizen or partner report.
```json
{
  "source": "citizen",
  "city": "Jaipur",
  "state": "Rajasthan",
  "latitude": 26.9124,
  "longitude": 75.7873,
  "text": "Severe waterlogging on MI Road, underpass is submerged.",
  "raw_category": "flooding",
  "is_synthetic": false
}
```

---

## 3. Geospatial Incident Hotspots

### `GET /api/incidents`
Retrieve clustered weather incidents with Platform-Derived Impact Scores.
- **Query Parameters**:
  - `city`: Filter by city
  - `category`: Filter by event category
  - `severity`: `low`, `moderate`, `high`, `severe`
  - `limit`: Default `50`
  - `offset`: Default `0`

### `GET /api/map/incidents`
Returns active incidents formatted as a standard GeoJSON `FeatureCollection` for direct ingestion into Leaflet, Mapbox, or QGIS.

### `GET /api/map/reports`
Returns canonical reports formatted as a standard GeoJSON `FeatureCollection`.

---

## 4. Real-Time Analytics & KPIs

### `GET /api/stats/summary`
Returns primary operations KPIs:
```json
{
  "total_reports": 506,
  "verified_reports": 113,
  "pending_reports": 335,
  "duplicate_reports": 35,
  "unique_incidents": 119,
  "high_impact_events": 42,
  "states_affected": 10
}
```

### `GET /api/stats/by-category`
Returns observation breakdown by weather category for Recharts distribution charts.

### `GET /api/stats/by-state`
Returns observation counts grouped by Indian state.

### `GET /api/stats/timeline`
Returns 24-hour observation velocity bucketed by hour.

### `GET /api/stats/source-reliability`
Returns quality metrics, verified ratios, and average trust scores grouped by source.

---

## 5. Admin Verification & Audit Trail

### `GET /api/admin/reports/pending`
Returns the queue of unverified citizen reports requiring human review.

### `PATCH /api/admin/reports/{report_id}/verification` (or `/verify`)
Approve, reject, or flag a report with a non-repudiable audit entry.
```json
{
  "status": "verified",
  "reason": "Corroborated by nearby municipal traffic camera feed",
  "reviewer": "duty_officer_1"
}
```

### `POST /api/admin/reports/{report_id}/merge`
Manually link a duplicate report to an existing canonical incident report.

### `GET /api/admin/audits`
Retrieve full immutable audit log of administrative actions.

---

## 6. Grounded WeatherGPT Assistant

### `POST /api/chat/weathergpt`
Query the grounded conversational weather intelligence engine.
```json
{
  "query": "Will it rain in Delhi tomorrow? Should I carry an umbrella?",
  "city": "Delhi"
}
```
Response includes synthesized answer, safety notices, structured sensor context, and data citations.
