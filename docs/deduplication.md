# Multimodal Weather Report Deduplication Engine

## 1. Problem Statement

During severe meteorological crises (such as a monsoon cloudburst in Mumbai or flash flooding in Jaipur), emergency dispatchers and monitoring dashboards are inundated by hundreds of citizen reports describing the same localized waterlogging, fallen electrical pole, or flooded underpass.

Processing every observation independently causes:
- **Artificially inflated incident counts**
- **Misallocated emergency relief teams**
- **Dashboard UI visual clutter**

The **Weather Deduplication Engine** (`ml_pipeline/weather_dedup.py`) solves this by identifying duplicate submissions and linking them to a primary canonical report (`duplicate_of = canonical_report_id`) while preserving each report's unique metadata for corroboration.

---

## 2. Multi-Stage Deduplication Pipeline

```
Candidate Weather Report
         │
         ▼
┌─────────────────────────────────┐
│ Stage 1: Spatiotemporal Filter  │
│ - Distance <= 3.5 km            │── No ──► Distinct Observation
│ - Time Delta <= 90 minutes      │
└────────────────┬────────────────┘
                 │ Yes
                 ▼
┌─────────────────────────────────┐
│ Stage 2: Category Consistency   │
│ - Matching Weather Category     │── No ──► Distinct Observation
└────────────────┬────────────────┘
                 │ Yes
                 ▼
┌─────────────────────────────────┐
│ Stage 3: Text Token Similarity  │
│ - Jaccard Word Overlap (>=0.55) │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│ Stage 4: Duplicate Score [0-100]│
│ Spatial (35) + Temporal (25) +  │
│ Category (20) + Text (20)       │
│ Score >= 60.0                   │── Yes ─► Mark Duplicate (duplicate_of = canonical_id)
└─────────────────────────────────┘
```

---

## 3. Mathematical Scoring Model

The duplicate similarity score $S_{\text{dup}} \in [0, 100]$ is computed as:

$$S_{\text{dup}} = S_{\text{spatial}} + S_{\text{temporal}} + S_{\text{category}} + S_{\text{text}}$$

Where:
1. **Spatial Proximity ($S_{\text{spatial}}$, Max 35)**:
   $$S_{\text{spatial}} = \max\left(0, 1 - \frac{d_{\text{km}}}{3.5}\right) \times 35$$
   where $d_{\text{km}}$ is the Haversine great-circle distance.
2. **Temporal Proximity ($S_{\text{temporal}}$, Max 25)**:
   $$S_{\text{temporal}} = \max\left(0, 1 - \frac{\Delta t_{\text{mins}}}{90}\right) \times 25$$
3. **Category Consistency ($S_{\text{category}}$, Max 20)**:
   $$S_{\text{category}} = \begin{cases} 20 & \text{if categories match or compatible} \\ 0 & \text{otherwise} \end{cases}$$
4. **Text Token Similarity ($S_{\text{text}}$, Max 20)**:
   $$S_{\text{text}} = \text{Jaccard}(T_1, T_2) \times 20$$

### Decision Threshold
If $S_{\text{dup}} \ge 60.0$ and categories are consistent:
- `is_duplicate = True`
- `duplicate_of = canonical_report.report_id`
- `verification_status = "duplicate"`
- A detailed rationale is logged (e.g. `Nearby (0.82 km <= 3.5 km); Within 15 mins; Matching category 'flooding'`).

---

## 4. Verification & Auditing

Every deduplication decision is non-destructive:
- Original reports remain in the database.
- The `duplicate_of` foreign key creates a traceable DAG of duplicates pointing to the canonical root.
- Operations dashboards can toggle between **"All Observations"** and **"Canonical Only"** to view unique hotspots without losing volume statistics.
