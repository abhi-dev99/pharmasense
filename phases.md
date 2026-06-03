# Pharmasense — Phased Build Plan

> **Motto:** By hook or by crook, deliver on everything we say. Nothing left halfway. Think product, not project.
>
> **Priority order:** Technical correctness → Accuracy → Backend solidity → Streamlit demo → Next.js UI (last)

---

## Dataset Reality Check (Before Any Schema Is Finalized)

Before building anything, here's exactly what the raw datasets look like. The schema is derived FROM this reality, not the other way around.

---

### Dataset 1: EpiClim (Zenodo 10.5281/zenodo.14580510)

**What it is:** Weekly district-level epidemic + climate data, India, 2009–2023. Sourced from IDSP (Integrated Disease Surveillance Programme) + ERA5-Land climate reanalysis.

**Raw CSV columns:**

| Column | Type | Notes |
|---|---|---|
| `week_of_outbreak` | string | e.g. "1st week", "2nd week" — needs parsing to ISO week |
| `state_ut` | string | Full state name — needs normalization (e.g. "Jammu & Kashmir" variants) |
| `district` | string | District name — **NO census code here**. Join to GeoJSON by name (fuzzy match needed) |
| `Disease` | string | Values: `Dengue`, `Malaria`, `Cholera`, `Acute Diarrhoeal Disease` |
| `Cases` | int | Number of cases reported that week |
| `Deaths` | int | Deaths reported (nullable — many rows missing) |
| `day` | int | Day of the week record (often 1 = Monday) |
| `mon` | int | Month (1-12) |
| `year` | int | Year (2009-2023) |
| `Latitude` | float | District centroid lat |
| `Longitude` | float | District centroid lon |
| `preci` | float | Daily precipitation in mm (ERA5-Land, district centroid) |
| `LAI` | float | Leaf Area Index — vegetation proxy (use as monsoon intensity signal) |
| `Temp` | float | Temperature in **Kelvin** — must convert to Celsius (subtract 273.15) |

**Total records:** 8,985 rows
**Diseases:** Dengue, Malaria, Cholera, Acute Diarrhoeal Disease (ADD)
**Key preprocessing steps:**
- Parse `week_of_outbreak` + `day`/`mon`/`year` → proper ISO date
- Convert `Temp` Kelvin → Celsius
- Normalize district names (lowercase, strip punctuation) for GeoJSON join
- Compute `cases_per_100k` using district population (external lookup)
- Aggregate to weekly granularity per (district, disease)
- Fill `Deaths` NaN → 0 (assume underreporting, not zero deaths)
- The dataset has lat/lon per record → use these as district centroids for ST-GNN node positions

**What goes into Supabase from this:**
- `epid_weekly` table: (district_id FK, disease, iso_week, cases, deaths, cases_per_100k)
- The preci/LAI/Temp from EpiClim are **historical** climate — they go into training data only, NOT live signals. Live climate comes from OpenWeatherMap.

---

### Dataset 2: India Medicines Kaggle (`apkaayush/india-medicines-and-drug-info-dataset`)

**What it is:** 250k+ drug SKUs scraped from 1mg/Indian pharma catalogues.

**Raw CSV columns (confirmed typical schema):**

| Column | Type | Notes |
|---|---|---|
| `id` | int | 1mg internal ID — use as external_id reference |
| `name` | string | Commercial name e.g. "Paracetamol 500mg Tablet" |
| `price` | float | MRP in INR |
| `is_discontinued` | bool | Whether SKU still in production |
| `manufacturer_name` | string | e.g. "GSK", "Cipla", "Sun Pharma" |
| `type` | string | Tablet/Syrup/Injection/etc. |
| `pack_size_label` | string | e.g. "Strip of 10 tablets", "Vial of 30ml" |
| `short_composition1` | string | Primary active ingredient e.g. "Paracetamol 500mg" |
| `short_composition2` | string | Secondary ingredient (if combination drug) |
| `substitute0`–`substitute4` | string | Alternative drug names |

**Key preprocessing steps:**
- Filter to `is_discontinued = False` only
- Extract `generic_name` from `short_composition1` (regex: strip dosage)
- Extract `dose_mg` from composition string (e.g. `500` from `Paracetamol 500mg`)
- Extract `formulation_type` from `type` (Tablet/Injection/Oral Solution/etc.)
- Extract `pack_size_units` from `pack_size_label` (e.g. 10 from "Strip of 10 tablets")
- Filter to ICMR-relevant drugs (paracetamol, ORS, chloroquine, artemether, lumefantrine, artesunate, primaquine, ringer's lactate, IV NS, metronidazole, doxycycline, azithromycin, cefixime)
- Deduplicate by generic_name + dose_mg + formulation_type → keep cheapest per generic

**What goes into Supabase from this:**
- `drugs` table: (id, name, generic_name, dose_mg, formulation_type, pack_size_units, price_inr, manufacturer_name, icmr_protocol_diseases[])

---

### Dataset 3: India District GeoJSON (DataMeet / datameet.org/maps)

**Format:** GeoJSON FeatureCollection, WGS84 (EPSG:4326)

**Properties per Feature:**

| Property | Type | Notes |
|---|---|---|
| `DISTRICT` | string | District name (uppercase) |
| `ST_NM` | string | State name |
| `ST_CEN_CD` | string | State census code |
| `DT_CEN_CD` | string | District census code — **USE THIS as canonical district ID** |
| `censuscode` | string | Full census code (state + district) |
| `geometry` | Polygon/MultiPolygon | The actual shape |

**Key preprocessing steps:**
- Use `DT_CEN_CD` as canonical ID — map EpiClim district names to this via fuzzy name matching
- Normalize `DISTRICT` name → lowercase for joining
- Compute adjacency matrix: two districts share an edge if their polygons share a border (GeoPandas `.touches()` or `.intersection()` with non-zero length)
- Compute `centroid_lat`/`centroid_lon` from geometry
- Compute `area_km2` from geometry (in projected CRS, convert back)
- Edge weight for ST-GNN = shared border length / sqrt(area_a × area_b)
- Export adjacency as `(district_a_census_code, district_b_census_code, edge_weight)` CSV for training

**What goes into Supabase from this:**
- `districts` table: (id=DT_CEN_CD, name, state, centroid_lat, centroid_lon, area_km2, geojson_polygon)
- PostGIS `GEOGRAPHY(POLYGON)` type for spatial queries
- Adjacency stored as flat array or separate `district_adjacency` table

---

### Dataset 4: OpenWeatherMap API (Live, Current Weather)

**Endpoint:** `api.openweathermap.org/data/2.5/weather?lat={}&lon={}&units=metric&appid={KEY}`

**Key JSON fields we extract:**

| JSON path | Meaning | Our column |
|---|---|---|
| `main.temp` | Current temp °C (units=metric) | `temp_celsius` |
| `main.humidity` | Humidity % | `humidity_pct` |
| `rain.1h` | Rain last 1hr mm (may be absent) | `rain_1h_mm` (default 0) |
| `rain.3h` | Rain last 3hr mm (may be absent) | `rain_3h_mm` (default 0) |
| `weather[0].main` | Condition group ("Rain", "Clear", etc.) | `weather_condition` |
| `dt` | UNIX timestamp | `fetched_at` |
| `coord.lat`, `coord.lon` | Echo of our query coords | (discard) |

**Coverage strategy:** We cannot call OWM for all 640 districts — free tier has rate limits. Strategy:
- Call for ~50 district centroids that are historically high-risk (based on EpiClim data)
- For remaining districts: interpolate from nearest available OWM reading using inverse distance weighting (IDW)
- Or: use OWM's `/forecast` endpoint with 5-day/3-hour data once daily to get projections

**What goes into Supabase from this:**
- `weather_signals` table: (district_id FK, fetched_at TIMESTAMPTZ, temp_celsius, humidity_pct, rain_1h_mm, rain_3h_mm, weather_condition)

---

### Dataset 5: pytrends (Google Symptom Search Signals)

**Library:** `pytrends` (unofficial Google Trends API)

**What we pull:** Search interest for symptom queries by state/region, weekly resolution

**Queries (per disease):**
- Dengue: `["dengue fever", "dengue symptoms", "platelet count"]`
- Malaria: `["malaria fever", "malaria symptoms", "chills fever"]`
- Cholera: `["cholera", "rice water diarrhea", "acute diarrhea ORS"]`
- ADD: `["diarrhea medicine", "ORS sachets", "stomach infection"]`

**pytrends response schema:**
- Returns a DataFrame: `timeframe` (week), `geoName` (state), value (0-100 interest index)
- Resolution is **state-level only** (Google doesn't give district-level)
- Lag: ~72 hours (trends finalized 3 days after the week ends)

**Preprocessing:**
- Map state → all districts in that state (broadcast state signal to district level)
- Normalize to 0-100 scale (already done by Google)
- Compute velocity: `search_score[week] - search_score[week-1]` = acceleration of interest

**What goes into Supabase from this:**
- `search_signals` table: (state, disease_query, iso_week, search_index INT, velocity FLOAT, fetched_at)

---

### Dataset 6: ICMR Translation Rules (Manual JSON, Based on ICMR STGs)

**Not a downloadable dataset — we write this manually as `data/icmr_rules.json`**

Based on ICMR Standard Treatment Workflows (stw.icmr.org.in) + WHO protocols:

```json
{
  "dengue": {
    "dengue_fever_mild": {
      "paracetamol_500mg_tablet": {"dose_per_case": 24, "unit": "tablets", "duration_days": 3},
      "ors_sachet": {"dose_per_case": 6, "unit": "sachets", "duration_days": 3}
    },
    "dengue_severe": {
      "paracetamol_500mg_tablet": {"dose_per_case": 24, "unit": "tablets", "duration_days": 3},
      "ringer_lactate_500ml_iv": {"dose_per_case": 4, "unit": "bags", "duration_days": 1},
      "iv_normal_saline_500ml": {"dose_per_case": 2, "unit": "bags", "duration_days": 1}
    }
  },
  "malaria": {
    "plasmodium_vivax": {
      "chloroquine_250mg_tablet": {"dose_per_case": 10, "unit": "tablets", "duration_days": 3},
      "primaquine_15mg_tablet": {"dose_per_case": 14, "unit": "tablets", "duration_days": 14}
    },
    "plasmodium_falciparum": {
      "artemether_lumefantrine_tablet": {"dose_per_case": 24, "unit": "tablets", "duration_days": 3},
      "artesunate_injection_60mg": {"dose_per_case": 3, "unit": "vials", "duration_days": 1}
    }
  },
  "cholera": {
    "mild_moderate": {
      "ors_sachet": {"dose_per_case": 12, "unit": "sachets", "duration_days": 3},
      "zinc_20mg_tablet": {"dose_per_case": 14, "unit": "tablets", "duration_days": 14}
    },
    "severe": {
      "ringer_lactate_500ml_iv": {"dose_per_case": 6, "unit": "bags", "duration_days": 1},
      "doxycycline_100mg_tablet": {"dose_per_case": 3, "unit": "tablets", "duration_days": 3},
      "azithromycin_500mg_tablet": {"dose_per_case": 3, "unit": "tablets", "duration_days": 3}
    }
  },
  "acute_diarrhoeal_disease": {
    "standard": {
      "ors_sachet": {"dose_per_case": 6, "unit": "sachets", "duration_days": 3},
      "zinc_20mg_tablet": {"dose_per_case": 14, "unit": "tablets", "duration_days": 14},
      "metronidazole_400mg_tablet": {"dose_per_case": 9, "unit": "tablets", "duration_days": 3}
    }
  }
}
```

**How the translation layer works at runtime:**
1. ST-GNN outputs: `{district_id, disease, predicted_cases_next_14_days}`
2. ICMR rules engine: `predicted_cases × dose_per_case` per drug → SKU demand volume
3. Severity split: assume 80% mild, 20% severe (configurable)
4. Output: `{drug_generic_name, units_needed, district_id, date_range}`

---

## The Supabase Schema (Dataset-Informed)

Now that we know what we're working with, here's the actual schema:

```sql
-- Enable extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── REFERENCE TABLES ─────────────────────────────────────────────────────────

CREATE TABLE districts (
    id              TEXT PRIMARY KEY,          -- DT_CEN_CD from GeoJSON (canonical)
    name            TEXT NOT NULL,             -- "Pune", "North Delhi" etc.
    state           TEXT NOT NULL,             -- "Maharashtra", "Delhi"
    centroid_lat    DOUBLE PRECISION NOT NULL,
    centroid_lon    DOUBLE PRECISION NOT NULL,
    area_km2        DOUBLE PRECISION,
    geom            GEOGRAPHY(GEOMETRY, 4326), -- PostGIS polygon
    adjacency_ids   TEXT[] DEFAULT '{}',       -- DT_CEN_CD array of neighbors
    population      BIGINT,                    -- from Census 2011 lookup
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ON districts USING GIST (geom);
CREATE INDEX ON districts (state);

CREATE TABLE drugs (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                TEXT NOT NULL,          -- commercial name from Kaggle
    generic_name        TEXT NOT NULL,          -- e.g. "paracetamol"
    dose_mg             NUMERIC,               -- e.g. 500 (from composition parse)
    formulation_type    TEXT NOT NULL,          -- "tablet","injection","oral_solution","sachet","iv_bag"
    pack_size_units     INT,                   -- units per pack (e.g. 10 for strip of 10)
    price_inr           NUMERIC(10,2),         -- MRP per pack
    manufacturer_name   TEXT,
    icmr_diseases       TEXT[] DEFAULT '{}',   -- ["dengue","malaria"] - which diseases use this
    is_active           BOOLEAN DEFAULT TRUE,
    external_1mg_id     INT,                   -- original Kaggle id for traceability
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ON drugs (generic_name);
CREATE INDEX ON drugs USING GIN (icmr_diseases);

CREATE TABLE hospitals (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT NOT NULL,
    district_id     TEXT REFERENCES districts(id),
    lat             DOUBLE PRECISION NOT NULL,
    lon             DOUBLE PRECISION NOT NULL,
    tier            TEXT NOT NULL CHECK (tier IN ('PHC','CHC','District','State')),
    bed_count       INT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ON hospitals (district_id);

-- ─── EPIDEMIOLOGICAL DATA ──────────────────────────────────────────────────────

CREATE TABLE epid_weekly (
    id              BIGSERIAL PRIMARY KEY,
    district_id     TEXT REFERENCES districts(id),
    disease         TEXT NOT NULL CHECK (disease IN ('dengue','malaria','cholera','acute_diarrhoeal_disease')),
    iso_week        TEXT NOT NULL,             -- "2023-W24" format
    week_start_date DATE NOT NULL,
    cases           INT NOT NULL DEFAULT 0,
    deaths          INT NOT NULL DEFAULT 0,
    cases_per_100k  NUMERIC(10,4),             -- computed during import
    data_source     TEXT DEFAULT 'epiclim',
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (district_id, disease, iso_week)
);

CREATE INDEX ON epid_weekly (district_id);
CREATE INDEX ON epid_weekly (disease, iso_week);
CREATE INDEX ON epid_weekly (week_start_date);

-- ─── LIVE SIGNALS ──────────────────────────────────────────────────────────────

CREATE TABLE weather_signals (
    id              BIGSERIAL PRIMARY KEY,
    district_id     TEXT REFERENCES districts(id),
    fetched_at      TIMESTAMPTZ NOT NULL,
    temp_celsius    NUMERIC(5,2),
    humidity_pct    NUMERIC(5,2),
    rain_1h_mm      NUMERIC(8,3) DEFAULT 0,
    rain_3h_mm      NUMERIC(8,3) DEFAULT 0,
    weather_cond    TEXT,                      -- "Rain","Clear","Clouds" from OWM
    is_interpolated BOOLEAN DEFAULT FALSE,     -- TRUE if estimated from nearby districts
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ON weather_signals (district_id, fetched_at DESC);

CREATE TABLE search_signals (
    id              BIGSERIAL PRIMARY KEY,
    state           TEXT NOT NULL,
    disease         TEXT NOT NULL,
    iso_week        TEXT NOT NULL,
    search_index    INT NOT NULL,              -- 0-100 from Google Trends
    search_velocity NUMERIC(6,2),             -- week-over-week delta
    fetched_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (state, disease, iso_week)
);

CREATE INDEX ON search_signals (state, disease, iso_week);

-- ─── ML OUTPUTS ────────────────────────────────────────────────────────────────

CREATE TABLE risk_scores (
    id              BIGSERIAL PRIMARY KEY,
    district_id     TEXT REFERENCES districts(id),
    disease         TEXT NOT NULL,
    score           NUMERIC(5,4) NOT NULL,     -- 0.0000 to 1.0000 (probability)
    risk_level      TEXT GENERATED ALWAYS AS (
                        CASE
                            WHEN score >= 0.7 THEN 'HIGH'
                            WHEN score >= 0.4 THEN 'MEDIUM'
                            ELSE 'LOW'
                        END
                    ) STORED,
    model_used      TEXT NOT NULL,             -- 'stgnn' or 'tft'
    predicted_cases INT,                       -- estimated cases for the 14-day window
    prediction_date DATE NOT NULL,
    horizon_days    INT NOT NULL DEFAULT 14,
    weather_score   NUMERIC(5,4),             -- input feature snapshot
    search_score    NUMERIC(5,4),             -- input feature snapshot
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (district_id, disease, prediction_date)
);

CREATE INDEX ON risk_scores (district_id, prediction_date DESC);
CREATE INDEX ON risk_scores (risk_level, prediction_date DESC);

CREATE TABLE demand_forecasts (
    id              BIGSERIAL PRIMARY KEY,
    district_id     TEXT REFERENCES districts(id),
    drug_id         UUID REFERENCES drugs(id),
    risk_score_id   BIGINT REFERENCES risk_scores(id),
    forecast_units  INT NOT NULL,              -- units needed per pack_size
    forecast_date   DATE NOT NULL,
    horizon_days    INT NOT NULL DEFAULT 14,
    severity_mix    JSONB,                     -- {"mild_pct": 0.8, "severe_pct": 0.2}
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (district_id, drug_id, forecast_date)
);

-- ─── INVENTORY & OPERATIONS ─────────────────────────────────────────────────────

CREATE TABLE inventory (
    id              BIGSERIAL PRIMARY KEY,
    hospital_id     UUID REFERENCES hospitals(id),
    drug_id         UUID REFERENCES drugs(id),
    stock_units     INT NOT NULL DEFAULT 0,    -- current units on hand (per pack)
    reorder_point   INT DEFAULT 50,            -- trigger PO below this
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (hospital_id, drug_id)
);

CREATE TABLE inventory_transactions (
    id              BIGSERIAL PRIMARY KEY,
    hospital_id     UUID REFERENCES hospitals(id),
    drug_id         UUID REFERENCES drugs(id),
    delta_units     INT NOT NULL,              -- positive=restock, negative=dispensed
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('dispensed','received','adjustment','opening_stock')),
    user_id         UUID,                      -- Supabase auth user
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE purchase_orders (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    hospital_id     UUID REFERENCES hospitals(id),
    drug_id         UUID REFERENCES drugs(id),
    qty_units       INT NOT NULL,
    unit_price_inr  NUMERIC(10,2),
    total_inr       NUMERIC(12,2) GENERATED ALWAYS AS (qty_units * unit_price_inr) STORED,
    status          TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','APPROVED','REJECTED','DISPATCHED','RECEIVED')),
    trigger_source  TEXT NOT NULL,             -- 'ml_alert','manual','whatsapp_approval'
    risk_score_id   BIGINT REFERENCES risk_scores(id),
    approved_by     UUID,                      -- user_id
    approved_at     TIMESTAMPTZ,
    whatsapp_sent   BOOLEAN DEFAULT FALSE,
    whatsapp_msg_id TEXT,                      -- Twilio message SID
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ON purchase_orders (hospital_id, status);
CREATE INDEX ON purchase_orders (status, created_at DESC);

-- ─── AUDIT ─────────────────────────────────────────────────────────────────────

CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    table_name      TEXT NOT NULL,
    action          TEXT NOT NULL CHECK (action IN ('INSERT','UPDATE','DELETE')),
    row_id          TEXT NOT NULL,
    user_id         UUID,
    old_values      JSONB,
    new_values      JSONB,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- ─── SUPABASE AUTH ROLES ────────────────────────────────────────────────────────
-- RLS policies — added after table creation
-- Role values (stored in JWT custom claim 'app_role'):
--   'state_minister'   → sees all districts in their state
--   'district_officer' → sees all hospitals in their district
--   'pharmacist'       → sees only their hospital_id
```

---

# Phase 0 — Data Foundation

**Goal:** Get all real data into Supabase. No ML, no API. Just raw data pipelines and schema.

**Timeline estimate:** 1 day

**Why this first:** Everything downstream — ML training, inference, API responses — depends on this being right. Wrong joins here cascade into wrong predictions.

## Step 0.1 — Download EpiClim Dataset

```
Source: https://zenodo.org/records/14580510
File:   EpiClim.csv (or equivalent filename in the ZIP)
Dest:   data/raw/epiclim/epiclim.csv
Size:   ~8,985 rows, ~1.2MB
```

Download manually or:
```bash
curl -L "https://zenodo.org/records/14580510/files/EpiClim.csv?download=1" \
     -o data/raw/epiclim/epiclim.csv
```

## Step 0.2 — Download India District GeoJSON

```
Source: https://github.com/datameet/maps/tree/master/Districts
File:   Districts.geojson
Dest:   data/raw/india_geojson/Districts.geojson
```

## Step 0.3 — Download India Medicines Kaggle Dataset

```
Source: kaggle.com/datasets/apkaayush/india-medicines-and-drug-info-dataset
Auth:   kaggle API key in ~/.kaggle/kaggle.json
Dest:   data/raw/india_medicines/
```

```bash
kaggle datasets download apkaayush/india-medicines-and-drug-info-dataset \
       -p data/raw/india_medicines/ --unzip
```

## Step 0.4 — Write ICMR Rules JSON

File: `data/icmr_rules.json`
Content: The JSON structure from the Dataset section above (dengue/malaria/cholera/ADD, mild/severe splits).

This is written by us — grounded in ICMR STWs. Not downloaded. Committed to git.

## Step 0.5 — Create Supabase Project + Get Credentials

1. Create project at supabase.com
2. Get:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
   - `SUPABASE_SERVICE_ROLE_KEY`
3. Add to `.env`
4. Run the schema SQL from above in Supabase SQL editor

## Step 0.6 — Write & Run Data Pipeline Scripts

### `data/scripts/01_load_geojson.py`
```
Input:  data/raw/india_geojson/Districts.geojson
Output: Supabase.districts table populated
Steps:
  1. Load GeoJSON with geopandas
  2. For each feature:
     - id = properties.DT_CEN_CD
     - name = properties.DISTRICT (lowercase strip)
     - state = properties.ST_NM
     - centroid = geometry.centroid
     - area_km2 = geometry.to_crs(epsg=3857).area / 1e6
     - geojson_polygon = geometry.__geo_interface__
  3. Compute adjacency: for each pair, check if geometries share border
     - Use .touches() or .exterior.intersects() — O(n²) but 640 districts → ~200k pairs, manageable
     - Store adjacency_ids[] on each district row
  4. Upsert to Supabase districts table
```

### `data/scripts/02_load_epiclim.py`
```
Input:  data/raw/epiclim/epiclim.csv
Output: Supabase.epid_weekly table populated
Steps:
  1. Load CSV with pandas
  2. Normalize disease names: map "Acute Diarrhoeal Disease" → "acute_diarrhoeal_disease" etc.
  3. Build date from day/mon/year → compute ISO week ("YYYY-WWW")
  4. Fuzzy join district name to districts.id (via rapidfuzz or jellyfish, threshold=85)
     - Log all unmatched rows — expect ~5-10% due to name variants
  5. Temp K → C, but this is historical climate for reference only (NOT stored in epid_weekly)
  6. cases_per_100k: requires population. Use Census 2011 district population CSV (public domain).
     - Add data/raw/district_population.csv to data pipeline
  7. Deduplicate: UNIQUE (district_id, disease, iso_week) — take SUM if multiple rows same week
  8. Upsert to epid_weekly
```

### `data/scripts/03_load_medicines.py`
```
Input:  data/raw/india_medicines/*.csv
Output: Supabase.drugs table populated (ICMR-relevant subset)
Steps:
  1. Load CSV, filter is_discontinued = False
  2. Extract generic_name from short_composition1 (regex strip dosage numbers)
  3. Extract dose_mg from composition
  4. Map generic_name → icmr_diseases[] (lookup dict: paracetamol→[dengue], chloroquine→[malaria] etc.)
  5. Filter: only keep rows where icmr_diseases is non-empty
  6. Deduplicate: per (generic_name, dose_mg, formulation_type) → keep cheapest pack
  7. Upsert to drugs table
```

### `data/scripts/04_seed_hospitals.py`
```
Input:  data/seed/hospitals_seed.csv (hand-curated, ~50-100 hospitals for demo)
Output: Supabase.hospitals table + inventory (opening_stock all zeros)
Steps:
  1. For the hackathon: seed 3-5 real hospitals per district for ~10 districts
     Source: National Health Facility Registry (NHFR) — public data
  2. Each hospital gets opening inventory = 0 for each ICMR drug
  3. Create Supabase Auth users for each role (state_minister × 1, district_officer × 2, pharmacist × 5)
  4. Add user_metadata: {app_role: "pharmacist", hospital_id: "..."}
```

## Step 0.7 — Validate Data Integrity

Run validation queries:
```sql
-- Check district coverage
SELECT COUNT(DISTINCT district_id) FROM epid_weekly; -- expect 300-500

-- Check disease distribution
SELECT disease, COUNT(*), SUM(cases) FROM epid_weekly GROUP BY disease;

-- Check GeoJSON adjacency sanity
SELECT id, name, array_length(adjacency_ids, 1) AS neighbor_count
FROM districts ORDER BY neighbor_count DESC LIMIT 10;
-- Uttar Pradesh border districts should have 5-8 neighbors

-- Check drug seeding
SELECT formulation_type, COUNT(*) FROM drugs GROUP BY formulation_type;
SELECT unnest(icmr_diseases), COUNT(*) FROM drugs GROUP BY 1;
```

**Phase 0 deliverable:** All raw data in Supabase, validated. No models, no API.

---

# Phase 1 — ML Training (Offline, on Google Colab)

**Goal:** Train ST-GNN and TFT. Produce `.pt` artifact files. These run ONCE — not on any server.

**Timeline estimate:** 2-3 days (data prep ~1 day, training ~1 day, debugging ~1 day)

**The artifacts from this phase get loaded into the FastAPI service in Phase 2.**

## Step 1.1 — Build District Adjacency Matrix

File: `ml/build_adjacency.py`

```python
# Input: data/raw/india_geojson/Districts.geojson
# Output: data/processed/adjacency_matrix.npz (scipy sparse)
#         data/processed/district_index.json  {DT_CEN_CD: node_index}

import geopandas as gpd
import scipy.sparse as sp
import numpy as np

gdf = gpd.read_file("data/raw/india_geojson/Districts.geojson")
gdf = gdf.set_index("DT_CEN_CD")
n = len(gdf)

# Build adjacency (touching polygons)
rows, cols, weights = [], [], []
for i, (id_a, row_a) in enumerate(gdf.iterrows()):
    for j, (id_b, row_b) in enumerate(gdf.iterrows()):
        if i >= j: continue
        if row_a.geometry.touches(row_b.geometry):
            shared = row_a.geometry.intersection(row_b.geometry)
            w = shared.length  # shared border length in degrees
            rows += [i, j]; cols += [j, i]; weights += [w, w]

adj = sp.coo_matrix((weights, (rows, cols)), shape=(n, n))
sp.save_npz("data/processed/adjacency_matrix.npz", adj)
```

## Step 1.2 — Build ST-GNN Training Dataset

File: `ml/build_stgnn_dataset.py`

```
Input:  Supabase.epid_weekly (2009-2021 for train, 2022 val, 2023 test)
        Supabase.weather_signals (historical — we seed these from EpiClim preci/Temp columns)
        data/processed/adjacency_matrix.npz

Output: data/processed/stgnn_train.pt (PyTorch Geometric Data objects)

Node features per timestep (8 weeks lookback window):
  x[node, timestep] = [
    cases_per_100k,       # from epid_weekly
    rain_mm,              # from weather_signals (historical ERA5 = EpiClim.preci)
    humidity_pct,         # NOT in EpiClim — use ERA5 monthly avg by district (static)
    temp_celsius,         # EpiClim.Temp - 273.15
    lai,                  # EpiClim.LAI (vegetation, monsoon proxy)
    search_idx,           # from search_signals (pytrends historical pull)
    sin_week,             # sin(2π × week_of_year / 52)
    cos_week,             # cos(2π × week_of_year / 52)
    monsoon_flag,         # 1 if month in [6,7,8,9,10]
  ]

Target:
  y[node] = 1 if cases_per_100k in next 2 weeks > threshold, else 0
  threshold = 99th percentile of historical baseline (computed per disease)
```

**Humidity note:** EpiClim doesn't have humidity. Options:
1. Use ERA5-Land monthly humidity by district (downloadable from Copernicus CDS)
2. Estimate: use `Temp` + `preci` as proxy features instead (still valid for monsoon modeling)
3. For v1: omit humidity from training features, add it from OWM at inference time with a feature dropout mask

**Decision: use option 3 for v1.** Train without humidity, add it as a bonus feature at inference. This is honest and won't break the model.

## Step 1.3 — Train ST-GNN

File: `ml/notebooks/stgnn_training.ipynb` (run on Colab T4)

```python
# Architecture: GraphSAGE + GRU temporal wrapper
import torch
import torch.nn.functional as F
from torch_geometric.nn import SAGEConv
from torch_geometric.data import DataLoader

class STGNN(torch.nn.Module):
    def __init__(self, in_channels, hidden, out_channels, num_layers=2):
        super().__init__()
        self.gru = torch.nn.GRU(in_channels, hidden, batch_first=True)
        self.convs = torch.nn.ModuleList([
            SAGEConv(hidden, hidden) for _ in range(num_layers)
        ])
        self.classifier = torch.nn.Linear(hidden, out_channels)

    def forward(self, x, edge_index, edge_weight):
        # x: [num_nodes, seq_len, features]
        _, h = self.gru(x)           # h: [1, num_nodes, hidden]
        h = h.squeeze(0)             # [num_nodes, hidden]
        for conv in self.convs:
            h = F.relu(conv(h, edge_index))
        return torch.sigmoid(self.classifier(h))  # [num_nodes, 1]

# Training config
# epochs: 100, lr: 1e-3, weight decay: 1e-4
# BCELoss with pos_weight for class imbalance (outbreaks are rare events)
# Early stopping on val AUC-ROC
# Save best model: torch.save(model.state_dict(), "stgnn_best.pt")
```

**Expected metrics (target):** AUC-ROC > 0.80 on held-out 2023 data

## Step 1.4 — Build TFT Training Dataset (Synthetic)

File: `ml/generate_synthetic.py`

```
We don't have real drug sales history. So we synthesize it from first principles.

Algorithm:
1. For each (district, week) in epid_weekly:
   - Get cases by disease
   - Apply ICMR rules: cases × dose_per_case = drug_units_used
   - Add baseline noise: ±15% from Gaussian noise (simulates non-outbreak demand)
   - Add seasonal multiplier: 1.2× in monsoon months for ORS, paracetamol
   - Store as (hospital_id, drug_id, week, units_dispensed)

2. Distribute across hospitals in district: weighted by bed_count
3. Add hospital-specific noise for realism

Output: data/processed/tft_train.csv
Schema: hospital_id, drug_id, week_start, units_dispensed, district_id, disease_context
```

## Step 1.5 — Train TFT

File: `ml/notebooks/tft_training.ipynb` (run on Colab T4)

```python
from pytorch_forecasting import TemporalFusionTransformer, TimeSeriesDataSet

# Dataset config
dataset = TimeSeriesDataSet(
    df,
    time_idx="week_idx",           # int index of week
    target="units_dispensed",
    group_ids=["hospital_id", "drug_id"],
    max_encoder_length=12,         # 12 weeks lookback
    max_prediction_length=4,       # 4 weeks forecast (30 days)
    time_varying_known_reals=["week_idx", "monsoon_flag", "sin_week", "cos_week"],
    time_varying_unknown_reals=["units_dispensed", "search_idx", "rain_mm"],
    static_categoricals=["hospital_id", "drug_id"],
    target_normalizer=GroupNormalizer(groups=["hospital_id", "drug_id"])
)

# Model config
tft = TemporalFusionTransformer.from_dataset(
    dataset,
    learning_rate=3e-3,
    hidden_size=32,
    attention_head_size=2,
    dropout=0.1,
    hidden_continuous_size=16,
    loss=QuantileLoss(quantiles=[0.1, 0.5, 0.9])  # prediction intervals
)
# Save: tft_best.pt
```

## Step 1.6 — Validate + Serialize Models

```
Post-training checks:
  ST-GNN: AUC-ROC per disease on 2023 holdout
  TFT:    MAPE on held-out hospitals

Serialize:
  torch.save(stgnn.state_dict(), "ml/artifacts/stgnn_v1.pt")
  tft.save("ml/artifacts/tft_v1.pt")
  Save district_index.json alongside for node ID mapping
  Save drug_scaler.pkl (StandardScaler for TFT inputs)

These .pt files are gitignored. They get:
  - Loaded manually into local dev environment
  - In production: uploaded to cloud storage, pulled at service startup
```

**Phase 1 deliverable:** Two trained `.pt` files + district_index.json + drug_scaler.pkl. 

---

# Phase 2 — FastAPI ML Service

**Goal:** A running Python service that loads the models and serves predictions via both REST and gRPC.

**Timeline estimate:** 2 days

**Architecture note:** This service is the brain. The Go gateway (Phase 4) calls it via gRPC. The Streamlit UI (Phase 5) can call it directly via HTTP during development — bypass the Go gateway for speed.

## Step 2.1 — Project Structure

```
backend/
├── main.py                   ← FastAPI app + lifespan startup
├── config.py                 ← pydantic-settings, loads .env
├── schemas.py                ← Pydantic request/response models
├── api/
│   ├── routes_risk.py        ← GET /risk/{district_id}
│   ├── routes_forecast.py    ← GET /forecast/{hospital_id}/{drug_id}
│   ├── routes_brief.py       ← GET /brief/{hospital_id}
│   ├── routes_simulate.py    ← POST /simulate/monsoon
│   └── routes_webhook.py     ← POST /hooks/whatsapp
├── ml/
│   ├── loader.py             ← load .pt files at startup, singleton
│   ├── router.py             ← etiology router (disease → model selection)
│   ├── stgnn_inference.py    ← ST-GNN forward pass
│   ├── tft_inference.py      ← TFT forward pass
│   ├── icmr.py               ← rules engine
│   └── prophet_fallback.py   ← if .pt artifacts missing
├── data/
│   ├── signals.py            ← OWM fetch + pytrends fetch
│   └── scheduler.py          ← APScheduler daily batch + hourly weather
├── kafka/
│   ├── producer.py
│   └── consumers/
│       ├── po_generator.py
│       └── whatsapp_notifier.py
├── cache/
│   └── redis_client.py       ← redis-py async client
├── db/
│   ├── supabase_client.py    ← supabase-py client singleton
│   ├── queries_risk.py
│   ├── queries_inventory.py
│   └── queries_po.py
├── requirements.txt
└── Dockerfile
```

## Step 2.2 — Startup & Model Loading

```python
# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from ml.loader import ModelStore
from db.supabase_client import init_supabase
from cache.redis_client import init_redis
from data.scheduler import start_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load models into memory at startup
    ModelStore.load_stgnn("ml/artifacts/stgnn_v1.pt", "data/processed/district_index.json")
    ModelStore.load_tft("ml/artifacts/tft_v1.pt", "data/processed/drug_scaler.pkl")
    ModelStore.load_icmr_rules("data/icmr_rules.json")
    # Init DB + cache connections
    init_supabase()
    init_redis()
    # Start APScheduler
    start_scheduler()
    yield
    # Cleanup on shutdown

app = FastAPI(lifespan=lifespan)
```

## Step 2.3 — Etiology Router

```python
# ml/router.py
COMMUNICABLE = {"dengue", "malaria", "cholera", "acute_diarrhoeal_disease"}
BASELINE_NCD  = {"hypertension", "diabetes", "antibiotics_routine"}

def route_prediction(disease: str, district_id: str, context: dict) -> dict:
    if disease in COMMUNICABLE:
        return stgnn_inference(district_id, disease, context)
    else:
        return tft_inference(district_id, disease, context)
```

## Step 2.4 — ST-GNN Inference

```python
# ml/stgnn_inference.py
# Key challenge: ST-GNN needs 8-week sequence for ALL nodes (not just the queried district)
# We run inference for the whole graph, then return the requested node's output

def run_stgnn(disease: str) -> dict[str, float]:
    """Returns risk_probability for all districts for given disease"""
    # 1. Fetch last 8 weeks of features for all districts from Supabase
    # 2. Assemble node feature tensor [640, 8, 9]
    # 3. Load adjacency matrix
    # 4. Run model.forward(x, edge_index, edge_weight)
    # 5. Return {district_id: risk_probability}
    # Cache result in Redis for 24h
```

**Caching strategy:**
- Key: `stgnn:{disease}:{date}` → entire dict of district risks
- On cache hit: return from Redis (sub-millisecond)
- On cache miss OR weather anomaly: run full inference

## Step 2.5 — ICMR Translation Layer

```python
# ml/icmr.py
import json

class ICMRRulesEngine:
    def __init__(self, rules_path: str):
        with open(rules_path) as f:
            self.rules = json.load(f)

    def translate(self, disease: str, predicted_cases: int,
                  severity_mix: dict = {"mild_pct": 0.8, "severe_pct": 0.2}) -> list[dict]:
        """
        Returns list of:
        {"drug_generic_name": str, "units_needed": int, "notes": str}
        """
        results = []
        mild_cases   = int(predicted_cases * severity_mix["mild_pct"])
        severe_cases = int(predicted_cases * severity_mix["severe_pct"])

        for severity, cases in [("mild_moderate" or "dengue_fever_mild", mild_cases),
                                 ("severe" or "dengue_severe", severe_cases)]:
            disease_rules = self.rules.get(disease, {})
            severity_rules = disease_rules.get(severity, {})
            for drug, dosing in severity_rules.items():
                units = cases * dosing["dose_per_case"]
                results.append({
                    "drug_generic_name": drug,
                    "units_needed": units,
                    "unit_type": dosing["unit"],
                    "severity": severity,
                    "duration_days": dosing["duration_days"]
                })
        return results
```

## Step 2.6 — Signal Fetchers (Weather + Trends)

```python
# data/signals.py
import httpx
import asyncio
from pytrends.request import TrendReq

DISEASE_QUERIES = {
    "dengue": ["dengue fever", "dengue symptoms", "platelet count"],
    "malaria": ["malaria fever", "malaria symptoms"],
    "cholera": ["cholera", "rice water diarrhea"],
    "acute_diarrhoeal_disease": ["diarrhea medicine", "ORS sachets"]
}

HIGH_RISK_DISTRICTS = [...]  # list of ~50 district IDs with their centroids

async def fetch_weather_for_districts(api_key: str) -> list[dict]:
    """Fetch OWM for HIGH_RISK_DISTRICTS, interpolate for rest"""
    async with httpx.AsyncClient() as client:
        tasks = [
            client.get(f"https://api.openweathermap.org/data/2.5/weather",
                       params={"lat": d["lat"], "lon": d["lon"],
                               "units": "metric", "appid": api_key})
            for d in HIGH_RISK_DISTRICTS
        ]
        responses = await asyncio.gather(*tasks)
    # Parse responses → upsert to weather_signals table

def fetch_pytrends() -> list[dict]:
    """Pull Google Trends for each disease, by state"""
    pytrends = TrendReq(hl='en-US', tz=330)  # IST timezone
    results = []
    for disease, queries in DISEASE_QUERIES.items():
        pytrends.build_payload(queries, timeframe='now 3-m', geo='IN')
        df = pytrends.interest_by_region(resolution='REGION')
        # df index = state name, columns = query terms
        for state, row in df.iterrows():
            results.append({
                "state": state, "disease": disease,
                "search_index": int(row.mean()),
                "iso_week": current_iso_week()
            })
    return results
```

## Step 2.7 — Daily Batch Scheduler

```python
# data/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

def start_scheduler():
    scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")

    # Daily at 06:00 IST — full prediction batch
    scheduler.add_job(run_daily_batch, "cron", hour=6, minute=0)

    # Hourly — weather refresh
    scheduler.add_job(run_hourly_weather, "cron", minute=0)

    scheduler.start()

async def run_daily_batch():
    """
    1. Fetch pytrends
    2. Fetch weather
    3. For each disease: run etiology router → risk scores
    4. Apply ICMR translation → demand forecasts
    5. Compute shortfalls (forecast - inventory)
    6. If shortfall > threshold: publish to Kafka
    7. Write risk_scores + demand_forecasts to Supabase
    8. Invalidate Redis cache for affected districts
    """

async def run_hourly_weather():
    """
    1. Fetch OWM for HIGH_RISK_DISTRICTS
    2. Write to weather_signals
    3. Check: rain > 40mm AND humidity > 80% for 3 consecutive hours?
       → Yes: set anomaly flag, invalidate Redis, trigger immediate re-inference
    """
```

## Step 2.8 — Kafka Producer

```python
# kafka/producer.py
from confluent_kafka import Producer

class OutbreakEventProducer:
    def __init__(self, bootstrap_servers: str):
        self.producer = Producer({"bootstrap.servers": bootstrap_servers})

    def publish_outbreak_event(self, event: dict):
        """
        event = {
          "district_id": str,
          "disease": str,
          "risk_score": float,
          "predicted_cases": int,
          "drug_shortfalls": [{"drug_id": str, "units_needed": int, "stock": int}],
          "hospitals_affected": [{"hospital_id": str, "pharmacist_whatsapp": str}],
          "event_ts": str (ISO8601)
        }
        """
        self.producer.produce(
            topic="outbreak_events",
            key=event["district_id"],
            value=json.dumps(event).encode()
        )
        self.producer.flush()
```

## Step 2.9 — Kafka Consumers

### PO Generator (`kafka/consumers/po_generator.py`)

```python
# Reads outbreak_events → creates purchase_orders in Supabase
# Logic:
#   1. For each drug_shortfall in event:
#   2. Find cheapest supplier for that drug (from drugs table → price_inr)
#   3. Create purchase_order: qty = shortfall + safety_buffer (20%)
#   4. Status: PENDING
#   5. Upsert to Supabase (don't duplicate if PO already exists for same district+drug+week)
```

### WhatsApp Notifier (`kafka/consumers/whatsapp_notifier.py`)

```python
# Reads outbreak_events → sends WhatsApp via Twilio
from twilio.rest import Client

def send_whatsapp_alert(pharmacist_number: str, event: dict, po_id: str):
    client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)

    body = (
        f"🚨 PHARMASENSE ALERT\n"
        f"Disease: {event['disease'].upper()} surge predicted in {district_name}\n"
        f"Risk Score: {event['risk_score']:.0%}\n"
        f"Predicted cases (14 days): {event['predicted_cases']}\n\n"
        f"📦 Auto-generated PO #{po_id[:8]} ready for approval.\n"
        f"Drugs: {drug_summary}\n\n"
        f"Reply YES to approve | NO to reject"
    )

    client.messages.create(
        from_=f"whatsapp:{TWILIO_FROM}",
        to=f"whatsapp:{pharmacist_number}",
        body=body
    )
```

### Twilio Webhook (`api/routes_webhook.py`)

```python
@router.post("/hooks/whatsapp")
async def twilio_webhook(request: Request):
    form = await request.form()
    body = form.get("Body", "").strip().upper()
    from_number = form.get("From", "").replace("whatsapp:", "")

    # Find pending PO for this pharmacist
    po = await db.get_pending_po_for_pharmacist(from_number)

    if body == "YES" and po:
        await db.update_po_status(po["id"], "APPROVED")
        await db.update_inventory(po["hospital_id"], po["drug_id"], po["qty_units"])
        return TwiML response: "✅ PO #{po_id[:8]} approved. Stock update logged."
    elif body == "NO" and po:
        await db.update_po_status(po["id"], "REJECTED")
        return TwiML response: "❌ PO rejected. Manual review required."
```

## Step 2.10 — Gemini LLM Brief

```python
# api/routes_brief.py
import google.generativeai as genai

async def generate_hospital_brief(hospital_id: str) -> str:
    # Check Redis cache first
    cached = await redis.get(f"brief:{hospital_id}")
    if cached: return cached

    # Fetch context
    hospital   = await db.get_hospital(hospital_id)
    inventory  = await db.get_inventory(hospital_id)
    risk_scores = await db.get_district_risks(hospital["district_id"])
    forecasts  = await db.get_demand_forecasts(hospital_id)
    weather    = await db.get_latest_weather(hospital["district_id"])

    prompt = f"""
    You are a public health supply chain AI assistant.
    
    Hospital: {hospital["name"]}, {district_name}, {state_name}
    
    Current risk scores:
    {format_risk_scores(risk_scores)}
    
    Current inventory vs. predicted demand (14 days):
    {format_inventory_vs_forecast(inventory, forecasts)}
    
    Recent weather signals:
    Rainfall: {weather["rain_3h_mm"]}mm, Humidity: {weather["humidity_pct"]}%
    
    Write a concise 3-paragraph hospital risk brief:
    1. Current outbreak risk assessment for this district
    2. Specific drug stock concerns with urgency level
    3. Recommended immediate actions for the pharmacist
    
    Be specific, use numbers, avoid jargon.
    """

    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    brief = response.text

    # Cache for 24h
    await redis.setex(f"brief:{hospital_id}", 86400, brief)
    return brief
```

## Step 2.11 — Monsoon Simulation Endpoint

```python
@router.post("/simulate/monsoon")
async def simulate_monsoon(districts: list[str], intensity: float = 1.5):
    """
    For demo purposes: artificially spike weather signals and rerun inference.
    intensity: multiplier on rain_mm (1.5 = 50% above threshold)
    Returns: before/after risk scores per district
    """
    # 1. Store original risk scores
    # 2. Inject synthetic weather: rain = ANOMALY_THRESHOLD * intensity
    # 3. Invalidate Redis for these districts
    # 4. Re-run ST-GNN inference
    # 5. Return comparison dict: {district_id: {before: score, after: score}}
    # 6. Do NOT write these simulated scores to Supabase (ephemeral)
```

**Phase 2 deliverable:** FastAPI service running locally, serving real predictions from trained models, writing to Supabase, publishing to Kafka, sending WhatsApp alerts.

---

# Phase 3 — Streamlit Dashboard (Phase 1 Frontend)

**Goal:** A working UI that connects to the FastAPI service directly. Proves the backend works. No Go gateway yet.

**Timeline estimate:** 1-1.5 days

**Philosophy:** This is NOT the final product UI. It's a proof-of-concept that validates every backend piece. It should be functional, not beautiful. The judges who see this demo may be looking at the Streamlit UI — that's fine, as long as it demonstrates real data flowing.

## Step 3.1 — Structure

```
frontend/
├── app.py                    ← main Streamlit app, routing
├── auth.py                   ← Supabase Auth login
├── views/
│   ├── map_view.py           ← pydeck 3D district heatmap
│   ├── inventory_table.py    ← drug stock vs. demand table
│   ├── signal_timeline.py    ← weather + search + epid charts
│   ├── hospital_brief.py     ← Gemini LLM brief panel
│   └── simulate.py           ← monsoon surge simulation UI
└── requirements.txt
```

## Step 3.2 — Login + Role Routing

```python
# auth.py
import streamlit as st
from supabase import create_client

def login():
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if response.user:
            st.session_state.user = response.user
            st.session_state.role = response.user.user_metadata.get("app_role")
            st.session_state.token = response.session.access_token
            st.rerun()

def route_by_role(role):
    if role == "state_minister":
        show_state_view()       # all districts
    elif role == "district_officer":
        show_district_view()    # hospitals in their district
    elif role == "pharmacist":
        show_hospital_view()    # their hospital only
```

## Step 3.3 — Map View (pydeck 3D Heatmap)

```python
# views/map_view.py
import pydeck as pdk

def render_map(risk_scores: list[dict]):
    """
    3D column layer: each district is an extruded column.
    Height = risk_score. Color = risk_level (green→yellow→red).
    Click a district column → fly to district, show hospitals as scatter points.
    """
    layer = pdk.Layer(
        "ColumnLayer",
        data=risk_scores,
        get_position=["centroid_lon", "centroid_lat"],
        get_elevation="risk_score * 50000",     # scale for visibility
        elevation_scale=1,
        radius=8000,
        get_fill_color=[
            "risk_level == 'HIGH' ? 220 : risk_level == 'MEDIUM' ? 255 : 50",
            "risk_level == 'HIGH' ? 50 : risk_level == 'MEDIUM' ? 200 : 180",
            50, 200
        ],
        pickable=True,
        auto_highlight=True
    )
    view = pdk.ViewState(latitude=20.5, longitude=78.9, zoom=4.5, pitch=45)
    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view,
                              tooltip={"text": "{name}\nRisk: {risk_score:.0%}"}))
```

## Step 3.4 — Signal Timeline

```python
# views/signal_timeline.py
import plotly.graph_objects as go

def render_signal_timeline(district_id: str):
    """
    Dual-axis chart:
    Left Y:  Cases per 100k (bar chart, blue)
    Right Y: Rainfall mm (line, gray) + Search index (line, orange)
    X axis:  Last 52 weeks
    """
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Cases/100k", x=weeks, y=cases_per_100k, yaxis="y1"))
    fig.add_trace(go.Scatter(name="Rainfall (mm)", x=weeks, y=rain_mm, yaxis="y2"))
    fig.add_trace(go.Scatter(name="Search Index", x=weeks, y=search_idx, yaxis="y2"))
    fig.update_layout(yaxis2=dict(overlaying="y", side="right"))
    st.plotly_chart(fig, use_container_width=True)
```

## Step 3.5 — Inventory Table

```python
# views/inventory_table.py
import pandas as pd

def render_inventory_table(hospital_id: str):
    """
    Table columns: Drug | Current Stock | 14-day Forecast | Shortfall | Days Until Stockout | Status
    Highlight rows: stockout < 7 days → red, < 14 days → yellow
    Action: "Create PO" button per row → POST /purchase-orders
    """
```

## Step 3.6 — Simulate View

```python
# views/simulate.py
def render_simulation():
    st.header("Monsoon Surge Simulation")
    districts = st.multiselect("Select districts", district_list)
    intensity = st.slider("Rainfall Intensity Multiplier", 1.0, 3.0, 1.5)

    if st.button("Run Simulation"):
        result = requests.post(f"{BACKEND_URL}/simulate/monsoon",
                               json={"districts": districts, "intensity": intensity},
                               headers={"Authorization": f"Bearer {st.session_state.token}"})
        before_after = result.json()
        # Show before/after risk comparison as grouped bar chart
```

**Phase 3 deliverable:** Streamlit dashboard running at localhost:8501. Full demo flow working.

---

# Phase 4 — Go API Gateway

**Goal:** Production-grade gateway between UI and ML service. Handles auth, rate limiting, gRPC routing.

**Timeline estimate:** 1-1.5 days

**Note:** After this phase, the Streamlit UI should switch from calling FastAPI directly to calling the Go gateway. Both UIs (Streamlit + Next.js) talk to Go.

## Step 4.1 — Project Structure

```
gateway/
├── main.go
├── routes/
│   ├── districts.go
│   ├── hospitals.go
│   ├── purchase_orders.go
│   └── simulate.go
├── middleware/
│   ├── auth.go           ← JWT verification (Supabase public key)
│   └── ratelimit.go      ← per-role, per-endpoint rate limiting
├── grpc/
│   ├── client.go         ← gRPC client to FastAPI ML service
│   └── proto/            ← .proto files
│       ├── pharmasense.proto
│       └── pharmasense.pb.go (generated)
├── go.mod
├── go.sum
└── Dockerfile
```

## Step 4.2 — Proto Definition

```protobuf
// grpc/proto/pharmasense.proto
syntax = "proto3";
package pharmasense;

service PharmasenseML {
    rpc GetDistrictRisk (RiskRequest) returns (RiskResponse);
    rpc GetDemandForecast (ForecastRequest) returns (ForecastResponse);
    rpc GetHospitalBrief (BriefRequest) returns (BriefResponse);
    rpc SimulateMonsoon (SimulateRequest) returns (SimulateResponse);
}

message RiskRequest {
    string district_id = 1;
    string disease = 2;
}

message RiskResponse {
    string district_id = 1;
    float risk_score = 2;
    string risk_level = 3;
    int32 predicted_cases = 4;
    string model_used = 5;
    repeated DrugShortfall shortfalls = 6;
}

message DrugShortfall {
    string drug_id = 1;
    string drug_name = 2;
    int32 units_needed = 3;
    int32 current_stock = 4;
    int32 shortfall_units = 5;
}
// ... (ForecastRequest, BriefRequest, etc.)
```

## Step 4.3 — JWT Middleware

```go
// middleware/auth.go
// Verify Supabase JWT using Supabase project's JWT secret
// Extract claims: sub (user_id), app_role, hospital_id, district_id, state
// Attach to request context
// Return 401 if invalid, 403 if role insufficient for endpoint
```

## Step 4.4 — Rate Limiting

```go
// middleware/ratelimit.go
// Per-role limits:
//   state_minister:   100 req/min (they view dashboards, not writing)
//   district_officer: 60 req/min
//   pharmacist:       30 req/min
// Use golang.org/x/time/rate (token bucket)
// Return 429 with Retry-After header
```

## Step 4.5 — Route Handlers

```go
// Each handler:
// 1. Parse + validate request params
// 2. Check JWT role → enforce data scope (pharmacist can only query their hospital_id)
// 3. Forward to FastAPI via gRPC client
// 4. Marshal gRPC response → JSON
// 5. Return JSON response
```

**Phase 4 deliverable:** Go gateway running at localhost:8080. All REST endpoints working. gRPC calls to FastAPI working. JWT auth enforced.

---

# Phase 5 — Integration, Testing & Docker Compose

**Goal:** Full stack running together. End-to-end demo flow verified.

**Timeline estimate:** 1 day

## Step 5.1 — Docker Compose

```yaml
# infra/docker-compose.yml
services:
  zookeeper:
    image: confluentinc/cp-zookeeper:7.6.0
    environment: ZOOKEEPER_CLIENT_PORT: 2181

  kafka:
    image: confluentinc/cp-kafka:7.6.0
    depends_on: [zookeeper]
    ports: ["9092:9092"]
    environment:
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  fastapi:
    build: ./backend
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [kafka, redis]
    volumes:
      - ./ml/artifacts:/app/ml/artifacts
      - ./data:/app/data

  gateway:
    build: ./gateway
    ports: ["8080:8080"]
    env_file: .env
    depends_on: [fastapi]

  streamlit:
    build: ./frontend
    ports: ["8501:8501"]
    env_file: .env
    depends_on: [gateway]
```

## Step 5.2 — End-to-End Test Scenarios

```
Test 1: Full prediction pipeline
  1. Manually insert high rainfall into weather_signals for Chennai district
  2. Trigger run_daily_batch() via HTTP POST /admin/trigger-batch
  3. Assert: risk_scores updated for Tamil Nadu districts
  4. Assert: demand_forecasts created for dengue drugs
  5. Assert: purchase_orders created (PENDING)
  6. Assert: Kafka message published to outbreak_events

Test 2: WhatsApp approval flow
  1. Send test Twilio webhook POST /hooks/whatsapp with Body="YES"
  2. Assert: PO status updated to APPROVED
  3. Assert: inventory updated

Test 3: Monsoon simulation
  1. POST /simulate/monsoon with 3 districts, intensity=2.0
  2. Assert: before/after risk scores returned
  3. Assert: no Supabase writes from simulation

Test 4: Role-based access
  1. Login as pharmacist for Hospital X
  2. GET /api/hospitals → assert only Hospital X returned
  3. GET /api/districts → assert 403 Forbidden

Test 5: Redis cache behavior
  1. GET /api/districts/{id}/risk → first call (cache miss)
  2. GET /api/districts/{id}/risk → second call (cache hit, response time < 10ms)
  3. Insert weather anomaly → GET /api/districts/{id}/risk → cache invalidated
```

## Step 5.3 — GitHub Actions CI

```yaml
# .github/workflows/ci.yml
on: [push, pull_request]
jobs:
  test-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r backend/requirements.txt
      - run: pytest backend/tests/ -v

  test-gateway:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-go@v5
        with: { go-version: "1.22" }
      - run: go test ./gateway/...
```

**Phase 5 deliverable:** Full stack in Docker Compose. All 5 test scenarios passing. CI green.

---

# Phase 6 — Deployment (Production-Ready)

**Goal:** Live URLs for the demo. Not localhost.

**Timeline estimate:** 0.5 days

## Services & Platforms

| Service | Platform | Free Tier |
|---|---|---|
| FastAPI ML service | Render.com (Web Service) | Yes (sleeps after 15min) |
| Go Gateway | Render.com (Web Service) | Yes |
| Kafka | Upstash Kafka | Yes (10k msg/day) |
| Redis | Upstash Redis | Yes (256MB) |
| Streamlit frontend | Streamlit Cloud | Yes |
| Supabase | Supabase Cloud | Yes |

**Render caveats:**
- Free tier sleeps after 15 minutes of inactivity → cold start ~30s
- For the hackathon: acceptable. Use a cron job to ping /health every 10 min
- Model artifacts (.pt files): must be committed to a private artifacts repo or uploaded to Render persistent disk

## Environment Variables on Render

Same as `.env`. Set via Render dashboard → Environment section. Never committed.

**Phase 6 deliverable:** Live URLs. Demo accessible without localhost.

---

# Phase 7 — Next.js Frontend (After Backend THRIVING)

**Goal:** Production-grade UI. Same Go gateway API. Lift Supplite assets.

**Timeline estimate:** 2 days (after Phase 6 is stable)

**This phase starts ONLY when:**
- All Phase 0-6 deliverables are done
- Backend is stable and deployed
- The judges can already see a working Streamlit demo

## Stack

```
Next.js 14 (App Router)
deck.gl + react-map-gl    → 3D district heatmap (LIFTED from Supplite)
Recharts                  → signal timelines
Tailwind CSS              → styling
Supabase Auth JS          → client-side auth (same JWT as backend)
SWR                       → data fetching + stale-while-revalidate
Clerk (optional)          → if Supabase Auth JS lacks UI polish
```

## Assets to Lift from Supplite

```
Supplite source: d:\hackathob\pharmasense\supplite\
Assets to take:
  - The SciFiMap / deck.gl setup (3D heatmap component)
  - index.css design tokens (color palette, typography)
  - Sidebar shell component
  - API fetch patterns (weeklyBriefApi.js, realEstateApi.js → adapt to pharmasense endpoints)

What NOT to take:
  - Any supply chain / WSI / retail logic
  - Auth system (Supplite's auth is different)
  - Data models
```

## Page Structure

```
/ (redirect to /login)
/login                          → Supabase Auth login
/dashboard
  /dashboard/map                → 3D district heatmap (state_minister view)
  /dashboard/districts/[id]     → district detail (district_officer view)
  /dashboard/hospitals/[id]     → hospital detail (pharmacist view)
  /dashboard/hospitals/[id]/inventory → drug inventory table
  /dashboard/purchase-orders    → PO list + approval
  /dashboard/simulate           → monsoon simulation
```

## Key UI Components

```
<RiskMap3D />           → deck.gl ColumnLayer, same as Streamlit map_view.py but interactive
<SignalTimeline />       → Recharts ComposedChart (bar + line dual axis)
<InventoryTable />       → sortable table, highlight critical stock
<HospitalBrief />       → LLM brief rendered as markdown
<SimulationPanel />     → slider + district selector + animated before/after map
<POApprovalList />      → table of pending POs with approve/reject buttons
```

**Phase 7 deliverable:** Next.js app deployed on Vercel. Same data, better UI. Judge-ready.

---

## Phase Summary

| Phase | What | Duration | Dependency |
|---|---|---|---|
| 0 | Data Foundation — all datasets in Supabase | 1 day | Nothing |
| 1 | ML Training — ST-GNN + TFT artifacts | 2-3 days | Phase 0 |
| 2 | FastAPI ML Service — inference + Kafka + WhatsApp | 2 days | Phases 0+1 |
| 3 | Streamlit Dashboard — Phase 1 frontend | 1-1.5 days | Phase 2 |
| 4 | Go API Gateway — gRPC + JWT + rate limiting | 1-1.5 days | Phase 2 |
| 5 | Integration + Docker Compose + CI | 1 day | Phases 2+3+4 |
| 6 | Deployment — live URLs | 0.5 days | Phase 5 |
| 7 | Next.js Frontend — Phase 2 UI | 2 days | Phase 6 stable |
| **Total** | | **~11-12 days** | |

---

## What We Are NOT Building (Explicitly)

- No fake/mock data in any production path
- No continuous model retraining in v1 (honest: offline artifacts, MLflow in v2 roadmap)
- No live ERP integration (honest: manual pharmacist input, webhook-ready API contract)
- No GPU inference server in v1 (honest: CPU inference on Render, gRPC gateway is pre-built for Triton in v2)
- No pytrends district-level granularity (honest: state-level, broadcast to districts)

---

*Last updated: 2026-06-03*
*Phase version: 1.0 — locked for AgTechathon 2.0 2K26*
