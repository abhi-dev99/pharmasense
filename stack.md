# Pharmasense — Complete Technical Stack & Architecture Reference

> **Internal Motto:** By hook or by crook, we deliver on everything we say. Nothing left halfway. Think product, not project.

---

## 1. What This Product Is

**Pharmasense** is a predictive pharmaceutical supply chain platform built for India.

**The problem it solves:** Drug stockouts during disease outbreaks are always reactive — shelves go empty, then someone orders. By the time the order arrives (7-14 day lead time), the outbreak has already peaked.

**What we do instead:** Cross-reference live environmental signals (monsoon weather, symptom search trends) against district-level epidemiological baselines to predict an outbreak **7-14 days before it physically crosses into a new district**. The moment a prediction crosses a risk threshold, the system autonomously generates Purchase Orders and alerts the pharmacist — before there's a problem.

**The ICMR Translation Layer (our core differentiator):** 1 confirmed dengue case → exact quantity of paracetamol, IV fluids, ORS required per ICMR Standard Treatment Guidelines. We don't predict "demand" generically — we predict exact drug-level drawdown volumes from first principles.

**The Dual-Engine Router (our ML differentiator):** Not one model. A Python classifier routes each disease type to the ML architecture best suited for it:
- **Communicable diseases** (dengue, malaria, cholera) → ST-GNN (disease spreads geographically via adjacency)
- **Non-communicable / baseline demand** (hypertension meds, routine antibiotics) → TFT (time-series with seasonality + covariates)

---

## 2. User Roles & Access Tiers

| Role | View | What they see |
|---|---|---|
| **State Health Minister** | Macro (state-level) | 3D district heatmap, macro risk scores, budget allocation recommendations |
| **District Health Officer** | Meso (district-level) | All hospitals in district, predicted shortfalls, PO approvals dashboard |
| **Hospital Pharmacist** | Micro (facility-level) | Their hospital only, drug-level inventory, approved orders, WhatsApp alerts |

Enforced via Supabase Row Level Security — a pharmacist SQL query physically cannot return another hospital's rows.

---

## 3. Full Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 1 CLIENT: Streamlit Dashboard                             │
│  PHASE 2 CLIENT: Next.js 14 (App Router) — same API, new UI     │
│                                                                  │
│  pydeck (deck.gl maps)  │  Plotly/Altair (charts)               │
│  Supabase Auth SDK      │  Streamlit-authenticator (phase 1)    │
└──────────────────────┬───────────────────────────────────────────┘
                       │ REST / JSON  (same contract for both UIs)
┌──────────────────────▼───────────────────────────────────────────┐
│  GO API GATEWAY  (Gin)                                           │
│  - JWT verification (Supabase tokens)                            │
│  - Role extraction → attaches to request context                 │
│  - Request routing to ML service                                 │
│  - Rate limiting (per-role, per-endpoint)                        │
│  - Observability (structured logs, request tracing)              │
│  - OpenAPI spec served at /docs                                  │
│                                                                  │
│  WHY GO: When ML runs on GPU clusters (Triton, TorchServe),     │
│  they speak gRPC natively. Our gateway is already gRPC-fluent.  │
│  No routing layer rewrite at scale. This is the moat.           │
└──────────────────────┬───────────────────────────────────────────┘
                       │ gRPC (internal only, never exposed)
┌──────────────────────▼───────────────────────────────────────────┐
│  FASTAPI ML SERVICE  (Python 3.11, async)                        │
│                                                                  │
│  ETIOLOGY ROUTER                                                 │
│    disease ∈ {dengue, malaria, cholera} → ST-GNN                │
│    disease ∈ {baseline, NCD}            → TFT                   │
│                                                                  │
│  ST-GNN (PyTorch Geometric)                                      │
│    Nodes = Indian districts (~640)                               │
│    Edges = shared district borders (adjacency matrix)            │
│    Features = [incidence_rate, weather_score, search_score]     │
│    Output = risk_probability per node, 14-day horizon            │
│    Trained on: EpiClim 2016-2023 (7 years, real data)           │
│                                                                  │
│  TFT (pytorch-forecasting)                                       │
│    Input = drug sales history + seasonal covariates              │
│    Output = demand forecast per drug per district, 30-day       │
│    Trained on: Synthetic txn data (EpiClim × ICMR rules)        │
│                                                                  │
│  ICMR Translation Layer (JSON rules engine)                      │
│    Input:  confirmed_cases × disease_type × district             │
│    Output: sku_demand_volumes (per drug, per day)                │
│                                                                  │
│  Gemini 1.5 Flash (LLM briefs, on-demand)                       │
│  Prophet (fallback forecaster if model artifacts missing)        │
│  Kafka Producer (publishes outbreak_events)                      │
│  Redis client (prediction cache, 24h TTL)                        │
└──────────────────────┬───────────────────────────────────────────┘
                       │
          ┌────────────┴──────────────────┐
          │                               │
┌─────────▼──────────┐         ┌──────────▼────────────────────────┐
│  REDIS             │         │  KAFKA + ZOOKEEPER                │
│  Prediction cache  │         │  Topic: outbreak_events            │
│  Key: district_id  │         │                                   │
│  + disease_type    │         │  Consumer 1: PO Generator         │
│  + date            │         │    → writes PO to Supabase        │
│  TTL: 24h          │         │    → marks status: PENDING        │
│  Invalidated by:   │         │                                   │
│  weather anomaly   │         │  Consumer 2: WhatsApp Notifier    │
│                    │         │    → Twilio API                   │
└────────────────────┘         │    → "Reply YES to approve PO"    │
                               │                                   │
                               │  Consumer 3: (Next.js phase)      │
                               │    → SSE/WebSocket live map update│
                               └───────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────────┐
│  SUPABASE  (PostgreSQL 15 + PostGIS + Auth + RLS)                │
│                                                                  │
│  hospitals (id, name, lat, lon, district_id, tier)              │
│  districts (id, name, state, geojson_polygon, adjacency_ids[])  │
│  drugs (id, name, generic_name, category, icmr_protocol)        │
│  inventory (hospital_id, drug_id, stock_units, updated_at)      │
│  inventory_transactions (hospital_id, drug_id, delta, ts)       │
│  epid_weekly (district_id, disease, week, cases_per_100k)       │
│  weather_signals (district_id, timestamp, rain_mm, humidity%)   │
│  search_signals (state, query_term, search_index, date)         │
│  risk_scores (district_id, drug_id, score, model_used, ts)     │
│  purchase_orders (id, hospital_id, drug_id, qty, status, ts)    │
│  audit_log (table, action, user_id, ts)                         │
│                                                                  │
│  Auth: Supabase Auth → JWT embeds role claim                     │
│  RLS: role-based row isolation (each role sees only its scope)   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. Tech Stack — Every Layer

### Frontend (Phase 1 — Streamlit)
| Tool | Version | Purpose |
|---|---|---|
| `streamlit` | 1.35+ | UI framework |
| `pydeck` | 0.9+ | deck.gl 3D hospital/district heatmap |
| `plotly` | 5.x | Signal timeline charts |
| `altair` | 5.x | Lightweight charting |
| `streamlit-authenticator` | 0.3+ | Role-based login in Streamlit |
| `supabase-py` | 2.x | Auth + data client |
| `httpx` | 0.27+ | Async calls to Go gateway |

### Frontend (Phase 2 — Next.js, after backend is solid)
| Tool | Purpose |
|---|---|
| Next.js 14 (App Router) | SSR, streaming, API routes |
| deck.gl + react-map-gl | 3D district heatmap (LIFTED from AgTechathon) |
| Recharts | Signal timelines |
| Tailwind CSS | Styling |
| Clerk OR Supabase Auth JS | Auth (same JWT, same RLS) |
| SWR | Data fetching + cache invalidation |

> **Key contract:** The Go gateway REST API is identical for both UIs. Migrating to Next.js = new frontend only, zero backend changes.

### API Gateway (Go)
| Tool | Purpose |
|---|---|
| `gin-gonic/gin` | HTTP router |
| `grpc-go` | gRPC client to FastAPI ML service |
| `golang-jwt/jwt` | Supabase JWT verification |
| `go-redis/redis` | Optional: edge-level cache check |
| Protocol Buffers | gRPC interface definition |

### ML Service (Python)
| Tool | Purpose |
|---|---|
| `fastapi` | Async API framework |
| `uvicorn` | ASGI server |
| `grpcio` + `grpcio-tools` | gRPC server (called by Go gateway) |
| `pydantic` v2 | Request/response validation |
| `torch` + `torch-geometric` | ST-GNN (communicable disease spread) |
| `pytorch-forecasting` | TFT (non-communicable baseline demand) |
| `prophet` | Fallback time-series forecaster |
| `geopandas` + `shapely` | District GeoJSON → adjacency matrix |
| `networkx` | Graph construction + analysis |
| `pandas` + `numpy` | Data processing |
| `scikit-learn` | Feature engineering, preprocessing |
| `google-generativeai` | Gemini API for LLM briefs |
| `redis-py` | Prediction cache |
| `confluent-kafka` | Kafka producer (outbreak events) |
| `supabase-py` | DB reads/writes |
| `pytrends` | Google symptom search trends |
| `openweathermap-requests` / `httpx` | Weather signals |
| `mlflow` | (Production) model tracking & registry |

### Infrastructure
| Tool | Purpose |
|---|---|
| Docker + Docker Compose | Local dev orchestration |
| Redis 7 | Prediction cache (24h TTL) |
| Apache Kafka 3.x + Zookeeper | Outbreak event bus |
| Supabase Cloud | Managed PostgreSQL + PostGIS + Auth |
| GitHub Actions | CI/CD (lint + test on every PR) |

### Deployment (production-ready from day 1)
| Layer | Platform |
|---|---|
| Streamlit (Phase 1) | Streamlit Cloud (free) |
| Next.js (Phase 2) | Vercel (free tier) |
| Go Gateway + FastAPI | Render / Railway (free tier → paid for GPU) |
| Supabase | Supabase Cloud |
| Redis | Upstash (serverless Redis, free tier) |
| Kafka | Upstash Kafka (serverless, free tier) |

---

## 5. Data Inventory — Live vs. Batch

### Static / Pre-loaded (loaded once, unchanged during runtime)
| Dataset | Source | What it provides | When loaded |
|---|---|---|---|
| EpiClim | Zenodo record 14580510 | Weekly district-level case counts, 2016-2023, all India, ~640 districts | At model training time |
| India district GeoJSON | Datameet (`datasets.datameet.org`) | District polygons → adjacency matrix for ST-GNN | At service startup |
| India Medicines catalog | Kaggle `apkaayush/india-medicines` | 250k+ SKUs, generics, MRP, manufacturers | At DB seed time |
| ICMR Translation rules | ICMR Standard Treatment Guidelines | `{disease: {drug: dose_per_case}}` JSON | At service startup |
| Trained ST-GNN artifact | Training run on Colab | `.pt` model weights | At service startup |
| Trained TFT artifact | Training run on Colab | `.pt` model weights | At service startup |

### Live / Refreshed (real data flowing continuously)
| Signal | Source | Freshness | How fetched |
|---|---|---|---|
| Weather (rain, humidity, temp) | OpenWeatherMap API | Every hour | Scheduled job in FastAPI lifespan |
| Symptom search trends | pytrends (Google Trends) | Weekly resolution, pulled daily | Daily cron |
| Hospital inventory state | Supabase (pharmacist writes) | Event-driven, on each transaction | Supabase realtime subscriptions |
| District risk scores | ML inference | Daily + on-demand on weather spike | Cached in Redis 24h |
| LLM Hospital Briefs | Gemini API | On-demand (user clicks hospital) | Cached 24h in Redis |

### Computed / Derived
| Output | Computed from | How often |
|---|---|---|
| District risk score (0-100) | Weather + search + epid history → ST-GNN or TFT | Daily batch + triggered on weather anomaly |
| SKU demand forecast (units) | Risk score × ICMR translation layer | Daily, per drug per district |
| Inventory shortfall | Forecast demand − (stock_on_hand + on_order) | Derived on every risk score update |
| Purchase Order | Shortfall > threshold | Triggered by Kafka consumer |
| Hospital Brief (LLM) | All of the above, formatted as prompt | On-demand |

---

## 6. Data Flow — Precise Timeline

```
DAILY BATCH (06:00 IST):
────────────────────────
  pytrends → pull weekly symptom search by state → Supabase.search_signals
  OpenWeatherMap → pull hourly weather for 10 metros → Supabase.weather_signals
  Compute: weather_score per district (rain × humidity formula)
  Compute: search_score per district (symptom velocity)
  Run ST-GNN inference → risk_probability per district (communicable)
  Run TFT inference → demand_forecast per drug per district (baseline)
  Apply ICMR translation → sku_demand_volumes
  Compute: shortfall = forecast − inventory
  Write: risk_scores table in Supabase
  Write: predicted shortfalls
  Cache: all predictions in Redis (key: district+drug+date, TTL 24h)
  IF any shortfall > threshold → publish to Kafka: outbreak_events

KAFKA CONSUMERS (always running):
──────────────────────────────────
  Consumer 1 (PO Generator):
    Read outbreak_event → compute order quantity
    Write purchase_order (status: PENDING) to Supabase
    
  Consumer 2 (WhatsApp Notifier):
    Read outbreak_event → compose alert message
    Twilio API → send WhatsApp to pharmacist
    "ALERT: Dengue surge predicted in [District]. 
     Paracetamol stock depletes in 4 days. 
     Reply YES to auto-approve PO for 5,000 units."

HOURLY:
───────
  OpenWeatherMap → weather update per metro
  IF rain > 40mm AND humidity > 80% for 3 consecutive days:
    → weather anomaly flag = True
    → invalidate Redis cache for affected districts
    → trigger immediate re-inference (not waiting for daily batch)
    → publish outbreak_event to Kafka if risk crosses threshold

ON-DEMAND (user triggers):
───────────────────────────
  User clicks hospital node on map:
    → Check Redis for cached brief
    → Cache miss: Gemini API generates Hospital Risk Brief
    → Render in Streamlit / Next.js panel
    → Cache for 24h

  Pharmacist replies "YES" to WhatsApp:
    → Twilio webhook → FastAPI endpoint
    → Update PO status: APPROVED
    → (Optional v2: trigger supplier webhook / ERP integration)
```

---

## 7. ML Architecture — Detail

### ST-GNN (Spatio-Temporal Graph Neural Network)

```python
# Graph structure
Nodes: 640 Indian districts
Edges: shared district borders (GeoPandas intersection)
Edge weights: shared border length / district area (proximity weight)

# Node features (per timestep t)
x[t] = [
    incidence_rate,       # EpiClim: cases per 100k this week
    rain_mm,              # OpenWeatherMap
    humidity_pct,         # OpenWeatherMap  
    symptom_search_idx,   # pytrends
    season_encoding,      # sin/cos of week-of-year
    monsoon_flag,         # binary
]

# Architecture: GraphSAGE + GRU temporal wrapper
GRU(sequence_length=8weeks) → hidden_state per node
GraphSAGE(hidden_state) → risk_probability per node

# Output
risk_probability[district, t+1..t+14] = probability of outbreak
                                         crossing risk threshold

# Training
Dataset: EpiClim 2016-2023
          ~7 years × 52 weeks × 640 districts
Split: train 2016-2021 / val 2021-2022 / test 2022-2023
Loss: Binary Cross-Entropy (outbreak / no-outbreak per district per week)
Platform: Google Colab T4 GPU (free)
```

### TFT (Temporal Fusion Transformer)

```python
# Per drug, per district — non-communicable baseline demand
Library: pytorch-forecasting

# Input features
known_past:   [drug_sales_history, season, holidays]
known_future: [monsoon_calendar, holiday_calendar]
static:       [district_income_tier, population, urbanization]

# Output
demand_forecast[drug, district, t+1..t+30] = units per day

# Training
Synthetic dataset generated by:
  EpiClim baseline incidence × ICMR treatment protocol → 
  → simulated drug drawdown volumes per hospital
```

### ML Feedback Loop

```
Hackathon Phase (v1):
  Train once (Colab) → serialize .pt → load at service startup
  No live retraining. Inference only.

Production Phase (v2):
  Weekly retraining job (Prefect scheduler)
  New training data: actual pharmacy drawdowns + IDSP confirmed cases
  MLflow: experiment tracking, model registry, champion/challenger
  Canary deployment: new model serves 10% of requests before promotion
```

---

## 8. API Contract (Stable — serves both Streamlit and Next.js)

All endpoints exposed by the **Go gateway** as REST/JSON.
gRPC is internal only (Gateway → FastAPI). Never exposed to clients.

```
Authentication: Bearer {supabase_jwt} on all routes

GET  /health                              → service health
GET  /api/districts                       → all districts + current risk scores
GET  /api/districts/{id}                  → district detail + hospital list
GET  /api/districts/{id}/risk             → current risk score + signal breakdown
GET  /api/hospitals                       → hospitals visible to current role
GET  /api/hospitals/{id}                  → hospital detail + inventory
GET  /api/hospitals/{id}/inventory        → drug-level inventory + forecasts
GET  /api/hospitals/{id}/brief            → LLM-generated Hospital Risk Brief
POST /api/simulate/monsoon                → trigger monsoon surge simulation
     body: {districts: [id,...], intensity: float}
GET  /api/purchase-orders                 → POs visible to current role
POST /api/purchase-orders/{id}/approve    → pharmacist approves PO
GET  /api/signals/timeline/{district_id} → weather + search + epid time series
POST /hooks/whatsapp                      → Twilio webhook (PO approval via WhatsApp)
```

---

## 9. Environment Variables

See `.env` file (gitignored). Variable names:
```
GOOGLE_GEMINI_API_KEY
OPENWEATHER_API_KEY
TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN
TWILIO_WHATSAPP_FROM
SUPABASE_URL
SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY
REDIS_URL
KAFKA_BOOTSTRAP_SERVERS
KAFKA_OUTBREAK_TOPIC
ML_SERVICE_GRPC_HOST
GATEWAY_HOST
ML_SERVICE_HTTP_HOST
STGNN_MODEL_PATH
TFT_MODEL_PATH
APP_ENV
LOG_LEVEL
```

---

## 10. Monorepo Structure

```
pharmasense/
├── .env                          ← secrets (gitignored)
├── .env.example                  ← template (committed)
├── .gitignore
├── stack.md                      ← this file
├── docker-compose.yml            ← Redis + Kafka + services
│
├── gateway/                      ← Go API gateway
│   ├── main.go
│   ├── routes/
│   ├── middleware/               ← JWT auth, rate limiting
│   ├── proto/                    ← Protobuf definitions
│   └── Dockerfile
│
├── backend/                      ← FastAPI ML service
│   ├── main.py
│   ├── api/                      ← route handlers
│   ├── ml/
│   │   ├── router.py             ← etiology router
│   │   ├── stgnn.py              ← ST-GNN inference
│   │   ├── tft.py                ← TFT inference
│   │   ├── icmr.py               ← translation layer
│   │   └── prophet_fallback.py
│   ├── data/
│   │   ├── signals.py            ← weather + pytrends fetchers
│   │   └── scheduler.py          ← daily batch jobs
│   ├── kafka/
│   │   ├── producer.py
│   │   └── consumers/
│   │       ├── po_generator.py
│   │       └── whatsapp_notifier.py
│   ├── cache/                    ← Redis helpers
│   ├── db/                       ← Supabase queries
│   ├── schemas.py                ← Pydantic models
│   ├── config.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── ml/                           ← Training code (run once, on Colab)
│   ├── train_stgnn.py
│   ├── train_tft.py
│   ├── build_adjacency.py        ← GeoJSON → adjacency matrix
│   ├── generate_synthetic.py     ← EpiClim × ICMR → training dataset
│   ├── artifacts/                ← .pt model files (gitignored, large)
│   └── notebooks/
│       ├── stgnn_training.ipynb  ← run on Colab
│       └── tft_training.ipynb
│
├── frontend/                     ← Streamlit (Phase 1)
│   ├── app.py
│   ├── views/
│   │   ├── map_view.py
│   │   ├── inventory_table.py
│   │   ├── signal_timeline.py
│   │   ├── hospital_brief.py
│   │   └── simulate.py
│   ├── components/               ← reusable Streamlit widgets
│   └── requirements.txt
│
├── data/
│   ├── raw/                      ← downloaded datasets (gitignored)
│   │   ├── epiclim/
│   │   ├── india_medicines/
│   │   └── india_geojson/
│   ├── icmr_rules.json           ← ICMR translation rules (committed)
│   └── seed/                     ← Supabase seed SQL scripts
│
├── infra/
│   ├── docker-compose.yml
│   ├── redis/
│   └── kafka/
│
└── agtechathon/                  ← planning docs (existing)
    └── docs/
```

---

## 11. Build Order

```
Phase 0 — Data Foundation (do this first, everything depends on it)
  [ ] Download EpiClim dataset → data/raw/epiclim/
  [ ] Download India Medicines Kaggle dataset → data/raw/india_medicines/
  [ ] Download India district GeoJSON (Datameet) → data/raw/india_geojson/
  [ ] Write ICMR rules JSON → data/icmr_rules.json
  [ ] Set up Supabase project → get credentials → add to .env
  [ ] Run DB migration (schema + seed hospitals, drugs, districts)

Phase 1 — ML Training (offline, Colab)
  [ ] build_adjacency.py → district adjacency matrix
  [ ] generate_synthetic.py → EpiClim × ICMR → training CSV
  [ ] stgnn_training.ipynb → train ST-GNN → download .pt artifact
  [ ] tft_training.ipynb → train TFT → download .pt artifact

Phase 2 — Backend Core (FastAPI ML service)
  [ ] ML inference endpoints (ST-GNN + TFT + router)
  [ ] ICMR translation layer
  [ ] Gemini LLM brief generation
  [ ] Redis prediction cache
  [ ] Weather + pytrends signal fetchers
  [ ] Daily batch scheduler
  [ ] Kafka producer

Phase 3 — Kafka Consumers
  [ ] PO generator consumer
  [ ] WhatsApp notifier consumer (Twilio)
  [ ] Twilio webhook handler (YES reply → approve PO)

Phase 4 — Go API Gateway
  [ ] Protobuf definitions
  [ ] gRPC client to FastAPI
  [ ] JWT middleware (Supabase token verification)
  [ ] REST routes with role enforcement
  [ ] Rate limiting

Phase 5 — Streamlit UI (Phase 1 frontend)
  [ ] Map view (pydeck) — district heatmap with risk colors
  [ ] Hospital inventory table
  [ ] Signal timeline (weather + search + epid)
  [ ] Hospital Brief panel
  [ ] "Simulate Monsoon Surge" button
  [ ] Login flow (Supabase Auth)

Phase 6 — Integration & Polish
  [ ] End-to-end test: weather spike → Kafka → PO → WhatsApp
  [ ] Docker Compose for full local stack
  [ ] GitHub Actions CI
  [ ] Deploy to Render + Streamlit Cloud + Supabase Cloud

Phase 7 — Next.js Frontend (after backend is THRIVING)
  [ ] Scaffold Next.js 14 App Router
  [ ] Lift deck.gl map from AgTechathon
  [ ] Build all views as React components
  [ ] Same Go gateway API, zero backend changes
  [ ] Deploy to Vercel
```

---

## 12. What We Commit To Deliver vs. What We Don't

### We build and deliver for real:
- ST-GNN trained on real EpiClim data
- TFT trained on synthetic data generated from real epidemiology × ICMR rules  
- Supabase RLS with 3 real user roles (log in as each, see different data)
- Real OpenWeatherMap signals driving real risk score changes
- Real Twilio WhatsApp approval flow
- Real Kafka event bus connecting outbreak detection → PO → notification
- Real Gemini LLM brief generation (not templated strings)
- Real Go gRPC gateway (not a mock, actually routes traffic)

### We are explicit about (not fake, just architectural choices):
- Models are pre-trained, not continuously retrained (we say this: "v1 uses offline-trained artifacts; v2 roadmap includes MLflow continuous retraining")
- pytrends has a 1-7 day lag — not real-time. We say: "search signals are weekly aggregated with ~72h lag"
- No live hospital ERP integration — pharmacists manually update inventory. We say: "designed for ERP webhook integration; currently manual entry"

---

*Last updated: 2026-06-03*
*Stack version: 1.0 — locked for AgTechathon 2.0 2K26 build*
