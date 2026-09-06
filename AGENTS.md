# AGENTS.md — Disaster Structural Intelligence Platform
## Project Constitution v0.1  ·  SIH Hackathon 2026

> **This file is the authoritative rulebook for every human and AI agent working on this
> codebase. All phases must comply. No exceptions without an explicit version bump and
> team sign-off.**

---

## 1. Project Purpose

Build a 4-day hackathon MVP that:

1. Ingests multi-source disaster reports (USGS earthquake feed + synthetic citizen
   reports; Reddit optional).
2. Normalises and deduplicates reports into a canonical schema.
3. Classifies structural damage using CLIP zero-shot image understanding.
4. Stores results in PostgreSQL + PostGIS with full geospatial indexing.
5. Exposes a FastAPI backend with structured REST endpoints.
6. Renders a Next.js dashboard that consumes **only** real backend data — no
   hardcoded statistics.
7. Provides an admin verification panel for human-in-the-loop review.

**Target domain:** India — historical and near-real-time earthquake events.

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  Data Sources                                                        │
│  ┌─────────────┐  ┌───────────────────┐  ┌──────────────────────┐   │
│  │ USGS GeoJSON│  │ Synthetic Reports │  │ Reddit (optional)    │   │
│  │ Earthquake  │  │ Generator         │  │ r/india / r/news     │   │
│  │ Feed        │  │ (is_synthetic=T)  │  │ PRAW, rate-limited   │   │
│  └──────┬──────┘  └────────┬──────────┘  └──────────┬───────────┘   │
│         │                  │                         │               │
│         └──────────────────┴─────────────────────────┘               │
│                            │ RawReport                                │
│                     ┌──────▼──────┐                                  │
│                     │ Normaliser  │  (ingestion layer)               │
│                     └──────┬──────┘                                  │
│                            │ NormalizedReport                         │
│              ┌─────────────┼────────────────┐                        │
│              │             │                │                        │
│       ┌──────▼──────┐ ┌────▼───────┐ ┌─────▼──────────┐            │
│       │ Dedup Engine│ │ CLIP Damage│ │ Trust / Verif. │            │
│       │ (Phase 2)   │ │ Classifier │ │ Scorer         │            │
│       └──────┬──────┘ │ (Phase 3)  │ └─────┬──────────┘            │
│              │         └────┬───────┘       │                        │
│              └──────────────┴───────────────┘                        │
│                            │                                         │
│                     ┌──────▼──────┐                                  │
│                     │  PostGIS DB │  (PostgreSQL 15 + PostGIS 3.4)  │
│                     └──────┬──────┘                                  │
│                            │                                         │
│                     ┌──────▼──────┐                                  │
│                     │  FastAPI    │  (Phase 4)                       │
│                     └──────┬──────┘                                  │
│                            │                                         │
│              ┌─────────────┼───────────────┐                         │
│       ┌──────▼──────┐              ┌────────▼───────┐               │
│       │ Next.js     │              │ Admin Panel    │               │
│       │ Dashboard   │              │ (Phase 6)      │               │
│       │ (Phase 5)   │              └────────────────┘               │
│       └─────────────┘                                               │
└──────────────────────────────────────────────────────────────────────┘

Supporting infrastructure: Redis (Celery task queue), Docker Compose
```

---

## 3. Phase Gates

Each phase must be complete, tested, and merged before the next begins.

| Phase | Deliverable | Done When |
|-------|-------------|-----------|
| **0** | Schemas, synthetic generator, Docker Compose | `python -m ingestion.synthetic_report_generator --count 50 --seed 42` produces valid JSONL; `docker compose config` passes |
| **1** | USGS live ingestion + normaliser | Live USGS events stored in PostGIS; offline fallback dataset works |
| **2** | Deduplication engine | Duplicate synthetic reports are merged; `duplicate_of` FK populated |
| **3** | CLIP zero-shot damage classifier | damage_type + severity populated from model; validated against ≥ 50 labelled samples from xBD |
| **4** | FastAPI backend | All dashboard endpoints return real DB data; Swagger UI passes manual smoke test |
| **5** | Next.js dashboard | Every visible statistic originates from a backend API call; no hardcoded values |
| **6** | Admin verification panel | Admin can approve/reject/merge reports via UI; status reflected in DB |
| **7** | Demo dataset + docs + rehearsal | `docker compose up --build` starts cleanly; offline demo runs with sample dataset |

**Gate rule:** A phase is not complete unless its explicit tests/smoke checks pass and
are documented in the PR or commit message.

---

## 4. Technology Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| Language | Python 3.10+ | |
| Schemas | Pydantic v2 | All inter-module data exchange |
| Database | PostgreSQL 15 + PostGIS 3.4 | Via Docker |
| ORM | SQLAlchemy 2.x + GeoAlchemy2 | |
| Migrations | Alembic | |
| Task queue | Celery + Redis | |
| Backend API | FastAPI | |
| ML | OpenCLIP (open-clip-torch) | Zero-shot; no fine-tuning in v1 |
| Frontend | Next.js (App Router) | |
| Container | Docker Compose | Single `docker compose up --build` |
| Testing | pytest | |
| Linting | ruff + mypy | |

---

## 5. Data-Source Rules

### 5.1 USGS Earthquake Feed
- **URL:** `https://earthquake.usgs.gov/fdsnws/event/1/query`
- **Format:** GeoJSON
- **Required fields:** `id`, `properties.mag`, `properties.magType`,
  `geometry.coordinates`, `properties.place`, `properties.time`, `properties.url`
- Every USGS event must retain its original `event_id` and `url` verbatim.
- Cache selected events to `data/sample_dataset/usgs_cache.json` for offline use.
- USGS failures must **not** crash the application. Log the error, raise a
  `DataSourceUnavailableError`, and allow the caller to fall back to cached data.
- Do **not** silently convert a failed real-data fetch into fabricated "real" events.

### 5.2 Synthetic Citizen Reports
- Generated by `ingestion/synthetic_report_generator.py`.
- **Every** synthetic record must have `is_synthetic = True`.
- Synthetic reports must reference a real USGS `earthquake_event_id` obtained from
  the live feed or from the cached sample dataset.
- Synthetic reports must never be presented to end-users or in dashboards as real
  citizen reports without clear UI labelling ("SYNTHETIC — DEMO DATA").
- The generator must be deterministic when `--seed N` is supplied.

### 5.3 Reddit (Optional)
- Use PRAW. Never use an unofficial scraper.
- Reddit integration must never block other phases if PRAW credentials are absent.
- Mark all Reddit-sourced records with `source = "reddit"`.

### 5.4 Prohibited Sources
- **No X/Twitter API** — API pricing and reliability make it unsuitable for this demo.
- **No Sentinel Hub** — licensing and download volume are incompatible with hackathon constraints.
- **No NCS (National Centre for Seismology) direct feed** — no stable public API.
- **No FNO (Forecast Notification Office) integration** — deferred to v2.

---

## 6. Testing Requirements

- All Pydantic models must be exercised with at least one valid and one invalid
  fixture in `tests/test_schemas.py`.
- `synthetic_report_generator.py` must be tested for:
  - Correct record count (`--count N`).
  - Determinism under the same seed.
  - `is_synthetic=True` on every record.
  - Valid `earthquake_event_id` (must appear in the USGS cache or live response).
  - Schema validity (every record must parse as `RawReport`).
- Every FastAPI endpoint must have at least one happy-path test and one error-path test.
- CLIP classifier must be benchmarked against a labelled sample before any accuracy
  claim appears in documentation or the dashboard.
- **Do not claim tests passed unless you actually executed them and observed the output.**

---

## 7. Scientific / Data-Integrity Rules

1. **Never fabricate validation accuracy.** If CLIP has not been benchmarked, the
   dashboard must show "Model accuracy: pending validation" or omit the metric.
2. **CLIP must be validated against a labelled xBD subset** (>=50 images) before any
   accuracy figure is quoted publicly.
3. **Trust scores must be computed by an algorithm**; they must never be hardcoded or
   randomly assigned at display time.
4. **Duplicate-merge decisions must be reproducible** — the dedup engine must log its
   rationale (distance threshold, text similarity score) for every merge decision.
5. **All timestamps** must be stored in UTC. Conversion to local time is a display
   concern only.
6. **Coordinate precision** must be preserved as-is from the source; do not round
   lat/lon during ingestion.
7. **Source attribution** must survive all transformations — the `source` and
   `source_record_id` fields must be propagated through normalisation, dedup, and into
   the final PostGIS record.

---

## 8. Demo Reliability Rules

1. `docker compose up --build` must start the full stack successfully from a clean
   clone, given only `.env` populated from `.env.example`.
2. The demo must remain runnable **offline** using the checked-in sample dataset
   (`data/sample_dataset/`). No live internet connection should be required for the
   demo after the dataset is seeded.
3. The sample dataset must be committed to the repository (it is synthetic — no PII,
   no real citizen data).
4. Every external API call (USGS, Reddit) must have an explicit `timeout` parameter
   and a `try/except` that logs the error and raises an application-level exception.
5. The frontend must never show a blank page or unhandled exception to the demo
   audience — use loading states and error boundaries.
6. The admin panel must support at least 10 concurrent verification actions in the
   demo without race conditions (optimistic locking or row-level locking in DB).
7. Database migrations must be idempotent — running `alembic upgrade head` twice must
   not error.

---

## 9. Versioning & Change Control

This file (`AGENTS.md`) is versioned. Any change to a Phase Gate, a prohibited
source, or a scientific-integrity rule requires a version bump in the header and a
brief changelog entry below.

### Changelog

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 0.1 | 2026-09-04 | init | Initial project constitution |

---

*End of AGENTS.md*
