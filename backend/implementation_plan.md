# Pharmasense — Backend Implementation Plan
### Status: LOCKED ✅ | Ready for Execution

> **Philosophy:** This is a product, not a project. Every decision is made with scalability, maintainability, and production credibility as non-negotiables. We build the way companies actually build.

---

## Resolved Decisions (No More Open Questions)

| Decision | Choice | Rationale |
|---|---|---|
| Gateway → ML service comms | **gRPC + Protobuf** | Industry standard for internal service-to-service. Adds 0 latency overhead over REST, adds compile-time contract safety. Judges will notice this. |
| Event bus | **Apache Kafka (Upstash)** | Real event-driven architecture. Decoupled consumers (PO + WhatsApp). Replayable. Companies like Swiggy/Zepto actually run this for supply chain. |
| Prediction cache | **Redis (Upstash)** | Sub-1ms reads for hot paths. 4 distinct use cases (see below). |
| NCD demand storage | **Hybrid**: in-memory compute for serving + second Supabase project for training data | Production never touches the 168MB file. ML notebooks use the dedicated training project. Zero storage pressure on the operational DB. |
| Supabase architecture | **Dual project** | Project A: Operational (hospitals, inventory, POs, risk_scores, weather, search, epid_weekly). Project B: Training data only (ncd_demand_weekly, full malaria_weekly). Backend reads from Project A only. |
| NCD in production | **In-memory MBQ generation** | ML service computes NCD demand on-demand using the same MBQ logic as the notebooks. Outputs (demand_forecasts table) are stored in Project A. Inputs are never in the operational DB. |

---

## Complete Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  React Frontend (Next.js 14)                                    │
│  deck.gl maps | Recharts | Tailwind | Supabase Auth JS          │
└─────────────────────┬───────────────────────────────────────────┘
                      │ HTTPS / REST + JSON
                      │ Bearer {supabase_jwt}
┌─────────────────────▼───────────────────────────────────────────┐
│  GO API GATEWAY  (Gin v1.10)  :8080                             │
│                                                                 │
│  ┌──────────────┐  ┌─────────────┐  ┌───────────────────────┐  │
│  │ JWT Middleware│  │ Rate Limiter│  │ Request Logger (JSON) │  │
│  │ (Supabase HS │  │ (Redis INCR │  │ + OpenTelemetry trace │  │
│  │  256 secret) │  │  sliding    │  │   IDs                 │  │
│  │ role extract │  │  window)    │  │                       │  │
│  └──────────────┘  └─────────────┘  └───────────────────────┘  │
│                                                                 │
│  Routes: /api/districts  /api/hospitals  /api/purchase-orders  │
│          /api/simulate   /hooks/whatsapp  /health  /docs        │
└─────────────────────┬───────────────────────────────────────────┘
                      │ gRPC  (internal, port 50051)
                      │ Protobuf  (pharmasense.proto)
┌─────────────────────▼───────────────────────────────────────────┐
│  FASTAPI ML SERVICE  (Python 3.11, asyncio)  :8000 / :50051    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  ETIOLOGY ROUTER                                        │   │
│  │  communicable → SpatialEnsemble (ST-GNN + GraphWaveNet) │   │
│  │  NCD/baseline → DemandEnsemble  (TFT + N-BEATS)         │   │
│  │  any           → AnomalyDetector (IF + IQR)             │   │
│  │  drug demand   → LightGBM + ICMR Translation Layer      │   │
│  │  fallback      → Prophet (when PT artifacts missing)     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  LP PROCUREMENT OPTIMIZER  (scipy HiGHS)                 │  │
│  │  Forecast → minimize procurement cost s.t. no stockout   │  │
│  │  Outputs: order_qty, urgency, weeks_of_cover per drug    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌────────────────────┐  ┌───────────────────────────────────┐ │
│  │  GEMINI 1.5 FLASH  │  │  APSCHEDULER                      │ │
│  │  Hospital briefs   │  │  Daily 06:00 IST batch            │ │
│  │  JSON output mode  │  │  Hourly weather anomaly check     │ │
│  │  Cached 24h Redis  │  │                                   │ │
│  └────────────────────┘  └───────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  SIGNAL FETCHERS                                          │ │
│  │  OpenWeatherMap → 50 district centroids + IDW interpolate │ │
│  │  pytrends       → state-level symptom search indices      │ │
│  └───────────────────────────────────────────────────────────┘ │
└────────────┬────────────────────────────────┬───────────────────┘
             │                                │
    ┌────────▼──────────┐          ┌──────────▼──────────────────┐
    │  REDIS (Upstash)  │          │  KAFKA (Upstash)            │
    │                   │          │  Topic: outbreak_events      │
    │  risk cache 24h   │          │                             │
    │  brief cache 24h  │          │  Consumer Group A:          │
    │  rate limit 60s   │          │  po_generator               │
    │  JWT blacklist    │          │  → writes PO to Supabase    │
    │                   │          │                             │
    └───────────────────┘          │  Consumer Group B:          │
                                   │  whatsapp_notifier          │
                                   │  → Twilio API               │
                                   └─────────────────────────────┘
                                             │
┌────────────────────────────────────────────▼───────────────────┐
│  SUPABASE PROJECT A — Operational DB  (PostgreSQL 15 + RLS)    │
│                                                                 │
│  districts | drugs | hospitals | inventory | inv_transactions  │
│  epid_weekly | weather_signals | search_signals                │
│  risk_scores | demand_forecasts | purchase_orders | audit_log  │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│  SUPABASE PROJECT B — Training Data  (ML notebooks only)       │
│                                                                 │
│  ncd_demand_weekly (168MB) | malaria_weekly (29MB)             │
│  Read-only from notebooks. Never touched by production service. │
└────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack — What We're Using & Why (Judge-Facing Narrative)

| Layer | Tech | Why It's Production-Grade |
|---|---|---|
| API Gateway | **Go + Gin** | Goroutine-per-request, ~35K req/sec on single core. Same stack as Uber's dispatch service. |
| Internal comms | **gRPC + Protobuf** | Type-safe, bi-directional streaming, 7x smaller payload than JSON. Used by every major tech company for internal services. |
| ML Service | **FastAPI + asyncio** | Non-blocking I/O means 1 process handles hundreds of concurrent inference requests while waiting for DB/Redis. |
| Cache | **Redis** | Sub-1ms reads. Eliminates 640 DB round-trips on every daily batch run. 4 production-grade use cases. |
| Event bus | **Apache Kafka** | Persistent, replayable event log. If WhatsApp consumer crashes, it replays from offset — zero message loss. |
| Optimizer | **scipy HiGHS LP** | Open-source Operations Research solver used by Google OR-Tools. Turns predictions into prescriptions. |
| LLM | **Gemini 1.5 Flash** | 1M token context window. Can consume a full district's data history in one prompt. |
| DB | **Supabase PostgreSQL 15 + PostGIS** | PostGIS spatial queries for district adjacency. Row Level Security enforces role isolation at the DB layer. |

---

## Redis — 4 Production Use Cases

```
Use Case 1: PREDICTION CACHE
  Key:  risk:{district_id}:{disease}:{YYYY-MM-DD}
  TTL:  24h (invalidated early on weather anomaly)
  Why:  640 districts × 4 diseases = 2,560 potential ML inferences/day.
        With cache, only ~50 unique requests actually hit the model.

Use Case 2: LLM BRIEF CACHE
  Key:  brief:{hospital_id}:{YYYY-MM-DD}
  TTL:  24h (invalidated on inventory change)
  Why:  Gemini Flash has 60 RPM quota. Cache prevents quota exhaust.
        Also reduces P99 latency from ~3s → ~5ms for repeat views.

Use Case 3: RATE LIMITING (sliding window counter)
  Key:  rl:{user_id}:{endpoint}:{60s_window_epoch}
  TTL:  70s (slightly over window)
  Why:  Prevents a single pharmacist from hammering the ML service.
        Protects against accidental infinite loops in the React frontend.

Use Case 4: JWT REVOCATION BLACKLIST
  Key:  jwt_revoked:{jti}
  TTL:  Matches token expiry
  Why:  Supabase JWTs are stateless — we can't invalidate them server-side
        without this. Critical for "log out all sessions" functionality.
```

---

## Kafka — 2 Consumer Groups (Same Topic, Different Purposes)

```
Producer publishes to: outbreak_events
  Trigger condition: risk_score >= 0.70 AND delta from last score > 0.10
  
  Payload:
  {
    "event_id": "uuid",
    "district_id": "27_025",
    "disease": "dengue",
    "risk_score": 0.82,
    "risk_level": "HIGH",
    "triggered_at": "2026-06-05T00:30:00Z",
    "hospitals": [{"id": "...", "name": "...", "shortfall_drugs": [...]}],
    "expires_at": "2026-06-06T00:30:00Z"
  }

Consumer Group A: po_generator
  - Reads every outbreak_event
  - For each hospital with shortfall, runs LP optimizer
  - Writes purchase_order (status=PENDING) to Supabase
  - Idempotent: checks for existing PENDING PO before creating

Consumer Group B: whatsapp_notifier  
  - Reads same events independently
  - Waits 60s (so PO is guaranteed to exist in DB)
  - Fetches PO details, composes message
  - Sends via Twilio WhatsApp Business API
  - Updates whatsapp_sent=True, stores msg_sid
  - On Twilio failure: retries 3x with backoff, logs to audit_log
```

---

## Complete File Tree (Every File We're Creating)

```
pharmasense/
│
├── .env                              ← secrets (gitignored)
├── .env.example                      ← MODIFY: add all new vars
├── docker-compose.yml                ← NEW: full local stack
│
├── gateway/                          ← Go API Gateway
│   ├── go.mod                        ← NEW
│   ├── go.sum                        ← NEW (generated)
│   ├── main.go                       ← NEW: Gin server, startup
│   ├── Dockerfile                    ← NEW: multi-stage Go build
│   ├── grpc/
│   │   └── proto/
│   │       └── pharmasense.proto     ← NEW: gRPC service contract
│   ├── middleware/
│   │   ├── auth.go                   ← NEW: JWT verify + role extract
│   │   ├── rate_limit.go             ← NEW: Redis sliding window
│   │   └── logger.go                 ← NEW: structured JSON logging
│   └── routes/
│       ├── districts.go              ← NEW
│       ├── hospitals.go              ← NEW
│       ├── orders.go                 ← NEW
│       ├── simulate.go               ← NEW
│       └── webhooks.go               ← NEW: Twilio webhook handler
│
├── backend/                          ← FastAPI ML Service
│   ├── main.py                       ← NEW: FastAPI app + lifespan
│   ├── config.py                     ← NEW: Pydantic Settings
│   ├── schemas.py                    ← NEW: all Pydantic v2 models
│   ├── requirements.txt              ← NEW: pinned deps
│   ├── Dockerfile                    ← NEW: multi-stage Python build
│   │
│   ├── grpc/
│   │   ├── server.py                 ← NEW: gRPC servicer impl
│   │   └── generated/                ← NEW: protoc output (auto)
│   │       ├── pharmasense_pb2.py
│   │       └── pharmasense_pb2_grpc.py
│   │
│   ├── ml/
│   │   ├── loader.py                 ← NEW: ModelRegistry singleton
│   │   ├── router.py                 ← NEW: Etiology Router
│   │   ├── stgnn.py                  ← NEW: ST-GNN inference wrapper
│   │   ├── graphwavenet.py           ← NEW: GWN inference wrapper
│   │   ├── tft.py                    ← NEW: TFT inference wrapper
│   │   ├── nbeats.py                 ← NEW: N-BEATS wrapper
│   │   ├── prophet_fallback.py       ← NEW: Prophet wrapper
│   │   ├── anomaly.py                ← NEW: Isolation Forest wrapper
│   │   ├── lgbm.py                   ← NEW: LightGBM wrapper
│   │   ├── ensemble.py               ← NEW: SpatialEnsemble + DemandEnsemble
│   │   ├── icmr.py                   ← NEW: ICMR Translation Layer
│   │   ├── ncd_generator.py          ← NEW: in-memory MBQ NCD demand
│   │   ├── gemini_brief.py           ← NEW: LLM brief generator
│   │   └── lp_optimizer.py           ← NEW: thin wrapper over ml/optimizer/
│   │
│   ├── api/
│   │   ├── risk.py                   ← NEW: /risk routes
│   │   ├── forecast.py               ← NEW: /forecast routes
│   │   ├── brief.py                  ← NEW: /brief routes
│   │   ├── signals.py                ← NEW: /signals routes
│   │   ├── simulate.py               ← NEW: /simulate routes
│   │   ├── orders.py                 ← NEW: /orders routes
│   │   └── admin.py                  ← NEW: /admin/batch routes
│   │
│   ├── cache/
│   │   ├── client.py                 ← NEW: async Redis pool
│   │   ├── keys.py                   ← NEW: centralized key schema
│   │   ├── decorators.py             ← NEW: @cache_response
│   │   └── invalidation.py           ← NEW: targeted cache busting
│   │
│   ├── data/
│   │   ├── weather.py                ← NEW: OWM fetcher + IDW interp
│   │   ├── search_trends.py          ← NEW: pytrends fetcher
│   │   └── scheduler.py             ← NEW: APScheduler daily + hourly
│   │
│   ├── kafka/
│   │   ├── producer.py               ← NEW: outbreak_events publisher
│   │   └── consumers/
│   │       ├── po_generator.py       ← NEW: PO creation consumer
│   │       ├── whatsapp_notifier.py  ← NEW: Twilio WA consumer
│   │       └── runner.py             ← NEW: consumer lifecycle mgmt
│   │
│   └── db/
│       ├── client.py                 ← NEW: Supabase + psycopg2
│       └── queries/
│           ├── risk.py               ← NEW
│           ├── inventory.py          ← NEW
│           ├── signals.py            ← NEW
│           ├── orders.py             ← NEW
│           └── districts.py         ← NEW
│
└── ml/
    └── optimizer/
        ├── ensemble.py               ← EXISTS ✅ (wire in)
        └── procurement_lp.py         ← EXISTS ✅ (wire in)
```

---

## Proposed Changes (Detailed)

---

### Component 1: Config & Environment

#### [MODIFY] `.env.example`
Add all new service vars:
```bash
# Supabase — Project A (Operational)
SUPABASE_URL_A=
SUPABASE_ANON_KEY_A=
SUPABASE_SERVICE_ROLE_KEY_A=
SUPABASE_DB_URL_A=postgresql://...  # direct psycopg2 connection

# Supabase — Project B (Training Data — ML notebooks only)
SUPABASE_URL_B=
SUPABASE_SERVICE_ROLE_KEY_B=

# Redis (Upstash)
REDIS_URL=rediss://...
REDIS_MAX_CONNECTIONS=20

# Kafka (Upstash)
KAFKA_BOOTSTRAP_SERVERS=
KAFKA_API_KEY=
KAFKA_API_SECRET=
KAFKA_OUTBREAK_TOPIC=outbreak_events
KAFKA_CONSUMER_GROUP_PO=pharmasense-po-generator
KAFKA_CONSUMER_GROUP_WA=pharmasense-whatsapp-notifier

# ML Service
ML_SERVICE_HOST=backend
ML_SERVICE_GRPC_PORT=50051
ML_SERVICE_HTTP_PORT=8000
STGNN_MODEL_PATH=ml/artifacts/stgnn_best.pt
GWN_MODEL_PATH=ml/artifacts/graphwavenet_best.pt
TFT_MODEL_PATH=ml/artifacts/tft_best.ckpt
NBEATS_MODEL_PATH=ml/artifacts/nbeats_ncd_latest.pt
PROPHET_MODEL_PATH=ml/artifacts/prophet_models.pkl
ANOMALY_MODEL_PATH=ml/artifacts/anomaly_detector.pkl
LGBM_MODEL_PATH=ml/artifacts/lgbm_demand.pkl

# Go Gateway
GATEWAY_PORT=8080
SUPABASE_JWT_SECRET=   # from Supabase dashboard > Settings > API > JWT Secret

# External APIs
GOOGLE_GEMINI_API_KEY=
OPENWEATHER_API_KEY=
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TWILIO_WEBHOOK_SECRET=

# App
APP_ENV=development
LOG_LEVEL=INFO
```

#### [NEW] `backend/config.py`
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    
    # Supabase
    supabase_url_a: str
    supabase_service_role_key_a: str
    supabase_db_url_a: str
    
    # Redis
    redis_url: str
    redis_max_connections: int = 20
    
    # Kafka
    kafka_bootstrap_servers: str
    kafka_api_key: str
    kafka_api_secret: str
    kafka_outbreak_topic: str = 'outbreak_events'
    kafka_consumer_group_po: str = 'pharmasense-po-generator'
    kafka_consumer_group_wa: str = 'pharmasense-whatsapp-notifier'
    
    # Model paths
    stgnn_model_path: str = 'ml/artifacts/stgnn_best.pt'
    gwn_model_path: str   = 'ml/artifacts/graphwavenet_best.pt'
    tft_model_path: str   = 'ml/artifacts/tft_best.ckpt'
    # ...etc
    
    # External APIs
    google_gemini_api_key: str
    openweather_api_key: str
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_from: str
    
    # Gateway
    supabase_jwt_secret: str
    
    # App
    app_env: str = 'development'
    log_level: str = 'INFO'

settings = Settings()
```

---

### Component 2: Protobuf Contract

#### [NEW] `gateway/grpc/proto/pharmasense.proto`
```protobuf
syntax = "proto3";
package pharmasense.v1;
option go_package = "gateway/grpc/gen;pharmasensepb";

service PharmasenseML {
  rpc GetDistrictRisk      (RiskRequest)         returns (RiskResponse);
  rpc GetAllDistrictsRisk  (AllRiskRequest)      returns (AllRiskResponse);
  rpc GetHospitalForecast  (ForecastRequest)     returns (ForecastResponse);
  rpc GetHospitalBrief     (BriefRequest)        returns (BriefResponse);
  rpc RunSimulation        (SimulationRequest)   returns (SimulationResponse);
  rpc GetSignalTimeline    (TimelineRequest)     returns (TimelineResponse);
  rpc TriggerBatch         (BatchTriggerReq)     returns (BatchStatusResponse);
  rpc GetHealth            (HealthRequest)       returns (HealthResponse);
}

message RiskRequest {
  string district_id = 1;
  repeated string diseases = 2;  // empty = all 4
  string date = 3;               // YYYY-MM-DD, empty = today
}

message RiskScore {
  string disease       = 1;
  double score         = 2;
  string risk_level    = 3;   // HIGH / MEDIUM / LOW
  int32  predicted_cases = 4;
  string model_used    = 5;
  double weather_score = 6;
  double search_score  = 7;
  double epid_baseline = 8;
  bool   is_anomaly    = 9;
}

message RiskResponse {
  string district_id   = 1;
  string district_name = 2;
  string state         = 3;
  repeated RiskScore scores = 4;
  string computed_at   = 5;
  bool   cache_hit     = 6;
}

message ForecastRequest {
  string hospital_id    = 1;
  int32  horizon_weeks  = 2;
  optional double budget_inr = 3;
}

message DrugOrder {
  string drug_id       = 1;
  string drug_name     = 2;
  double order_quantity = 3;
  double order_cost_inr = 4;
  double weeks_of_cover = 5;
  string urgency        = 6;  // CRITICAL / HIGH / NORMAL / DEFER
  string reason         = 7;
}

message ForecastResponse {
  string hospital_id          = 1;
  string optimization_status  = 2;
  repeated DrugOrder orders   = 3;
  double total_cost_inr       = 4;
  repeated string drugs_at_risk = 5;
}

message BriefRequest  { string hospital_id = 1; }
message BriefResponse { string brief_markdown = 1; bool cache_hit = 2; }

message SimulationRequest {
  repeated string district_ids = 1;
  double intensity             = 2;  // 0.0 - 1.0
  int32  duration_weeks        = 3;
}

message SimulationResponse {
  map<string, double> baseline_scores  = 1;
  map<string, double> simulated_scores = 2;
  map<string, double> delta_scores     = 3;
}

message TimelineRequest  { string district_id = 1; int32 days = 2; }
message TimelineResponse { repeated TimelinePoint points = 1; }
message TimelinePoint    {
  string date        = 1;
  double rain_mm     = 2;
  double humidity    = 3;
  double temp_c      = 4;
  int32  search_idx  = 5;
  int32  epid_cases  = 6;
  string disease     = 7;
}

message AllRiskRequest  {}
message AllRiskResponse { repeated RiskResponse districts = 1; }
message BatchTriggerReq { bool force = 1; }
message BatchStatusResponse {
  string last_run_at     = 1;
  bool   success         = 2;
  int32  districts_scored = 3;
  string error_message   = 4;
}
message HealthRequest   {}
message HealthResponse  {
  bool   ok             = 1;
  map<string, bool> models = 2;  // model_name -> is_loaded
  bool   redis_ok       = 3;
  bool   db_ok          = 4;
  bool   kafka_ok       = 5;
}
```

---

### Component 3: ML Inference Layer

#### [NEW] `backend/ml/loader.py` — ModelRegistry Singleton
```python
"""
Singleton model registry. Loads all artifacts at startup.
Exposes is_ready(model_name) for health checks.
Falls back gracefully when artifacts are missing.
"""

class ModelRegistry:
    _instance = None
    
    def __init__(self):
        self._models: dict = {}
        self._ready: dict[str, bool] = {}
    
    def load_all(self):
        self._load_stgnn()
        self._load_graphwavenet()
        self._load_tft()          # non-fatal if missing
        self._load_nbeats()
        self._load_prophet()
        self._load_anomaly()
        self._load_lgbm()
        self._load_district_index()
        self._load_icmr_rules()
        self._load_disease_drug_map()
    
    def is_ready(self, name: str) -> bool:
        return self._ready.get(name, False)
    
    def get(self, name: str):
        return self._models.get(name)
    
    @property
    def health_map(self) -> dict[str, bool]:
        return dict(self._ready)
```

#### [NEW] `backend/ml/router.py` — Etiology Router
```python
from enum import Enum

COMMUNICABLE = {'dengue', 'malaria', 'cholera', 'acute_diarrhoeal_disease'}
NCD = {'hypertension', 'type2_diabetes', 'tuberculosis', 'anaemia',
       'viral_fever_urti', 'acute_gastritis_dyspepsia', 'musculoskeletal_pain',
       'asthma_copd_respiratory', 'helminth_infestation',
       'uti_bacterial_infections', 'maternal_anc_supplements'}

class InferenceStrategy(Enum):
    SPATIAL_ENSEMBLE  = 'spatial'    # ST-GNN + GWN → communicable
    DEMAND_ENSEMBLE   = 'demand'     # TFT + N-BEATS → NCD
    PROPHET_FALLBACK  = 'prophet'    # when PT models not loaded
    ANOMALY_ONLY      = 'anomaly'    # supplement to spatial

def route(disease: str, registry) -> InferenceStrategy:
    if disease in COMMUNICABLE:
        if registry.is_ready('stgnn') or registry.is_ready('graphwavenet'):
            return InferenceStrategy.SPATIAL_ENSEMBLE
        return InferenceStrategy.PROPHET_FALLBACK
    if disease in NCD:
        if registry.is_ready('tft') or registry.is_ready('nbeats'):
            return InferenceStrategy.DEMAND_ENSEMBLE
        return InferenceStrategy.PROPHET_FALLBACK
    return InferenceStrategy.PROPHET_FALLBACK
```

#### [NEW] `backend/ml/icmr.py` — ICMR Translation Layer
```python
"""
Loads data/icmr_rules.json.
Converts (disease, predicted_cases, severity_mix) → {drug_id: units_needed}.
This is the clinical bridge between 'cases predicted' and 'drugs to order'.
"""

class ICMRTranslator:
    def translate(
        self,
        disease: str,
        predicted_cases: int,
        severity_mix: dict = None   # {'mild_pct': 0.8, 'severe_pct': 0.2}
    ) -> dict[str, float]:
        """Returns {drug_key: total_units_needed} over forecast horizon."""
        ...
```

#### [NEW] `backend/ml/ncd_generator.py` — In-Memory NCD Demand
```python
"""
Generates NCD weekly demand for a district IN MEMORY using MBQ logic.
Identical algorithm to the Colab notebooks — no DB dependency.
Called by the demand ensemble when NCD condition is requested.
Returns a DataFrame with (week_start_date, condition, patients_est).
"""

class NCDDemandGenerator:
    def generate_for_district(
        self,
        district: str,
        state: str,
        population: int,
        weeks_back: int = 52,
        weeks_forward: int = 4,
    ) -> pd.DataFrame:
        ...
```

---

### Component 4: FastAPI Core

#### [NEW] `backend/main.py`
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
import structlog

@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    log = structlog.get_logger()
    log.info("pharmasense.startup.begin")
    
    registry.load_all()           # ML models
    await redis_client.ping()     # Redis
    await db_client.verify()      # Supabase
    grpc_server.start()           # gRPC server on :50051
    scheduler.start()             # APScheduler
    kafka_runner.start()          # Kafka consumers
    
    log.info("pharmasense.startup.complete",
             models=registry.health_map)
    
    yield  # ← app is running
    
    # SHUTDOWN
    await kafka_runner.stop()
    scheduler.shutdown()
    grpc_server.stop(grace=5)
    await redis_client.aclose()

app = FastAPI(
    title="Pharmasense ML Service",
    version="1.0.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(risk_router,     prefix="/api/v1")
app.include_router(forecast_router, prefix="/api/v1")
app.include_router(brief_router,    prefix="/api/v1")
app.include_router(signals_router,  prefix="/api/v1")
app.include_router(simulate_router, prefix="/api/v1")
app.include_router(orders_router,   prefix="/api/v1")
app.include_router(admin_router,    prefix="/api/v1")
```

---

### Component 5: API Route Handlers

#### [NEW] `backend/api/risk.py`
```
GET /api/v1/risk/district/{district_id}
  Query: ?diseases=dengue,malaria&date=2026-06-05

Flow:
  1. Check Redis: risk:{district_id}:{disease}:{date}
  2. Cache hit → return immediately (cache_hit=True)
  3. Cache miss → load weather + search signals from DB
  4. For each disease:
     a. Route via EtiologyRouter
     b. Run inference (spatial or demand ensemble)
     c. Run anomaly detector
     d. Apply ICMR translation → drug demand estimates
  5. Write to risk_scores table (upsert)
  6. Cache all scores → Redis TTL 24h
  7. Check outbreak threshold → publish to Kafka if triggered
  8. Return RiskResponse
```

#### [NEW] `backend/api/forecast.py`
```
GET /api/v1/forecast/hospital/{hospital_id}?horizon_weeks=4&budget_inr=50000

Flow:
  1. Get hospital → district_id, population
  2. Get latest risk_scores for district (from cache or DB)
  3. Get current inventory for hospital (from DB)
  4. For each drug linked to high-risk diseases:
     a. Run ICMR translation → demand_q50, demand_q90 arrays
     b. Attach current_stock from inventory
  5. Run LP Procurement Optimizer with all drug forecasts + budget
  6. Return ForecastResponse (orders sorted by urgency)
```

#### [NEW] `backend/api/brief.py`
```
GET /api/v1/brief/hospital/{hospital_id}

Flow:
  1. Check Redis: brief:{hospital_id}:{today}
  2. Cache hit → return (cache_hit=True)
  3. Assemble context:
     - Hospital details (name, tier, district, bed_count)
     - Top 5 inventory items at risk (stock < reorder_point)
     - District risk scores (all diseases, last 7 days)
     - Weather signals (last 7 days, rain + humidity trend)
     - Search signals (last 4 weeks, velocity)
     - LP optimizer top 3 urgent orders
  4. Call Gemini 1.5 Flash (JSON output mode)
  5. Cache response → Redis TTL 24h
  6. Return brief markdown
```

#### [NEW] `backend/api/simulate.py`
```
POST /api/v1/simulate/monsoon
Body: {district_ids: [...], intensity: 0.8, duration_weeks: 4}

Flow:
  1. Fetch current weather + search signals for districts
  2. Apply intensity multiplier to rain_mm, humidity_pct
  3. Re-run inference WITHOUT writing to DB or Redis
  4. Return delta: {district_id: {disease: {baseline, simulated, delta}}}
  
IMPORTANT: Pure read + compute. No side effects. No Kafka events.
```

---

### Component 6: Signal Fetchers

#### [NEW] `backend/data/weather.py`
```python
"""
OpenWeatherMap strategy:
- Direct fetch for ~50 major cities/district HQs
- IDW interpolation for remaining ~590 districts
  using 3 nearest direct-fetch neighbors weighted by 1/d²
- Writes to weather_signals table
- Computes weather_score:
    score = sigmoid(0.3 * rain_normalized + 0.5 * humidity_normalized
                  + 0.2 * temp_deviation_from_optimal)
  where "optimal" for dengue breeding = 27-32°C, humidity > 70%
"""

class WeatherFetcher:
    DIRECT_FETCH_DISTRICTS = [...]  # 50 centroids, pre-defined
    
    async def fetch_and_persist(self) -> int:
        """Returns number of districts updated."""
        ...
    
    async def compute_weather_score(self, district_id: str) -> float:
        ...
```

#### [NEW] `backend/data/search_trends.py`
```python
"""
pytrends strategy:
- Query: ["dengue fever", "malaria symptoms", "loose motions",
          "cholera treatment", "diarrhea medicine"]
- Geo: IN-{state_code} per state
- Timeframe: today 3-m (rolling, for trend context)
- Rate limit protection: max 2 req/sec, 10s cooldown between states
- search_velocity = (this_week_index - last_week_index) / last_week_index
"""

class SearchTrendsFetcher:
    async def fetch_and_persist(self) -> int:
        ...
```

#### [NEW] `backend/data/scheduler.py`
```python
# APScheduler with asyncio backend

async def daily_batch_06am_IST():
    """
    Full system run. Logs to audit_log. Updates batch:status in Redis.
    Steps:
    1. fetch_weather()
    2. fetch_search_trends()
    3. run_inference_all_districts()  # parallel, up to 16 concurrent
    4. upsert_risk_scores()
    5. run_procurement_all_hospitals()
    6. publish_outbreak_events()      # triggers PO + WhatsApp consumers
    7. redis_client.set("batch:status:last", json.dumps({...}))
    """

async def hourly_weather_anomaly_check():
    """
    Lightweight. Only re-runs inference for districts where:
    rain_mm > 40 AND humidity > 80 AND 3 consecutive hours.
    Invalidates Redis cache for those districts.
    """
```

---

### Component 7: Go API Gateway

#### [NEW] `gateway/middleware/auth.go`
```go
// Verifies Supabase JWT using HS256 + SUPABASE_JWT_SECRET
// Extracts user_metadata fields → attaches to Gin context:
//   ctx.Set("role", role)
//   ctx.Set("hospital_id", hospitalID)
//   ctx.Set("district_name", districtName)
//   ctx.Set("state", state)
//   ctx.Set("user_id", userID)
//
// Checks Redis jwt_revoked:{jti} → 401 if revoked
// 
// Returns 401 on: missing header, invalid signature, expired token, revoked
// Returns 403 on: role not in allowed set for this route
```

#### [NEW] `gateway/middleware/rate_limit.go`
```go
// Redis sliding window counter
// Limits per role per endpoint per 60s:
//   state_minister:  1000 req/min  (bulk map loads)
//   district_officer: 500 req/min
//   pharmacist:       200 req/min
//
// Key: rl:{user_id}:{route_pattern}:{window}
// INCR + EXPIRE atomically via Lua script (prevents TOCTOU race)
// Returns 429 with Retry-After header
```

#### [NEW] `gateway/routes/hospitals.go`
```go
// Role enforcement at route level:
// GET /api/hospitals        → all roles, but SQL RLS scopes result
// GET /api/hospitals/:id    → all roles
// GET /api/hospitals/:id/inventory → all roles
// GET /api/hospitals/:id/brief    → all roles
//
// Gateway does NOT do the data filtering — Supabase RLS does.
// Gateway only ensures the JWT is valid and role is authenticated.
```

---

### Component 8: Kafka Integration Detail

#### [NEW] `backend/kafka/producer.py`
```python
"""
Outbreak event publisher.
Threshold: risk_score >= 0.70 AND |score - prev_score| >= 0.10
This prevents spamming the same alert every hour for a known HIGH district.
Uses prev_score from Redis cache to compute delta.
"""

class OutbreakProducer:
    async def maybe_publish(
        self,
        district_id: str,
        disease: str,
        new_score: float,
        hospitals: list,
    ) -> bool:
        prev_score = await redis.get(f"prev_risk:{district_id}:{disease}")
        delta = abs(new_score - float(prev_score or 0))
        if new_score >= 0.70 and (prev_score is None or delta >= 0.10):
            await self._publish(...)
            await redis.set(f"prev_risk:{district_id}:{disease}", new_score, ex=86400)
            return True
        return False
```

#### [NEW] `backend/kafka/consumers/po_generator.py`
```python
"""
Idempotent PO creation.
Checks: SELECT id FROM purchase_orders 
        WHERE hospital_id=? AND drug_id=? AND status='PENDING'
        AND created_at > now() - interval '24h'
If exists → skip. If not → create.
This prevents duplicate POs if consumer restarts and replays.
"""
```

#### [NEW] `backend/kafka/consumers/whatsapp_notifier.py`
```python
"""
WhatsApp message format (via Twilio):
"🏥 Pharmasense Alert
 Hospital: {name} | District: {district}
 ⚠️ {disease} outbreak predicted (Risk: {level})
 
 Critical Drug Shortfall:
 • {drug_1}: {qty} units needed (depletes in {days}d)
 • {drug_2}: {qty} units needed (depletes in {days}d)
 
 Auto PO: ₹{total_cost} | Reply YES to approve, NO to defer"

On YES reply → webhook → Gateway → DB update PO status=APPROVED
"""
```

---

### Component 9: Docker Compose

#### [NEW] `docker-compose.yml`
```yaml
version: '3.9'
services:
  
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
  
  zookeeper:
    image: confluentinc/cp-zookeeper:7.6.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
    healthcheck:
      test: ["CMD", "nc", "-z", "localhost", "2181"]
  
  kafka:
    image: confluentinc/cp-kafka:7.6.0
    depends_on: [zookeeper]
    ports: ["9092:9092"]
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    healthcheck:
      test: ["CMD", "kafka-topics", "--bootstrap-server", "localhost:9092", "--list"]
  
  backend:
    build: ./backend
    ports: ["8000:8000", "50051:50051"]
    volumes:
      - ./ml/artifacts:/app/ml/artifacts:ro
      - ./data/icmr_rules.json:/app/data/icmr_rules.json:ro
      - ./data/seed/disease_drug_map.csv:/app/data/seed/disease_drug_map.csv:ro
      - ./ml/data/district_index.json:/app/ml/data/district_index.json:ro
    env_file: .env
    depends_on:
      redis: { condition: service_healthy }
      kafka: { condition: service_healthy }
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      start_period: 60s   # give models time to load
  
  gateway:
    build: ./gateway
    ports: ["8080:8080"]
    env_file: .env
    depends_on:
      backend: { condition: service_healthy }
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
```

---

## Build Sequence — Strict Dependency Order

```
PHASE 1: Foundation (no ML, no external APIs)
─────────────────────────────────────────────
Step 1:  .env.example + config.py              (30 min)
Step 2:  schemas.py                            (45 min)
Step 3:  backend/db/client.py + queries/       (60 min)
Step 4:  backend/cache/client.py + keys.py     (30 min)
Step 5:  backend/cache/decorators.py           (20 min)
Step 6:  gateway/grpc/proto/pharmasense.proto  (45 min)
           → protoc codegen (both Go + Python)

PHASE 2: ML Inference Layer
────────────────────────────
Step 7:  backend/ml/loader.py (ModelRegistry)  (45 min)
Step 8:  backend/ml/router.py (EtiologyRouter) (20 min)
Step 9:  backend/ml/stgnn.py                   (45 min)
Step 10: backend/ml/graphwavenet.py            (30 min)
Step 11: backend/ml/tft.py                     (45 min)
Step 12: backend/ml/nbeats.py                  (30 min)
Step 13: backend/ml/prophet_fallback.py        (20 min)
Step 14: backend/ml/anomaly.py                 (20 min)
Step 15: backend/ml/lgbm.py                    (20 min)
Step 16: backend/ml/ensemble.py (wire existing)(20 min)
Step 17: backend/ml/icmr.py                    (30 min)
Step 18: backend/ml/ncd_generator.py           (30 min)
Step 19: backend/ml/lp_optimizer.py (wire)     (20 min)
Step 20: backend/ml/gemini_brief.py            (45 min)

PHASE 3: FastAPI Service + gRPC
────────────────────────────────
Step 21: backend/main.py (lifespan + app)      (30 min)
Step 22: backend/api/risk.py                   (45 min)
Step 23: backend/api/forecast.py               (45 min)
Step 24: backend/api/brief.py                  (30 min)
Step 25: backend/api/signals.py                (30 min)
Step 26: backend/api/simulate.py               (30 min)
Step 27: backend/api/orders.py                 (30 min)
Step 28: backend/grpc/server.py                (60 min)
                          ↑
         [ CHECKPOINT: test /health, /risk, /forecast locally ]

PHASE 4: Data Signals + Scheduling
────────────────────────────────────
Step 29: backend/data/weather.py               (60 min)
Step 30: backend/data/search_trends.py         (45 min)
Step 31: backend/data/scheduler.py             (45 min)

PHASE 5: Kafka Pipeline
────────────────────────
Step 32: backend/kafka/producer.py             (45 min)
Step 33: backend/kafka/consumers/po_generator  (45 min)
Step 34: backend/kafka/consumers/whatsapp_notifier (45 min)
Step 35: backend/kafka/consumers/runner.py     (20 min)
                          ↑
         [ CHECKPOINT: trigger test event → verify PO + WA msg ]

PHASE 6: Go Gateway
────────────────────
Step 36: gateway/go.mod + main.go              (45 min)
Step 37: gateway/middleware/auth.go            (60 min)
Step 38: gateway/middleware/rate_limit.go      (30 min)
Step 39: gateway/middleware/logger.go          (20 min)
Step 40: gateway/routes/districts.go           (30 min)
Step 41: gateway/routes/hospitals.go           (30 min)
Step 42: gateway/routes/orders.go              (30 min)
Step 43: gateway/routes/simulate.go            (20 min)
Step 44: gateway/routes/webhooks.go            (30 min)
                          ↑
         [ CHECKPOINT: full request through gateway → gRPC → ML → response ]

PHASE 7: Docker + Dockerfiles
──────────────────────────────
Step 45: backend/Dockerfile                    (30 min)
Step 46: gateway/Dockerfile                    (20 min)
Step 47: docker-compose.yml                    (30 min)
Step 48: docker compose up → integration test  (30 min)

TOTAL ESTIMATE: ~18-20 hrs of focused build time
```

---

## Verification Plan

### After Phase 2 (ML Layer)
```python
# Smoke test: load all models and run a single district inference
python -c "
from backend.ml.loader import ModelRegistry
r = ModelRegistry(); r.load_all()
print(r.health_map)
# Expected: {'stgnn': True, 'graphwavenet': True, 'nbeats': True, ...}
"
```

### After Phase 3 (FastAPI)
```bash
uvicorn backend.main:app --reload
curl http://localhost:8000/health
# Expected: {"ok": true, "models": {...}, "redis_ok": true, "db_ok": true}

curl "http://localhost:8000/api/v1/risk/district/27_025?diseases=dengue"
# Expected: RiskResponse JSON with score, risk_level, model_used

curl "http://localhost:8000/api/v1/forecast/hospital/{id}?horizon_weeks=4"
# Expected: ForecastResponse with LP optimizer orders
```

### After Phase 5 (Kafka)
```bash
# Manually publish a test outbreak event
python -c "
from backend.kafka.producer import OutbreakProducer
import asyncio
asyncio.run(OutbreakProducer().publish_test_event('27_025', 'dengue', 0.85))
"
# Wait 5 seconds, then:
# 1. Check Supabase: purchase_orders table should have 1 PENDING row
# 2. Check Twilio test number: should receive WhatsApp message
```

### After Phase 6 (Gateway)
```bash
# Test JWT auth
curl -H "Authorization: Bearer {invalid_token}" http://localhost:8080/api/districts
# Expected: 401

# Test role scoping (pharmacist JWT)
curl -H "Authorization: Bearer {pharmacist_jwt}" http://localhost:8080/api/hospitals
# Expected: Only their hospital, not all hospitals

# Test rate limiting
for i in $(seq 1 210); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -H "Authorization: Bearer {pharmacist_jwt}" \
    http://localhost:8080/api/districts
done | sort | uniq -c
# Expected: 200 occurrences of "200", 10 occurrences of "429"
```

---

## Stack Story for Judges

> This is what you say when they ask "why did you build it this way?"

**"We made a deliberate decision to build Pharmasense with the same infrastructure patterns used by production healthcare and logistics companies — not because a hackathon demands it, but because we're building a product.**

**The Go gateway handles JWT verification and rate limiting at the edge — zero ML code runs until a request is authenticated. The gRPC interface between our gateway and ML service gives us a typed contract; if we change the forecast response schema, the Go compiler will catch it before it ever reaches production.**

**Redis serves four distinct purposes — prediction caching eliminates 640 daily model inference calls, brief caching keeps Gemini quota safe, rate limiting prevents the ML service from being hammered, and JWT revocation gives us stateless logout.**

**Kafka gives us a persistent, replayable event log. If our WhatsApp notifier crashes at 2 AM during a dengue surge, the consumer group simply replays from the last committed offset when it restarts — zero message loss, zero missed pharmacy alerts.**

**And the LP Procurement Optimizer is our real differentiator. Every other team predicts. We prescribe — exact drug quantities, budget constraints, urgency classifications, all solved as a linear program. That's the difference between a dashboard and a decision support system."**

---

*Plan locked: 2026-06-05*
*Stack version: 1.0 — AgTechathon 2.0 2K26*
*Next action: Execute Phase 1 → Foundations*
