# MedFusion - Disease Intelligence Dashboard


MedFusion is a full-stack disease surveillance platform that unifies real-time data from 12 public health sources — WHO, CDC, ECDC, ProMED, HealthMap, Open Targets, PubChem, and more — into a single intelligent interface. It goes beyond displaying raw data: every output is processed, fused across sources, and explained with scientific rationale.

---

## What It Does

Query any disease and immediately get:

- **Where it is spreading** — geographic distribution from WHO, CDC, ECDC
- **How fast** — R₀, Rt, doubling time, 7-day trend computed from real data
- **What the data says** — multi-source fusion with conflict resolution and confidence scoring
- **What ML predicts** — XGBoost 14-day forecast + Z-Score/CUSUM anomaly detection
- **Which genes are involved** — ranked gene-disease associations from Open Targets
- **Which drugs exist** — drug data from PubChem with WHO Essential Medicines status
- **India-specific burden** — from NVBDCP, MoHFW, NACO, WHO India Office
- **Live outbreak alerts** — ProMED RSS + HealthMap, filtered to the queried disease
- **Country risk leaderboard** — composite outbreak risk scored live from disease.sh

---

## Architecture

```
medf/
├── medfusion_backend/          # FastAPI — Python 3.12
│   ├── connectors/             # 12 source connectors
│   ├── fusion/                 # Multi-source data fusion layer
│   │   ├── normalizer.py       # Source → NormalizedCaseRecord
│   │   └── merger.py           # Weighted merge + conflict resolution
│   ├── pipeline/
│   │   └── orchestrator.py     # 8-stage pipeline (fetch→normalize→fuse→metrics→ML→cross-domain→alerts→insights)
│   ├── ml/
│   │   ├── forecast.py         # XGBoost lag-feature forecaster
│   │   ├── anomaly.py          # Z-Score + CUSUM (WHO standard)
│   │   └── risk.py             # SIR-derived composite risk scoring
│   ├── services/
│   │   ├── epidemiology.py     # R₀, Rt, CFR, doubling time, trend classification
│   │   ├── explainability.py   # WHY explanations for every ML output
│   │   ├── query_intelligence.py # Synonym mapping, fuzzy match, region-aware queries
│   │   └── outbreak_risk.py    # Country-wise outbreak risk leaderboard
│   ├── schemas/
│   │   └── models.py           # NormalizedCaseRecord, FusedDiseaseRecord, ComputedMetrics
│   └── api/
│       └── app.py              # FastAPI endpoints
│
└── medfusion_frontend/         # Next.js 14 — TypeScript + Tailwind + Recharts
    └── src/app/page.tsx        # Single-page application
```

---

## Data Sources (12 total)

| Source | What It Provides | Update Frequency |
|--------|-----------------|-----------------|
| disease.sh | COVID-19 global live stats | ~10 minutes |
| disease.sh (historical) | COVID-19 90-day timeline | Daily |
| disease.sh (countries) | 200+ countries COVID breakdown | ~10 minutes |
| WHO GHO OData API | Malaria, TB, Dengue annual estimates | Annual |
| CDC Open Data (Socrata) | US state-level COVID surveillance | Daily |
| CDC FluView (ILINet) | Influenza-like illness % surveillance | Weekly |
| ECDC Open Data | European COVID data by country | Daily |
| UKHSA Dashboard | UK COVID and flu data | Daily |
| ProMED RSS | Real-time infectious disease alerts | Real-time |
| HealthMap | Geo-tagged outbreak alerts | Real-time |
| Open Targets Platform (GraphQL) | Gene-disease associations by evidence score | Quarterly |
| PubChem PUG-REST | Drug information + WHO EML status | Ongoing |
| IHME GHDx / NVBDCP / MoHFW | India-specific disease burden | Annual |

---

## Pipeline — 8 Stages

Every query runs through this pipeline. The full execution log is returned in the API response.

```
STAGE 1  fetch_sources()        Parallel fetch from all relevant sources
STAGE 2  normalize_sources()    Convert to unified NormalizedCaseRecord schema
STAGE 3  fuse_records()         Weighted merge (WHO=0.50, CDC=0.30, others=0.20)
                                + conflict resolution + confidence scoring
STAGE 4  compute_metrics()      R₀, Rt, CFR, doubling time, 7-day trend
STAGE 5  run_ml()               XGBoost forecast + Z-Score/CUSUM + SIR risk
STAGE 6  fetch_cross_domain()   Open Targets genomics + PubChem therapeutics
STAGE 7  filter_alerts()        ProMED + HealthMap filtered by disease + synonyms
STAGE 8  generate_response()    Explainable insights + unified JSON
```

**Example for `dengue in india`:**
- Stage 1 fetches WHO GHO dengue + ProMED 30 alerts + HealthMap + IHME India
- Stage 3 fusion: single WHO source → `single_source` method, confidence MEDIUM
- Stage 6 fetches Open Targets gene associations using EFO `MONDO_0005502`
- Stage 7 filters alerts matching "dengue" + synonyms "denv", "dengue fever"
- Stage 8 generates insight: India: 289,000 cases/year (NVBDCP 2022), peak Jul–Oct

---

## Data Fusion

Sources are not simply aggregated — they are fused using source reliability weights.

**Source weights:**
```
WHO GHO        → 0.50   (gold standard, peer-reviewed estimates)
CDC Open Data  → 0.30   (authoritative national surveillance)
ECDC           → 0.20   (regional authority)
disease.sh     → 0.20   (aggregator)
ProMED         → 0.10   (alert-based signal)
```

**Conflict resolution:**

```python
# Weighted average: Σ(value × weight) / Σ(weight)
# Outlier downweighting: values >2σ from mean get 70% weight reduction
# Biological consistency: deaths capped at 60% of cases
# CFR priority: computed from fused cases/deaths first, else weighted avg of sources
```

**Confidence score (returned in every response):**

```
overall = 0.40 × completeness + 0.35 × agreement + 0.25 × freshness
```

---

## ML Models

| Model | What It Does | Basis |
|-------|-------------|-------|
| XGBoost lag-feature | 14-day case forecast using 7-day lag window | Outperforms Prophet on epidemic data (lower RMSE) |
| Z-Score + CUSUM | Anomaly detection — spikes and sustained shifts | WHO/CDC EWARN surveillance standard |
| SIR composite risk | 0–100 risk score from R₀, CFR, burden, growth | SIR model-derived component weights |
| Growth classifier | Exponential / linear / plateau / volatile detection | R² comparison of linear vs log-linear fit |

Every ML output includes a WHY explanation. Example:

> *"Risk HIGH (score 62.5/100): R₀=2.1 contributes 37pts — epidemic spreading. CFR=1.5% contributes 8pts. Cases increased +15.3% in 7 days contributes 5pts."*

---

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /disease/{name}` | Full 8-stage pipeline — the primary endpoint |
| `GET /insights/{disease}` | Cross-domain intelligence insights only |
| `GET /trends/{disease}` | Timeline + XGBoost forecast + anomaly detection |
| `GET /compare/{d1}/{d2}` | Side-by-side disease comparison |
| `GET /genomics/{disease}` | Gene associations from Open Targets |
| `GET /therapeutics/{disease}` | Drug data from PubChem PUG-REST |
| `GET /alerts?disease=X` | ProMED + HealthMap filtered alerts |
| `GET /india/{disease}` | India-specific burden (IHME/NVBDCP/MoHFW) |
| `GET /hotspots` | Country-wise outbreak risk leaderboard (live) |
| `GET /spread` | Geographic spread — countries, continents, US, Europe, UK |
| `GET /sources` | All 12 sources + pipeline stage documentation |

Interactive API docs: `http://localhost:8000/docs`

---

## Query Intelligence

The system understands natural language disease queries with synonym resolution, fuzzy matching, and region awareness.

```
"covid"          → covid-19  (canonical resolution)
"tb"             → tuberculosis  (alias)
"flu"            → influenza  (alias)
"dengue in india"→ disease=dengue, region=india  (region-aware)
"bird flu"       → h5n1  (synonym)
"monkeypox"      → mpox  (synonym)
```

---

## Diseases with Full Data

| Disease | Case Count | Trend | Forecast | Genomics | Therapeutics | India |
|---------|-----------|-------|----------|----------|--------------|-------|
| COVID-19 | ✅ Live | ✅ | ✅ XGBoost | ✅ | ✅ | ✅ |
| Malaria | ✅ WHO ~249M | — | — | ✅ | ✅ | ✅ |
| Tuberculosis | ✅ WHO ~10.6M | — | — | ✅ | ✅ | ✅ |
| Influenza | ✅ CDC ILI | — | — | ✅ | ✅ | — |
| Others | ProMED alerts | — | — | ✅ | ✅ | ✅ |

---

## Running Locally

### Backend

```bash
cd medfusion_backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

No API keys required. All sources are publicly accessible.

### Frontend

```bash
cd medfusion_frontend
npm install
npm run dev
# http://localhost:3000
```

**Environment:**
```
# medfusion_frontend/.env.local
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### Test all sources

```bash
cd medfusion_backend
python test_sources.py
```

---

## Tech Stack

**Backend**
- Python 3.12, FastAPI, Uvicorn
- XGBoost 2.0.3, NumPy 1.26.4
- feedparser, requests, beautifulsoup4

**Frontend**
- Next.js 14, React 18, TypeScript
- Tailwind CSS, Recharts
- IBM Plex Mono (typography)

---
