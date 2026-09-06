# WeatherGPT: Grounded Conversational Weather Intelligence

## 1. Design Principles

In emergency disaster response and meteorological monitoring, standard Large Language Models (LLMs) pose severe operational risks due to **hallucinations** — inventing plausible-sounding temperatures, fake storm warnings, or nonexistent clear skies.

**WeatherGPT** solves this problem by adhering to strict grounding principles:
1. **Zero Hallucination**: Does not extrapolate or fabricate numerical values. Every meteorological variable (temperature, wind gust, precipitation probability) is retrieved directly from physical meteorological models.
2. **Dual-Layer Grounding**: Combines forward-looking physical forecasts (Open-Meteo) with real-time ground observations and verified incident clusters (PostGIS database).
3. **Traceable Citations**: Every answer includes explicit citations pointing to the sensor coordinates and database records supporting the response.
4. **Mandatory Safety Notices**: Detects high-risk questions (such as marine or maritime queries) and automatically injects official India Meteorological Department (IMD) / Port Authority advisory disclaimers.
5. **Explainability Drawer**: Provides an interactive *"Why this answer?"* context panel exposing the raw numerical metrics, incident severity scores, and observation counts.

---

## 2. Retrieval & Grounding Flow

```
User Query: "Should I carry an umbrella in Mumbai tomorrow?"
                           │
                           ▼
          ┌──────────────────────────────────┐
          │ Intent & Location Extraction     │
          │ - Location: "Mumbai"             │
          │ - Intent: "precipitation"        │
          └────────────────┬─────────────────┘
                           │
                           ▼
          ┌──────────────────────────────────┐
          │ Dual-Layer Retrieval             │
          │ 1. Open-Meteo Physical Forecast: │
          │    - Tomorrow Rain Prob: 85%     │
          │    - Condition: Heavy Rain       │
          │    - Max Temp: 31°C              │
          │ 2. PostGIS Ground Truth:         │
          │    - 14 recent citizen reports   │
          │    - 6 verified observations     │
          │    - Impact Score: 78/100 (HIGH) │
          └────────────────┬─────────────────┘
                           │
                           ▼
          ┌──────────────────────────────────┐
          │ Answer Synthesis Engine          │
          │ - Cites rain probability (85%)   │
          │ - Cites local ground reports     │
          │ - Clear operational advice       │
          │ - Links citations & context      │
          └──────────────────────────────────┘
```

---

## 3. Supported Query Intents

| Intent | Trigger Examples | Key Grounded Metrics Returned |
|---|---|---|
| **Precipitation** | "Will it rain?", "Need an umbrella?", "Monsoon status" | Precipitation probability, current rain rate, verified waterlogging reports |
| **Wind & Storm** | "How strong are the winds?", "Cyclone alert?", "Gusts" | Sustained wind speed, max gust speed, active storm incidents |
| **Marine Safety** | "Can I go fishing?", "Is boating safe?", "Sea conditions" | Wind speed, gust velocities, swell alerts, **IMD Marine Warning Disclaimer** |
| **Travel Advisory**| "Can I drive on the highway?", "Flight delays?", "Road trip" | Visibility, local flash flood hotspots, platform impact score |
| **General Overview**| "What's the weather like?", "Current conditions" | Temperature, humidity, active incident clusters in the district |

---

## 4. Operational API Example

### Request
```bash
curl -X POST http://localhost:8000/api/chat/weathergpt \
  -H "Content-Type: application/json" \
  -d '{"query": "Is it safe to sail a boat near Mumbai today?"}'
```

### Response
```json
{
  "query": "Is it safe to sail a boat near Mumbai today?",
  "city": "Mumbai",
  "intent": "marine_safety",
  "answer": "Regarding boating around **Mumbai**: current wind speeds are **18.2 km/h** with gusts reaching **32.4 km/h**.\n\nWeather is relatively steady, but check local coastal radar before departure.",
  "safety_notice": "SAFETY NOTICE: This summary reflects aggregated meteorological feeds and citizen observations. It is NOT an official maritime safety clearance. Always consult the India Meteorological Department (IMD) and Port Authority marine warnings before sailing.",
  "structured_context": {
    "city": "Mumbai",
    "current_temp_c": 29.5,
    "condition": "Humid / Light Rain",
    "wind_kmh": 18.2,
    "wind_gust_kmh": 32.4,
    "tomorrow_rain_prob": 75,
    "active_incidents_count": 4,
    "platform_impact_score": 68.0,
    "platform_severity": "high"
  },
  "citations": [
    "Open-Meteo Numerical Forecast (lat: 19.08, lon: 72.88)",
    "National Database: 32 recent citizen reports in Mumbai",
    "Verified Ground Observations: 8 verified incident reports",
    "Platform Geospatial Intelligence (Impact Score: 68/100)"
  ],
  "updated_at": "11:58 UTC"
}
```
