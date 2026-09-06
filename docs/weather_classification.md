# AI-Assisted Weather Event Classification Pipeline

## 1. Objective & Scope

Citizen weather reports arrive in diverse formats — ranging from colloquial social media blurbs to emergency helpline summaries. Reports often use regional Indian meteorological terminology rather than formal meteorological labels:
- *"Bohot tez andhi aa rahi hai highway pe"* (Dust storm)
- *"Heavy barish and waterlogging near station"* (Rainfall / Flooding)
- *"Extreme loo blowing today, temperature is unbearable"* (Heatwave)
- *"Ghanera kohra on expressways"* (Dense fog)

The **Weather Event Classification Pipeline** (`ml_pipeline/weather_classifier.py`) performs rapid, calibrated classification into 12 standardized categories.

---

## 2. Canonical Weather Categories

| Category | Typical Phenomena / Triggers | Example Regional Terms |
|---|---|---|
| **`rainfall`** | Continuous showers, downpours, cloudburst | *barish*, *monsoon*, *barsaat*, *drizzle* |
| **`thunderstorm`** | Lightning squalls, thunderclaps, convective storm | *toofan*, *bijli*, *squall*, *thunderclap* |
| **`flooding`** | Waterlogged roads, submerged underpasses, inundated homes | *jal-bharav*, *waterlogging*, *submerged* |
| **`heatwave`** | Scorching thermal index, blistering dry winds, $T \ge 45^\circ\text{C}$ | *loo*, *extreme heat*, *scorching* |
| **`dust_storm`** | Convective sand squall, wall of dust, blinding grit | *andhi*, *aandhi*, *dust squall*, *haboob* |
| **`strong_winds`** | Gales, tin roof damage, uprooted trees | *gale*, *gusty winds*, *howling wind* |
| **`cyclone`** | Coastal depression, storm surges, hurricane force | *cyclonic storm*, *deep depression* |
| **`hailstorm`** | Ice pellets, frozen rain damage to crops | *ola*, *ole*, *hailstones* |
| **`fog`** | Zero visibility smog/mist on expressways | *kohra*, *smog*, *dense fog*, *mist* |
| **`lightning`** | Cloud-to-ground strikes, exploded transformers | *bijli girna*, *thunderbolt*, *lightning strike* |
| **`cold_wave`** | Freezing nighttime temperatures across northern plains | *shivering chill*, *sheatlehar*, *frost* |
| **`landslide`** | Mudslides, rockfalls blocking ghat roads | *rockfall*, *mudslide*, *debris flow* |
| **`other`** | General unclassified atmospheric observations | *cloudy*, *windy*, *normal* |

---

## 3. Classification Architecture

```
Raw Report Text (Eyewitness submission)
                   │
                   ▼
┌────────────────────────────────────────┐
│ Preprocessing & Regional Normalization │
│ - Lowercase & whitespace trimming      │
│ - Lexical accent normalization         │
└──────────────────┬─────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────┐
│ Calibrated Lexical / Semantic Scoring  │
│ - Weighted keyword matching            │
│ - Multi-term cumulative resonance      │
└──────────────────┬─────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────┐
│ Confidence Calibration [0.0 - 1.0]     │
│ - Max category score extraction        │
│ - Confidence calibrated [0.45, 0.98]   │
└──────────────────┬─────────────────────┘
                   │
                   ▼
       ClassificationResult
       - Category: WeatherEventCategory
       - Confidence: 0.88
       - Model: "nlp_lexical_v1"
```

---

## 4. Scientific & Operational Integrity

1. **No False Certainty**: If a report cannot be reliably mapped to any recognized category, it is safely classified as `other` with low confidence ($\le 0.30$), prompting manual operator verification.
2. **Deterministic Calibration**: The model avoids floating hallucinations and yields identical scores for identical inputs.
3. **Multi-Category Disambiguation**: When an observation mentions both rain and flooding (*"Heavy rain caused severe flooding"*), priority weights favor the higher-impact physical outcome (`flooding`).
