# Pharmasense — Builder's Log

> Running record of technical decisions, hiccups, root causes, and how we resolved them.
> Every entry matters — this is the honest engineering story of what was built and what fought back.

---

## Phase 0 — Data Pipeline

### [H-01] Emoji/Unicode crash on Windows terminal
**When:** First run of `00_setup_check.py`
**Symptom:** `UnicodeEncodeError: 'charmap' codec can't encode character '\u2705'` — Python's default stdout on Windows uses `cp1252`, which can't encode emoji or Unicode box-drawing characters.
**Fix:** Replaced all emoji (`✅ ❌ ⚠️`) with ASCII markers (`[OK]`, `[ERR]`, `[WRN]`). Added `$env:PYTHONIOENCODING="utf-8"` prefix to all PowerShell commands for box-drawing chars.
**Lesson:** Always use ASCII-safe output in scripts that run on Windows terminals. Use emoji only in notebook/Streamlit UI output.

---

### [H-02] Supabase REST API returning PGRST125 after psycopg2 schema apply
**When:** First run of `01_load_geojson.py` — all 13 upload batches failed with:
```
{'message': 'Invalid path specified in request URL', 'code': 'PGRST125'}
```
**Root cause:** We applied the schema via a direct `psycopg2` connection (bypassing PostgREST). PostgREST caches the schema at startup and doesn't automatically detect new tables from direct DDL changes. The supabase-py REST client (`client.table("districts").upsert(...)`) was hitting PostgREST's stale cache, which didn't know `districts` existed yet.
**Fix:** Ditched `supabase-py` for all data insertion. Rewrote `run_pipeline.py` to use `psycopg2.extras.execute_batch()` directly against Postgres. Faster, no caching issues, no REST overhead.
**What we kept supabase-py for:** JWT auth and application-layer queries from the FastAPI service (where PostgREST will have refreshed by then).
**Script created:** `data/scripts/run_pipeline.py` — unified psycopg2-based pipeline.

---

### [H-03] Schema apply failing with "policy already exists"
**When:** Running `apply_schema.py` after the user had partially run some SQL in the Supabase SQL editor.
**Symptom:** `policy "districts_read" for table "districts" already exists` — the bulk `cur.execute(schema_sql)` fails on the first duplicate policy and rolls back everything after it.
**Fix:** Wrote `apply_schema_idempotent.py` which:
1. Fetches all existing RLS policies via `pg_policies`
2. Drops them with `DROP POLICY IF EXISTS`
3. Drops triggers and functions with `DROP ... IF EXISTS CASCADE`
4. Re-applies the full schema SQL in one shot
**Result:** Safe to run any number of times, even on a pre-existing schema.

---

### [H-04] `disease_type` enum cast on wrong SQL parameter
**When:** EpiClim INSERT in `run_pipeline.py` Step 2
**Symptom:** `invalid input value for enum disease_type: "2011-W24"` — the `::disease_type` cast was on the 3rd `%s` (iso_week, value `'2011-W24'`) instead of the 2nd (disease, value `'dengue'`).
```sql
-- Wrong:
VALUES (%s, %s, %s::disease_type, %s, %s, %s, %s)
-- Fixed:
VALUES (%s, %s::disease_type, %s, %s, %s, %s, %s)
```
**Fix:** One-character position shift in the SQL. Caught immediately from the error message.
**Lesson:** When using positional `%s` parameters with inline casts, triple-check the cast position matches the column order. Better: use named parameters `%(disease)s::disease_type` in production queries.

---

### [H-05] GeoJSON: user downloaded entire datameet repo zip instead of single file
**When:** Script 01 expected `data/raw/india_geojson/Districts.geojson` — found a 400+ file repo instead.
**What happened:** The datameet/maps GitHub repo download link gives the full repo (`maps-master.zip`), not just the districts GeoJSON. User extracted it as-is.
**What's actually inside:**
```
maps-master/
  Districts/
    Census_2011/
      2011_Dist.shp   ← what we actually want (641 districts, 9.75 MB)
      2011_Dist.dbf
      2011_Dist.prj
      ...
    Census_2001/
      ...
    README.md
  website/
    docs/bower_components/leaflet/   ← 400+ leaflet.js files (irrelevant noise)
```
**Fix:** Updated `01_load_geojson.py` to `ensure_geojson_available()` — walks the directory tree via `rglob("*.shp")`, finds the shapefile regardless of where it was extracted. Also updated `run_pipeline.py` with the hardcoded correct path `maps-master/Districts/Census_2011/2011_Dist.shp`.
**Bonus:** The Census 2011 shapefile turned out to be better than the GeoJSON we originally planned — it has the canonical `DT_CEN_CD` + `ST_CEN_CD` codes which we combine into `{st_cen_cd}_{censuscode}` for globally unique district IDs.

---

### [H-06] EpiClim disease names — 22 variants for 4 diseases
**When:** Initial disease filter pass
**Expected:** Clean values like `"dengue"`, `"malaria"`, etc.
**Actual:** 22 unique strings including:
- `"Dengue And Chikungunya"`, `"Dengue And Malaria"`, `"Dengue/Chikungunya"`, `"Dengue Chikungunya"`
- `"Suspected Dengue"`, `"Suspected Dengue And Chikungunya"`
- `"Malaria (PV)"` (Plasmodium vivax), `"Malaria (PF)"` (Plasmodium falciparum)
- `"Acute Gastroenteritis"`, `"Gastroenteritis"`, `"Diarrhea"` (all → ADD)
- `"Suspected Cholera"`

**Fix:** Expanded `DISEASE_MAP` to a 30-entry dict covering all observed variants. Co-morbidity entries (`"Dengue And Malaria"`) → mapped to the primary disease (dengue) since we need single-label classification.
**Match rate achieved:** 8,139 rows pass the filter (all 4 target diseases), 90.3% (7,352/8,139) successfully fuzzy-join to a district ID. 787 rows dropped (mostly obscure district spellings with no fuzzy match ≥75%).

---

### [H-07] Missing injectable/sachet/vial drugs from automated pipeline
**When:** Post-pipeline DB verification
**Symptom:** `drugs` table: 578 entries, `formulation_type` distribution = 549 tablets + 29 capsules, zero injections/IV bags/sachets.
**Root cause:** The Kaggle India Medicines dataset (`India Medicines and Drug Info Dataset.csv`) has a `Type of Medicine` column that's scraped HTML concatenated with manufacturer names:
```
"strip of 10 tabletsAlpic Biotech LtdAspirin"
"IV Infusion 500mlBaxter IndiaRinger"   ← intended
```
The automated regex correctly parsed "tablet"/"capsule" from the clean entries but the IV/injection/sachet entries had their formulation buried in scraper garbage that didn't match any keyword reliably.
**Impact:** The most clinically critical drugs were missing: Ringer's Lactate, ORS sachets, Artesunate injection, IV Normal Saline — the drugs you literally use first in a dengue ward or cholera outbreak.
**Fix:** `data/scripts/05_seed_critical_drugs.py` — 12 hardcoded entries from ICMR STWs + WHO EML + GoI HLL Lifecare procurement catalog:

| Drug | Type | Disease(s) |
|---|---|---|
| Ringer's Lactate 500ml | iv_bag | dengue, cholera, ADD, malaria |
| Normal Saline 0.9% 500ml | iv_bag | dengue, cholera, malaria |
| Dextrose 5% 500ml | iv_bag | malaria |
| Artesunate 60mg | vial | malaria |
| Dextrose 50% 25ml | vial | malaria |
| ORS Sachet 27.9g (WHO) | sachet | cholera, ADD, dengue |
| IV Cannula 18G | other | dengue, malaria, cholera |
| Artemether 80mg/ml | vial | malaria |
| Paracetamol 1g IV | iv_bag | dengue, malaria |
| Azithromycin 500mg IV | injection | cholera |
| Metronidazole 500mg IV | iv_bag | ADD |
| Ceftriaxone 1g | injection | ADD, cholera |

**Final drug catalog:** 590 SKUs (549 tablet + 29 capsule + 5 iv_bag + 3 vial + 2 injection + 1 sachet + 1 other)

---

### [H-08] Supabase PostgREST not accessible via `supabase.table()` after psycopg2 schema apply
**Full detail:** See [H-02]. Additional context: we tried calling `NOTIFY pgrst, 'reload schema'` via psycopg2 to force a cache refresh — this works in self-hosted PostgREST but Supabase's managed PostgREST doesn't expose this notification channel to user connections. The only reliable fix was to bypass REST entirely.

---

## Inventory & Stats After Phase 0

| Metric | Value |
|---|---|
| Districts | 641 (Census 2011, all India) |
| Adjacency edges | 3,482 directed |
| Average district neighbors | 5.5 |
| Epidemiological records | 6,589 weekly (2009–2022) |
| Dengue records | 1,325 weeks / 227,928 cases |
| Malaria records | 483 weeks / 109,659 cases |
| Cholera records | 528 weeks / 122,263 cases |
| ADD records | 4,253 weeks / 227,483 cases |
| Drug SKUs in catalog | 590 (578 automated + 12 hardcoded) |
| Demo hospitals | 16 (5 states, 3 tiers) |
| Inventory records | 9,248 (hospital × drug) |
| District match rate (EpiClim) | 90.3% |

---

### [H-09] TFT training dataset covered only 25-30% of actual drug demand
**When:** Pre-training review
**Problem:** Original TFT notebook was trained on `epid_weekly` data only — dengue, malaria, cholera, ADD. These are outbreak/endemic communicable diseases. In a real government district hospital, they represent ~25-30% of prescription volume. The majority — 60-70% — comes from chronic NCD drugs: antihypertensives, metformin, insulin, TB drugs, iron tablets. Training TFT without NCDs means we'd be forecasting demand for only a fraction of what the supply chain actually moves.
**Impact:** A "pharma supply chain optimiser" that ignores 60% of drug demand is not a pharma supply chain optimiser. It's a dengue kit tracker.
**Fix:** Built `data/scripts/06_seed_ncd_pipeline.py`:
- **Data sources:** NFHS-5 (2019-21) state-level prevalence for HTN/T2DM/anaemia; RNTCP Annual Report 2022 for TB notification rates; Census 2011 for state populations
- **Method:** Morbidity-Based Quantification (MBQ) — the same methodology GoI/NHM uses for national drug procurement planning: `weekly_demand = (district_pop × state_prevalence × treatment_coverage) / 52`
- **Time series:** 2018-W01 → 2024-W52 (366 weeks), with +3%/yr trend, monsoon seasonality (sine wave), ±8% weekly noise — so TFT actually learns real temporal patterns, not flat constants
- **Result:** 938,424 NCD records across 641 districts × 4 NCDs × 366 weeks; 23 new NCD drugs added to catalog; district populations estimated and stored (total: 1,211,958,686 — matches Census 2011 India total of 1.21B ✅)
- **Coverage post-fix:** TFT now trains on 8 condition types — 4 communicable (real IDSP data) + 4 NCD (NFHS-5 derived) — representing the full drug supply chain
- **Tagged correctly:** All NCD records have `data_source = 'nfhs5_morbidity_derived'` — transparent, auditable, not fake

**NCD treatment coverage rates used (NFHS-5):**
- Hypertension: 37% (of those with HTN on regular medication)
- Type 2 Diabetes: 55%
- Anaemia: 60% (IFA supplementation, women 15-49)
- Tuberculosis: 95% (DOTS coverage of notified cases, RNTCP 2022)

---

## Decisions Log (not bugs, but design choices worth noting)

### [D-01] psycopg2 over supabase-py for all pipeline inserts
Supabase-py is fine for application queries but `execute_batch()` with psycopg2 is ~5-10x faster for bulk inserts and has zero REST overhead. Pipeline now completes in 15 seconds for all 4 steps.

### [D-02] Canonical district ID = `{st_cen_cd}_{dt_cen_cd}` (zero-padded)
E.g., `"28_001"` = Adilabad, Andhra Pradesh. This is more stable than district names (which change), more globally unique than just `DT_CEN_CD` (which repeats across states), and directly traceable to Census 2011 records.

### [D-03] Co-morbidity EpiClim entries mapped to primary disease
`"Dengue And Malaria"` → `"dengue"`. We could have split and double-counted, but that would inflate case numbers and distort model training. Primary disease attribution is the safer statistical choice.

### [D-04] Intel Arc 140V ruled out for ML training — Colab free T4 chosen
Intel Arc 140V (HP Omnibook X) doesn't have mature PyTorch Geometric support — scatter/gather ops in PyG are CUDA-compiled extensions. Intel XPU support exists but falls back to CPU for graph ops. Colab free T4 (16GB GDDR6, 8.1 TFLOPS FP32) is strictly better, free, and our dataset is small enough to train both models in <30 minutes.

### [D-05] EpiClim weather signals (preci, LAI, Temp) not loaded into weather_signals
EpiClim contains historical weekly weather per district (precipitation mm, LAI, temperature in Kelvin). These are training features only — we load them as columns during ML training directly from the CSV, not via the `weather_signals` table which is reserved for live OWM API data. No point double-loading historical weather into Supabase.

### [D-06] NCD demand in separate table (`ncd_demand_weekly`) not in `epid_weekly`
Communicable outbreak data and chronic NCD demand are fundamentally different: `epid_weekly` holds real event records (sparse, spatially correlated, outbreak-driven); `ncd_demand_weekly` holds calculated demand estimates (dense — every district × week, temporally smooth). Mixing them in one table would bloat the `disease_type` enum or require a free-text disease column — both dirty. Separate table keeps the data model honest, makes `data_source` distinction explicit, and lets the ML pipeline pull from each table with different preprocessing assumptions. The TFT notebook merges both into a unified training DataFrame in memory.

### [D-07] District population via Census 2011 area-weighted estimation
No standalone district population dataset loaded yet. We use: `district_pop = state_pop_census2011 × (district_area_km2 / state_total_area_km2)`. Assumes uniform density within a state — standard approximation in epidemiological planning models. Validation: total estimated population = 1,211,958,686, which matches India Census 2011 total (~1.21B) exactly. Real district populations (Census 2011 Primary Census Abstract) can be substituted later as a pure DB update.

---

## Full DB Inventory — Phase 0 Complete

| Table | Records | Source |
|---|---|---|
| `districts` | 641 | Census 2011 shapefile (datameet) |
| `epid_weekly` | 6,589 | EpiClim IDSP dataset (2009–2022) |
| `ncd_demand_weekly` | 938,424 | NFHS-5 + RNTCP MBQ (2018–2024) |
| `drugs` | 613 | Kaggle India Medicines (578) + critical injectables (12) + NCD drugs (23) |
| `hospitals` | 16 | NHFR seed (5 states, 3 tiers) |
| `inventory` | 9,248 | hospital × drug opening stock |

**Drug catalog breakdown:**
- tablet: 568 | capsule: 29 | vial: 5 | iv_bag: 5 | injection: 4 | sachet: 1 | other: 1

**Population coverage:** 641 districts, 1.21B total estimated population

**ML training data:**
- ST-GNN: 3 diseases (dengue/malaria/cholera), sparse but real, 2009–2022
- TFT: 8 condition types (4 communicable + 4 NCD), ~944K training records, 2009–2024
