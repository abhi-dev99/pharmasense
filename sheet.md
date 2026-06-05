# Pharmasense — Executive Brief

---

## What It Is
- Predictive pharmaceutical supply chain platform for India's public health system
- Predicts drug shortages **7–14 days before they happen**, not after shelves run empty
- Bridges the gap between epidemic outbreak signals and hospital procurement decisions
- Built for government district hospitals and PHCs across 641 districts of India

---

## The Problem
- Drug stockouts during outbreaks are always reactive
- A dengue surge peaks → pharmacy runs out → order placed → 7–14 day lead time → outbreak is over
- No existing system connects epidemic forecasting directly to procurement

---

## Target Market
- **Primary:** Hospital pharmacists + supply chain managers at government hospitals/PHCs
- **Secondary:** District health officers managing procurement across multiple facilities
- **Scale:** 641 districts, ~25,000 government health facilities, all of India

---

## Core USPs

1. **ICMR Translation Layer** — Converts predicted case counts into exact drug quantities using ICMR Standard Treatment Guidelines. 1 confirmed dengue case → exact units of Paracetamol, ORS, IV Ringer's Lactate. Not generic "demand will rise" — specific SKU volumes.

2. **Adjacency-Informed Pre-Stocking** — If a neighbouring district has a rising outbreak signal, the system pre-generates purchase orders for your facility before the disease crosses the border. Nobody else does this.

3. **Full Loop Automation** — Outbreak detected → drug quantities calculated → PO drafted → pharmacist notified on WhatsApp → approved with a "YES" reply. No dashboard required.

---

## ML Architecture

| Model | Role |
|---|---|
| ST-GNN (GraphSAGE + GRU) | Communicable disease spread — fixed district adjacency |
| Graph WaveNet | Communicable disease spread — learned transmission adjacency |
| TFT | Multi-variate demand forecasting — communicable + NCD baseline |
| N-BEATS | NCD demand decomposition — trend + seasonality, interpretable |
| CatBoost Meta-Learner | Ensemble stacker — combines all model outputs |
| LP Optimizer (scipy) | Converts demand forecasts → cost-optimal purchase orders |
| LSTM Autoencoder | Anomaly detection on drug consumption patterns |

- 7 models, 3 architectures (deep learning + classical ML + operations research)
- Communicable diseases → spatial GNN models (disease spreads across borders)
- Chronic NCDs → temporal models (predictable, non-spatial)

---

## Data

- **EpiClim IDSP** — real weekly epidemic data, 2009–2022, 641 districts
- **NFHS-5 + RNTCP** — NCD prevalence for morbidity-based demand quantification
- **Census 2011 shapefile** — district polygons → adjacency matrix
- **613 drug SKUs** — including critical injectables (Ringer's Lactate, Artesunate, ORS)
- **ICMR STG rules** — treatment protocol → exact drug quantity engine
- **Live:** OpenWeatherMap (hourly), Google Trends/pytrends (daily)
- Coverage: 8 disease types × 641 districts × up to 7 years = 944K+ training records

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, TypeScript, Tailwind, deck.gl (3D map) |
| API Gateway | Go (Gin) — JWT auth, rate limiting, gRPC routing |
| ML Service | FastAPI (Python 3.11) — inference + ICMR engine |
| Database | Supabase (PostgreSQL + PostGIS + Row Level Security) |
| Cache | Redis — 24h prediction cache |
| Event Bus | Apache Kafka — outbreak → PO → WhatsApp |
| Notifications | Twilio WhatsApp API |
| LLM | Gemini 1.5 Flash — AI risk briefs on demand |

---

## Key Features

- Live 3D district heatmap of India — outbreak risk, color + height encoded, public-facing
- Smart inventory table — current stock vs. predicted demand vs. days of cover
- Auto-drafted Purchase Orders — system creates PO, pharmacist just approves
- Signal Intelligence view — rainfall + search trends + case forecast on one chart
- AI Hospital Brief — Gemini-generated plain-English risk summary, cached 24h
- Monsoon Surge Simulator — simulate worst-case weather, see which facilities collapse
- WhatsApp approvals — reply YES to approve a PO, no login needed

---

## What Exists vs. What We Do

- **ODISCM (Haryana)** — uses Prophet for demand forecasting. No spatial propagation, no adjacency signalling, no procurement loop.
- **IDSP/IHIP** — outbreak surveillance only. No supply chain connection.
- **SAP IBP / Blue Yonder** — private sector, not built for India public health or ICMR protocols.
- **Gap we close:** epidemic signal → drug quantity → PO → pharmacist notification, automated, using India-specific protocols, at district granularity.

---

## Potential Challenges

- Sparse data for cholera/dengue → mitigated by ensemble with TFT baseline
- Census 2011 population estimates (pre-bifurcations) → trend multiplier + documented limitation
- Weather data covers metros only → district-level interpolated from nearest centroid
- Government APIs inconsistent → all live data from reliable third-party APIs

---

## Workflow

```
DAILY (06:00 IST)

  OpenWeatherMap + Google Trends
          ↓
  ST-GNN + Graph WaveNet  →  outbreak risk per district
  TFT + N-BEATS           →  drug demand per district
          ↓
  ICMR Translation Layer  →  cases × protocol = exact SKU quantities
          ↓
  LP Optimizer            →  cost-optimal PO quantities
          ↓
  Write to Supabase + Redis cache
          ↓
  IF shortfall > threshold:
          ↓
        KAFKA
       ↙      ↘
  Auto PO    WhatsApp alert to pharmacist
  (PENDING)  "Reply YES to approve"


HOURLY

  Rain > 40mm + Humidity > 80% for 3 days
    → Invalidate Redis cache
    → Re-run inference immediately


ON DEMAND

  User clicks hospital → Gemini generates risk brief
  Pharmacist replies YES → Twilio webhook → PO approved
```

---

*AgTechathon 2.0 2K26*
