-- ============================================================
-- Pharmasense — Supabase Database Schema
-- Run this in Supabase SQL Editor (Project > SQL Editor > New Query)
-- Order matters: extensions → tables → indexes → RLS policies
-- ============================================================

-- ─── Extensions ──────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- for fuzzy text search

-- ─── ENUM types ───────────────────────────────────────────────────────────────
DO $$ BEGIN
    CREATE TYPE hospital_tier AS ENUM ('PHC', 'CHC', 'District', 'State');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE disease_type AS ENUM (
        'dengue', 'malaria', 'cholera', 'acute_diarrhoeal_disease'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE po_status AS ENUM (
        'PENDING', 'APPROVED', 'REJECTED', 'DISPATCHED', 'RECEIVED'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE formulation_type AS ENUM (
        'tablet', 'capsule', 'injection', 'vial', 'iv_bag',
        'oral_solution', 'sachet', 'powder', 'topical', 'drops', 'other'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE transaction_type AS ENUM (
        'dispensed', 'received', 'adjustment', 'opening_stock'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE app_role AS ENUM (
        'state_minister', 'district_officer', 'pharmacist'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ─── REFERENCE TABLES ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS districts (
    id              TEXT        PRIMARY KEY,        -- DT_CEN_CD from DataMeet GeoJSON
    name            TEXT        NOT NULL,
    state           TEXT        NOT NULL,
    centroid_lat    DOUBLE PRECISION,
    centroid_lon    DOUBLE PRECISION,
    area_km2        DOUBLE PRECISION,
    geom            GEOGRAPHY(GEOMETRY, 4326),      -- PostGIS polygon for spatial queries
    adjacency_ids   TEXT[]      DEFAULT '{}',       -- neighbor district IDs (for ST-GNN)
    population      BIGINT,                         -- Census 2011 district population
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS districts_geom_idx   ON districts USING GIST (geom);
CREATE INDEX IF NOT EXISTS districts_state_idx  ON districts (state);
CREATE INDEX IF NOT EXISTS districts_name_trgm  ON districts USING GIN (name gin_trgm_ops);

COMMENT ON TABLE districts IS 'India district boundaries from DataMeet, with adjacency for ST-GNN graph construction';

-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS drugs (
    id                  UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                TEXT        NOT NULL,           -- commercial/brand name
    generic_name        TEXT        NOT NULL,           -- e.g. "paracetamol"
    dose_mg             NUMERIC,                        -- e.g. 500 (from composition parse)
    formulation_type    formulation_type NOT NULL DEFAULT 'other',
    pack_size_units     INT,                            -- units per pack (e.g. 10 tablets/strip)
    price_inr           NUMERIC(10, 2),                 -- MRP per pack
    manufacturer_name   TEXT,
    icmr_diseases       TEXT[]      DEFAULT '{}',       -- diseases this drug treats per ICMR
    is_active           BOOLEAN     DEFAULT TRUE,
    external_1mg_id     INT,                            -- original row id from Kaggle dataset
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS drugs_generic_idx     ON drugs (generic_name);
CREATE INDEX IF NOT EXISTS drugs_icmr_idx        ON drugs USING GIN (icmr_diseases);
CREATE INDEX IF NOT EXISTS drugs_active_idx      ON drugs (is_active) WHERE is_active = TRUE;

COMMENT ON TABLE drugs IS 'ICMR-relevant drug catalog seeded from India Medicines Kaggle dataset';

-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS hospitals (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT        NOT NULL,
    district_id     TEXT        REFERENCES districts(id) ON DELETE RESTRICT,
    lat             DOUBLE PRECISION NOT NULL,
    lon             DOUBLE PRECISION NOT NULL,
    tier            hospital_tier NOT NULL DEFAULT 'District',
    bed_count       INT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS hospitals_district_idx ON hospitals (district_id);

COMMENT ON TABLE hospitals IS 'Demo hospitals seeded from NHFR public data, ~16 across 5 states';

-- ─── EPIDEMIOLOGICAL DATA ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS epid_weekly (
    id              BIGSERIAL   PRIMARY KEY,
    district_id     TEXT        REFERENCES districts(id) ON DELETE CASCADE,
    disease         disease_type NOT NULL,
    iso_week        TEXT        NOT NULL,               -- "2023-W24"
    week_start_date DATE        NOT NULL,               -- Monday of that week
    cases           INT         NOT NULL DEFAULT 0,
    deaths          INT         NOT NULL DEFAULT 0,
    cases_per_100k  NUMERIC(10, 4),                     -- computed during import (requires population)
    data_source     TEXT        DEFAULT 'epiclim_zenodo_14580510',
    created_at      TIMESTAMPTZ DEFAULT now(),

    CONSTRAINT epid_weekly_unique UNIQUE (district_id, disease, iso_week)
);

CREATE INDEX IF NOT EXISTS epid_weekly_district_idx ON epid_weekly (district_id);
CREATE INDEX IF NOT EXISTS epid_weekly_disease_idx  ON epid_weekly (disease, iso_week);
CREATE INDEX IF NOT EXISTS epid_weekly_date_idx     ON epid_weekly (week_start_date DESC);

COMMENT ON TABLE epid_weekly IS 'EpiClim dataset: weekly district-level case counts 2009-2023, fuzzy-joined to districts';

-- ─── LIVE SIGNALS ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS weather_signals (
    id              BIGSERIAL   PRIMARY KEY,
    district_id     TEXT        REFERENCES districts(id) ON DELETE CASCADE,
    fetched_at      TIMESTAMPTZ NOT NULL,
    temp_celsius    NUMERIC(5, 2),
    humidity_pct    NUMERIC(5, 2),
    rain_1h_mm      NUMERIC(8, 3) DEFAULT 0,
    rain_3h_mm      NUMERIC(8, 3) DEFAULT 0,
    weather_cond    TEXT,                               -- "Rain","Clear","Clouds" from OWM
    is_interpolated BOOLEAN     DEFAULT FALSE,          -- TRUE if IDW-estimated from neighbors
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS weather_signals_district_ts_idx ON weather_signals (district_id, fetched_at DESC);
CREATE INDEX IF NOT EXISTS weather_signals_ts_idx          ON weather_signals (fetched_at DESC);

COMMENT ON TABLE weather_signals IS 'OpenWeatherMap hourly signals; ~50 districts direct, rest IDW-interpolated';

-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS search_signals (
    id              BIGSERIAL   PRIMARY KEY,
    state           TEXT        NOT NULL,
    disease         disease_type NOT NULL,
    iso_week        TEXT        NOT NULL,
    search_index    INT         NOT NULL CHECK (search_index BETWEEN 0 AND 100),
    search_velocity NUMERIC(6, 2),                      -- week-over-week delta (positive = rising)
    fetched_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now(),

    CONSTRAINT search_signals_unique UNIQUE (state, disease, iso_week)
);

CREATE INDEX IF NOT EXISTS search_signals_state_idx ON search_signals (state, disease, iso_week);

COMMENT ON TABLE search_signals IS 'Google Trends via pytrends — state-level symptom search indices, weekly';

-- ─── ML OUTPUTS ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS risk_scores (
    id              BIGSERIAL   PRIMARY KEY,
    district_id     TEXT        REFERENCES districts(id) ON DELETE CASCADE,
    disease         disease_type NOT NULL,
    score           NUMERIC(5, 4) NOT NULL CHECK (score BETWEEN 0 AND 1),
    risk_level      TEXT        GENERATED ALWAYS AS (
                        CASE
                            WHEN score >= 0.70 THEN 'HIGH'
                            WHEN score >= 0.40 THEN 'MEDIUM'
                            ELSE 'LOW'
                        END
                    ) STORED,
    model_used      TEXT        NOT NULL CHECK (model_used IN ('stgnn', 'tft', 'prophet_fallback')),
    predicted_cases INT,                                -- estimated cases for horizon window
    prediction_date DATE        NOT NULL,
    horizon_days    INT         NOT NULL DEFAULT 14,
    -- Input feature snapshots (for explainability)
    weather_score   NUMERIC(5, 4),
    search_score    NUMERIC(5, 4),
    epid_baseline   NUMERIC(10, 4),                     -- recent cases_per_100k baseline
    created_at      TIMESTAMPTZ DEFAULT now(),

    CONSTRAINT risk_scores_unique UNIQUE (district_id, disease, prediction_date)
);

CREATE INDEX IF NOT EXISTS risk_scores_district_date_idx ON risk_scores (district_id, prediction_date DESC);
CREATE INDEX IF NOT EXISTS risk_scores_level_idx         ON risk_scores (risk_level, prediction_date DESC);
CREATE INDEX IF NOT EXISTS risk_scores_disease_idx       ON risk_scores (disease, prediction_date DESC);

COMMENT ON TABLE risk_scores IS 'ST-GNN or TFT model outputs: risk probability per district per disease per day';

-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS demand_forecasts (
    id              BIGSERIAL   PRIMARY KEY,
    district_id     TEXT        REFERENCES districts(id) ON DELETE CASCADE,
    drug_id         UUID        REFERENCES drugs(id) ON DELETE CASCADE,
    risk_score_id   BIGINT      REFERENCES risk_scores(id) ON DELETE SET NULL,
    forecast_units  INT         NOT NULL,               -- units needed (per pack)
    forecast_date   DATE        NOT NULL,
    horizon_days    INT         NOT NULL DEFAULT 14,
    severity_mix    JSONB,                              -- {"mild_pct": 0.8, "severe_pct": 0.2}
    created_at      TIMESTAMPTZ DEFAULT now(),

    CONSTRAINT demand_forecasts_unique UNIQUE (district_id, drug_id, forecast_date)
);

CREATE INDEX IF NOT EXISTS demand_forecasts_district_idx ON demand_forecasts (district_id, forecast_date DESC);
CREATE INDEX IF NOT EXISTS demand_forecasts_drug_idx     ON demand_forecasts (drug_id, forecast_date DESC);

COMMENT ON TABLE demand_forecasts IS 'ICMR translation layer output: drug units needed per district per disease outbreak';

-- ─── INVENTORY & OPERATIONS ─────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS inventory (
    id              BIGSERIAL   PRIMARY KEY,
    hospital_id     UUID        REFERENCES hospitals(id) ON DELETE CASCADE,
    drug_id         UUID        REFERENCES drugs(id) ON DELETE CASCADE,
    stock_units     INT         NOT NULL DEFAULT 0 CHECK (stock_units >= 0),
    reorder_point   INT         DEFAULT 50,             -- trigger PO below this
    updated_at      TIMESTAMPTZ DEFAULT now(),

    CONSTRAINT inventory_unique UNIQUE (hospital_id, drug_id)
);

CREATE INDEX IF NOT EXISTS inventory_hospital_idx ON inventory (hospital_id);

COMMENT ON TABLE inventory IS 'Current drug stock per hospital; updated by pharmacist or on PO receipt';

-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS inventory_transactions (
    id              BIGSERIAL   PRIMARY KEY,
    hospital_id     UUID        REFERENCES hospitals(id) ON DELETE CASCADE,
    drug_id         UUID        REFERENCES drugs(id) ON DELETE CASCADE,
    delta_units     INT         NOT NULL,               -- +ve = restock, -ve = dispensed
    transaction_type transaction_type NOT NULL,
    user_id         UUID,                               -- auth.users.id
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS inv_txn_hospital_idx ON inventory_transactions (hospital_id, created_at DESC);

COMMENT ON TABLE inventory_transactions IS 'Full transaction log for inventory changes (audit trail)';

-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS purchase_orders (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    hospital_id     UUID        REFERENCES hospitals(id) ON DELETE CASCADE,
    drug_id         UUID        REFERENCES drugs(id) ON DELETE CASCADE,
    qty_units       INT         NOT NULL CHECK (qty_units > 0),
    unit_price_inr  NUMERIC(10, 2),
    total_inr       NUMERIC(12, 2) GENERATED ALWAYS AS (qty_units * unit_price_inr) STORED,
    status          po_status   NOT NULL DEFAULT 'PENDING',
    trigger_source  TEXT        NOT NULL CHECK (trigger_source IN ('ml_alert', 'manual', 'whatsapp_approval')),
    risk_score_id   BIGINT      REFERENCES risk_scores(id) ON DELETE SET NULL,
    approved_by     UUID,                               -- auth.users.id
    approved_at     TIMESTAMPTZ,
    whatsapp_sent   BOOLEAN     DEFAULT FALSE,
    whatsapp_msg_sid TEXT,                              -- Twilio message SID for tracking
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS po_hospital_status_idx ON purchase_orders (hospital_id, status);
CREATE INDEX IF NOT EXISTS po_status_date_idx     ON purchase_orders (status, created_at DESC);

COMMENT ON TABLE purchase_orders IS 'Auto-generated or manual purchase orders; approved via dashboard or WhatsApp reply';

-- ─── AUDIT LOG ─────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS audit_log (
    id              BIGSERIAL   PRIMARY KEY,
    table_name      TEXT        NOT NULL,
    action          TEXT        NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
    row_id          TEXT        NOT NULL,
    user_id         UUID,
    old_values      JSONB,
    new_values      JSONB,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_log_table_idx ON audit_log (table_name, created_at DESC);

-- ─── TRIGGER: auto-update inventory.updated_at ────────────────────────────────
CREATE OR REPLACE FUNCTION update_inventory_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS inventory_updated_at ON inventory;
CREATE TRIGGER inventory_updated_at
    BEFORE UPDATE ON inventory
    FOR EACH ROW EXECUTE FUNCTION update_inventory_timestamp();

-- ─── TRIGGER: inventory_transactions → auto-update inventory.stock_units ──────
CREATE OR REPLACE FUNCTION apply_inventory_transaction()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO inventory (hospital_id, drug_id, stock_units)
    VALUES (NEW.hospital_id, NEW.drug_id, GREATEST(0, NEW.delta_units))
    ON CONFLICT (hospital_id, drug_id)
    DO UPDATE SET
        stock_units = GREATEST(0, inventory.stock_units + NEW.delta_units),
        updated_at  = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS inventory_txn_apply ON inventory_transactions;
CREATE TRIGGER inventory_txn_apply
    AFTER INSERT ON inventory_transactions
    FOR EACH ROW EXECUTE FUNCTION apply_inventory_transaction();

-- ─── ROW LEVEL SECURITY ────────────────────────────────────────────────────────
-- Enable RLS on all tables
ALTER TABLE districts           ENABLE ROW LEVEL SECURITY;
ALTER TABLE drugs               ENABLE ROW LEVEL SECURITY;
ALTER TABLE hospitals           ENABLE ROW LEVEL SECURITY;
ALTER TABLE epid_weekly         ENABLE ROW LEVEL SECURITY;
ALTER TABLE weather_signals     ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_signals      ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_scores         ENABLE ROW LEVEL SECURITY;
ALTER TABLE demand_forecasts    ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory           ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE purchase_orders     ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log           ENABLE ROW LEVEL SECURITY;

-- Helper: extract app_role from JWT
CREATE OR REPLACE FUNCTION auth_role()
RETURNS TEXT AS $$
    SELECT COALESCE(
        auth.jwt() -> 'user_metadata' ->> 'app_role',
        auth.jwt() ->> 'role',
        'anon'
    );
$$ LANGUAGE sql STABLE;

-- Helper: extract hospital_id from JWT
CREATE OR REPLACE FUNCTION auth_hospital_id()
RETURNS UUID AS $$
    SELECT (auth.jwt() -> 'user_metadata' ->> 'hospital_id')::UUID;
$$ LANGUAGE sql STABLE;

-- Helper: extract district_name from JWT
CREATE OR REPLACE FUNCTION auth_district_name()
RETURNS TEXT AS $$
    SELECT auth.jwt() -> 'user_metadata' ->> 'district_name';
$$ LANGUAGE sql STABLE;

-- Helper: extract state from JWT
CREATE OR REPLACE FUNCTION auth_state()
RETURNS TEXT AS $$
    SELECT auth.jwt() -> 'user_metadata' ->> 'state';
$$ LANGUAGE sql STABLE;

-- ── districts: all authenticated users can read ──────────────────────────────
CREATE POLICY "districts_read" ON districts
    FOR SELECT USING (auth.role() = 'authenticated');

-- ── drugs: all authenticated users can read ──────────────────────────────────
CREATE POLICY "drugs_read" ON drugs
    FOR SELECT USING (auth.role() = 'authenticated');

-- ── hospitals: role-scoped read ──────────────────────────────────────────────
-- state_minister sees all hospitals in their state
CREATE POLICY "hospitals_minister_read" ON hospitals
    FOR SELECT USING (
        auth.role() = 'authenticated'
        AND auth_role() = 'state_minister'
        AND district_id IN (
            SELECT id FROM districts WHERE state = auth_state()
        )
    );

-- district_officer sees all hospitals in their district
CREATE POLICY "hospitals_district_read" ON hospitals
    FOR SELECT USING (
        auth.role() = 'authenticated'
        AND auth_role() = 'district_officer'
        AND district_id IN (
            SELECT id FROM districts WHERE name = auth_district_name()
        )
    );

-- pharmacist sees only their hospital
CREATE POLICY "hospitals_pharmacist_read" ON hospitals
    FOR SELECT USING (
        auth.role() = 'authenticated'
        AND auth_role() = 'pharmacist'
        AND id = auth_hospital_id()
    );

-- ── epid_weekly: all authenticated can read (public health data) ──────────────
CREATE POLICY "epid_weekly_read" ON epid_weekly
    FOR SELECT USING (auth.role() = 'authenticated');

-- ── weather_signals: all authenticated can read ───────────────────────────────
CREATE POLICY "weather_signals_read" ON weather_signals
    FOR SELECT USING (auth.role() = 'authenticated');

-- ── search_signals: all authenticated can read ───────────────────────────────
CREATE POLICY "search_signals_read" ON search_signals
    FOR SELECT USING (auth.role() = 'authenticated');

-- ── risk_scores: all authenticated can read ───────────────────────────────────
CREATE POLICY "risk_scores_read" ON risk_scores
    FOR SELECT USING (auth.role() = 'authenticated');

-- ── demand_forecasts: all authenticated can read ─────────────────────────────
CREATE POLICY "demand_forecasts_read" ON demand_forecasts
    FOR SELECT USING (auth.role() = 'authenticated');

-- ── inventory: scoped by role ─────────────────────────────────────────────────
CREATE POLICY "inventory_minister_read" ON inventory
    FOR SELECT USING (
        auth.role() = 'authenticated'
        AND auth_role() = 'state_minister'
    );

CREATE POLICY "inventory_district_read" ON inventory
    FOR SELECT USING (
        auth.role() = 'authenticated'
        AND auth_role() = 'district_officer'
        AND hospital_id IN (
            SELECT h.id FROM hospitals h
            JOIN districts d ON h.district_id = d.id
            WHERE d.name = auth_district_name()
        )
    );

CREATE POLICY "inventory_pharmacist_read" ON inventory
    FOR SELECT USING (
        auth.role() = 'authenticated'
        AND auth_role() = 'pharmacist'
        AND hospital_id = auth_hospital_id()
    );

-- Pharmacist can update their own inventory (write)
CREATE POLICY "inventory_pharmacist_write" ON inventory_transactions
    FOR INSERT WITH CHECK (
        auth.role() = 'authenticated'
        AND auth_role() = 'pharmacist'
        AND hospital_id = auth_hospital_id()
    );

-- ── purchase_orders: scoped by role ──────────────────────────────────────────
CREATE POLICY "po_minister_read" ON purchase_orders
    FOR SELECT USING (
        auth.role() = 'authenticated'
        AND auth_role() = 'state_minister'
    );

CREATE POLICY "po_district_read" ON purchase_orders
    FOR SELECT USING (
        auth.role() = 'authenticated'
        AND auth_role() = 'district_officer'
        AND hospital_id IN (
            SELECT h.id FROM hospitals h
            JOIN districts d ON h.district_id = d.id
            WHERE d.name = auth_district_name()
        )
    );

CREATE POLICY "po_pharmacist_read" ON purchase_orders
    FOR SELECT USING (
        auth.role() = 'authenticated'
        AND auth_role() = 'pharmacist'
        AND hospital_id = auth_hospital_id()
    );

CREATE POLICY "po_pharmacist_approve" ON purchase_orders
    FOR UPDATE USING (
        auth.role() = 'authenticated'
        AND auth_role() = 'pharmacist'
        AND hospital_id = auth_hospital_id()
    );

-- ── audit_log: only service role can write; state_minister can read ───────────
CREATE POLICY "audit_minister_read" ON audit_log
    FOR SELECT USING (
        auth.role() = 'authenticated'
        AND auth_role() = 'state_minister'
    );

-- Service role bypasses all RLS (used by data pipeline scripts)
-- This is automatic for service_role key — no policy needed

-- ─── VERIFICATION QUERIES ─────────────────────────────────────────────────────
-- Run these after loading data to verify integrity:
--
-- SELECT COUNT(*) FROM districts;                  -- expect 500-700
-- SELECT COUNT(DISTINCT district_id) FROM epid_weekly; -- expect 300-500
-- SELECT disease, COUNT(*), SUM(cases) FROM epid_weekly GROUP BY disease;
-- SELECT formulation_type, COUNT(*) FROM drugs GROUP BY formulation_type;
-- SELECT unnest(icmr_diseases), COUNT(*) FROM drugs GROUP BY 1;
-- SELECT tier, COUNT(*) FROM hospitals GROUP BY tier;
-- SELECT COUNT(*) FROM inventory;                  -- expect hospitals * drugs
