# Big Data Analytics & Scalability Architecture

## 1. Workload Characteristics in Extreme Weather Events

During extreme meteorological events — such as the landfall of Cyclone Biparjoy or a monsoon cloudburst in Mumbai — the platform experiences extreme spikes in observation data:
- **Observation Velocity**: Bursts of $1,000–10,000$ citizen reports per minute.
- **Data Skew**: Intense concentration of reports in localized geographic clusters ($< 15\text{ km}$ radius).
- **High Concurrency**: Thousands of citizens and disaster management officials simultaneously querying maps and asking conversational intelligence questions.

To sustain this throughput without performance degradation, the platform incorporates a distributed, decoupled big data architecture.

---

## 2. Decoupled Ingestion & Processing

```
Incoming Reports (HTTP / Webhooks / Citizen Mobile App)
                        │
                        ▼
            ┌───────────────────────┐
            │   FastAPI Ingestion   │  (Stateless, sub-5ms response)
            └───────────┬───────────┘
                        │ Enqueue Task
                        ▼
            ┌───────────────────────┐
            │    Redis Task Queue   │  (In-memory buffer)
            └───────────┬───────────┘
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
┌──────────────────┐          ┌──────────────────┐
│ Celery Worker 1  │          │ Celery Worker 2  │  (Horizontal worker scaling)
│ - AI Category    │          │ - AI Category    │
│ - Trust Scoring  │          │ - Trust Scoring  │
└────────┬─────────┘          └────────┬─────────┘
         │                             │
         └──────────────┬──────────────┘
                        ▼
            ┌───────────────────────┐
            │  PostGIS Batch Insert │  (Optimized write transactions)
            └───────────────────────┘
```

1. **Non-Blocking Ingestion**: The API validates the raw payload against Pydantic schemas and immediately enqueues the processing job to Redis, returning an ingestion UUID in $< 5\text{ ms}$.
2. **Worker Elasticity**: Multiple Celery worker processes consume the queue concurrently. During high-velocity bursts, worker replicas can be scaled dynamically without modifying the database or API.

---

## 3. Spatial Indexing & Geospatial Query Optimization

### PostGIS GIST Indexing
Geographic points are indexed using Generalized Search Trees (`GIST`):
```sql
CREATE INDEX idx_weather_reports_geometry ON weather_reports USING gist (geometry);
CREATE INDEX idx_weather_incidents_geometry ON weather_incidents USING gist (geometry);
```

### Grid-Based Spatiotemporal Pruning
Pairwise deduplication across $N$ reports has a naive complexity of $\mathcal{O}(N^2)$. The platform reduces this to $\mathcal{O}(N)$ using spatial grid partitioning:
1. Divide the bounding box of India into $0.05^\circ \times 0.05^\circ$ spatial grid cells ($\approx 5.5\text{ km} \times 5.5\text{ km}$).
2. When evaluating a new observation, candidate canonical matches are queried **only from the host grid cell and its 8 immediate neighboring cells**.
3. Any report outside the 90-minute temporal buffer is automatically excluded by B-tree index on `event_time`.

---

## 4. Multi-Tier Caching Architecture

| Tier | Technology | TTL | Purpose |
|---|---|---|---|
| **L1: Process Memory** | Python dictionary | 60 seconds | Cache current weather parameters per city |
| **L2: Shared Cache** | Redis 7 | 5 minutes | Cache aggregated dashboard KPIs (`/api/stats/summary`) |
| **L3: Persistent Fallback**| JSON file on disk | Indefinite | Offline operation mode for air-gapped demo environments |

---

## 5. Horizontal Database Scaling Strategy (Roadmap)

For production deployment handling tens of millions of records annually:
1. **Time-Based Table Partitioning**: Partition `weather_reports` by month using PostgreSQL declarative table partitioning:
   ```sql
   CREATE TABLE weather_reports_2026_09 PARTITION OF weather_reports
   FOR VALUES FROM ('2026-09-01 00:00:00+00') TO ('2026-10-01 00:00:00+00');
   ```
2. **Read Replica Pools**: Distribute analytical read traffic (dashboard map queries and statistics) across read replicas with PgBouncer connection pooling.
3. **GeoJSON Vector Tiles**: For millions of concurrent map viewers, pre-render incident boundaries as Mapbox Vector Tiles (`MVT`) via `ST_AsMVT()`.
