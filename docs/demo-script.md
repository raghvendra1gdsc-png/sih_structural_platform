# SIH 2026 Presentation & Demonstration Script

> **Time Budget**: 7 Minutes  
> **Audience**: Smart India Hackathon Evaluation Jury  
> **Key Objective**: Prove that the platform ingests multi-source data, performs AI classification, eliminates duplicate reports, detects misinformation transparently, clusters incidents with quantitative impact scores, and grounds conversational intelligence without hallucinations.

---

## ⏱️ Turn-by-Turn Presentation Timeline

### 0:00 – 1:00 | The Problem & National Vision
- **Speaker Action**: Open presentation or landing view on projector.
- **Narrative**:
  > *"Good morning, respected judges. During extreme monsoon cloudbursts in Mumbai or convective dust storms in Rajasthan, state disaster management authorities face two opposite problems simultaneously: **sensor blind spots** where Doppler radar has latency, and **data overload** from emergency hotlines inundated with thousands of redundant, unverified citizen reports.*
  > 
  > *Existing systems either ignore citizen data because of misinformation risks or get overwhelmed by it. Our solution is the **National Weather Big Data Analytics Platform** — an end-to-end meteorological intelligence system that triages, deduplicates, verifies, and clusters high-velocity weather observations into actionable geospatial hotspots in real time."*

---

### 1:00 – 2:15 | Command Operations Center (`/dashboard`)
- **Speaker Action**: Navigate browser to `http://localhost:3000/dashboard`.
- **Key Points to Highlight**:
  1. **Real Data Guarantee**: Point out the KPI counters: Total Reports, Verified Observations, Active Incident Hotspots, and States Monitored.
     > *"Every number on this dashboard is computed dynamically from PostgreSQL and PostGIS — there are zero hardcoded statistics."*
  2. **Interactive India Operations Map**:
     - Zoom into Jaipur or Mumbai.
     - Show the pulsing red/orange/yellow incident markers with dynamic radius circles representing clustered weather hotspots.
     - Click on an incident to reveal the popup summary: Centroid, Platform Impact Score, Category, and Observation count.
  3. **Live Observation Feed**:
     - Point out the stream of citizen and automated reports with real-time badges (`HIGH TRUST`, `SUSPECT`, `VERIFIED`).

---

### 2:15 – 3:30 | Live Ingestion & Rapid Monsoon Scenario
- **Speaker Action**: Switch to terminal and execute:
  ```bash
  python -m demo.scenario_monsoon
  ```
- **Narrative**:
  > *"Let us simulate a live rapid-onset weather event right now in Jaipur. A sudden torrential downpour triggers multiple citizen reports along MI Road and Sindhi Camp."*
- **Observation on Terminal & Screen**:
  1. Show terminal output: 6 burst reports ingested.
  2. Explain the AI classifier output: Text classified as `flooding` and `rainfall` with $>85\%$ confidence, recognizing colloquial regional terms like *barish*.
  3. Point out the **Deduplication Engine**: Two reports submitted 15 minutes apart within $0.8\text{ km}$ are automatically identified as duplicates and linked (`duplicate_of`).
  4. Point out the **Incident Clustering**: The platform dynamically aggregates the reports into an active hotspot with a **Platform Impact Score of 74/100 (HIGH)**.
  5. Refresh or observe the dashboard update instantly with the new incident.

---

### 3:30 – 4:30 | Explainable Trust & Misinformation Triage
- **Speaker Action**: Navigate browser to `http://localhost:3000/admin`.
- **Narrative**:
  > *"How do we handle misinformation and fake news? Black-box AI trust scores are dangerous in disaster response. Our engine provides 100% transparent, explainable scoring."*
- **Key Points to Show**:
  1. Click on a pending report in the review queue.
  2. Show the **Trust Score Breakdown**:
     - Source Reliability (Citizen eyewitness vs Automated sensor)
     - Radar & Forecast Consistency (Matches local precipitation radar)
     - Geospatial Bounds Check
     - Adjacent Report Corroboration
  3. Show the human-readable explanation tags:
     - `✓ Matches local meteorological radar (moderate rain showers)`
     - `✓ Corroborated: 4 adjacent reports in vicinity`
     - `⚠ Text-only report without attached photo/video evidence`
  4. Click **Verify Report**. Show the instant status change and the new entry in the non-repudiable **Audit Trail**.

---

### 4:30 – 5:45 | Grounded WeatherGPT Intelligence (`/weathergpt`)
- **Speaker Action**: Navigate browser to `http://localhost:3000/weathergpt`.
- **Narrative**:
  > *"When citizens or field responders need weather advice, standard LLMs hallucinate dangerous errors. WeatherGPT is strictly grounded in numerical weather models and our PostGIS ground truth."*
- **Interactive Prompts to Run**:
  1. Click suggested prompt: *"Will it rain in Delhi tomorrow? Should I carry an umbrella?"*
     - Point out the response: Cites numerical precipitation probability ($75\%$) and current local reports.
  2. Type a safety-critical query: *"Can I sail a small fishing boat near Mumbai today?"*
     - Point out the **MANDATORY SAFETY NOTICE**: Prominently highlights official IMD / Port Authority maritime advisories.
  3. Click **"Why this answer? (Evidence & Context)"** drawer:
     - Reveal the exact structured context: Open-Meteo temperature, wind gust speeds, active incident counts, and verified database citations.

---

### 5:45 – 7:00 | Big Data Scalability, Offline Guarantee & Conclusion
- **Speaker Action**: Navigate to `/analytics` or return to `/dashboard`.
- **Narrative**:
  > *"To summarize our architecture:
  > - **Scalability**: Decoupled ingestion via Celery and Redis with spatial GIST indexing handles tens of thousands of burst submissions.
  > - **Offline Resilience**: Even if the venue internet cuts out completely, our entire stack runs 100% locally with zero external API dependencies using pre-cached meteorological feeds.
  > - **Complete MVP**: Ingested, classified, deduplicated, verified, clustered, and queried — all through live, working software.
  > 
  > Thank you, judges. We are ready for your questions!"*
