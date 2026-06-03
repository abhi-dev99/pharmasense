"""
Phase 0 — Unified Data Loader (psycopg2-based)
Bypasses Supabase REST API entirely. Uses direct PostgreSQL inserts.
Runs all 4 pipelines: GeoJSON → EpiClim → Medicines → Hospitals

Usage: python data/scripts/run_pipeline.py --db-password pharmasons99lite
"""

import sys
import os
import re
import json
import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import psycopg2
import psycopg2.extras
import pandas as pd
import numpy as np
import geopandas as gpd
from tqdm import tqdm
from rapidfuzz import process, fuzz

# ─── DB Connection ─────────────────────────────────────────────────────────────
def get_conn(password: str):
    url = os.getenv("SUPABASE_URL", "")
    ref = url.replace("https://", "").split(".")[0]
    conn = psycopg2.connect(
        host=f"db.{ref}.supabase.co",
        port=5432, dbname="postgres",
        user="postgres", password=password,
        sslmode="require", connect_timeout=20,
    )
    conn.autocommit = True
    return conn

# ─── STEP 1: Load GeoJSON ──────────────────────────────────────────────────────
def step1_geojson(cur):
    print("\n" + "="*60)
    print("  STEP 1 — Districts (GeoJSON / Shapefile)")
    print("="*60)

    shp_path = ROOT / "data/raw/india_geojson/maps-master/Districts/Census_2011/2011_Dist.shp"
    if not shp_path.exists():
        candidates = list((ROOT / "data/raw/india_geojson").rglob("*.shp"))
        if candidates:
            shp_path = candidates[0]
        else:
            print("[ERR] No shapefile found"); return False

    print(f"Loading {shp_path.name}...")
    gdf = gpd.read_file(str(shp_path)).to_crs(epsg=4326)
    print(f"  {len(gdf)} districts loaded")

    # Column mapping
    cols = {c.lower(): c for c in gdf.columns}
    gdf = gdf.rename(columns={
        cols.get("district", cols.get("dt_nm", "DISTRICT")): "district_name",
        cols.get("st_nm", cols.get("state", "ST_NM")):       "state_name",
        cols.get("censuscode", cols.get("dt_cen_cd", "censuscode")): "censuscode",
        cols.get("st_cen_cd", "ST_CEN_CD"):                  "st_cen_cd",
    })

    # Build canonical ID: state_code + district_code, zero padded
    gdf["district_id"] = (
        gdf["st_cen_cd"].astype(str).str.zfill(2) + "_" +
        gdf["censuscode"].astype(str).str.zfill(3)
    )

    # Centroids (project first for accuracy)
    gdf_proj = gdf.to_crs(epsg=32643)
    centroids = gdf.geometry.centroid  # in WGS84
    gdf["centroid_lat"] = centroids.y.round(6)
    gdf["centroid_lon"] = centroids.x.round(6)
    gdf["area_km2"]     = (gdf_proj.geometry.area / 1e6).round(2)

    # Adjacency
    print("Computing adjacency...")
    sindex   = gdf.sindex
    ids      = list(gdf["district_id"])
    geoms    = list(gdf.geometry)
    adjacency = {id_: [] for id_ in ids}

    for i, (id_a, geom_a) in enumerate(tqdm(zip(ids, geoms), total=len(ids), desc="Adjacency")):
        for j in sindex.intersection(geom_a.bounds):
            if j <= i: continue
            id_b = ids[j]
            try:
                inter = geom_a.intersection(geoms[j])
                if not inter.is_empty and inter.length > 0.001:
                    adjacency[id_a].append(id_b)
                    adjacency[id_b].append(id_a)
            except Exception:
                pass

    # Save index for ML
    out = ROOT / "data/processed/district_index.json"
    out.parent.mkdir(exist_ok=True)
    id_to_idx = {id_: i for i, id_ in enumerate(ids)}
    rows, cols_e, weights = [], [], []
    for id_a, neighbors in adjacency.items():
        for id_b in neighbors:
            rows.append(id_to_idx[id_a])
            cols_e.append(id_to_idx[id_b])
            weights.append(1.0)
    with open(out, "w") as f:
        json.dump({"id_to_index": id_to_idx,
                   "index_to_id": {str(v): k for k, v in id_to_idx.items()},
                   "n_districts": len(ids),
                   "edges": {"rows": rows, "cols": cols_e, "weights": weights},
                   "metadata": {"n_edges": len(rows), "created": datetime.now().isoformat()}}, f)
    print(f"  Saved district_index.json — {len(ids)} nodes, {len(rows)} edges")

    # Upsert into DB
    print(f"Inserting {len(gdf)} districts into Supabase...")
    records = []
    for _, row in gdf.iterrows():
        records.append((
            row["district_id"],
            str(row["district_name"]).strip().title(),
            str(row["state_name"]).strip().title(),
            float(row["centroid_lat"]),
            float(row["centroid_lon"]),
            float(row["area_km2"]),
            adjacency.get(row["district_id"], []),
        ))

    psycopg2.extras.execute_batch(cur, """
        INSERT INTO districts (id, name, state, centroid_lat, centroid_lon, area_km2, adjacency_ids)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            name=EXCLUDED.name, state=EXCLUDED.state,
            centroid_lat=EXCLUDED.centroid_lat, centroid_lon=EXCLUDED.centroid_lon,
            area_km2=EXCLUDED.area_km2, adjacency_ids=EXCLUDED.adjacency_ids;
    """, records, page_size=100)

    cur.execute("SELECT COUNT(*) FROM districts;")
    count = cur.fetchone()[0]
    print(f"[OK] Districts in DB: {count}")
    return True

# ─── STEP 2: Load EpiClim ─────────────────────────────────────────────────────
DISEASE_MAP = {
    "dengue": "dengue", "dengue fever": "dengue",
    "suspected dengue": "dengue", "dengue and chikungunya": "dengue",
    "dengue and malaria": "dengue", "dengue/chikungunya": "dengue",
    "dengue chikungunya": "dengue", "suspected dengue and chikungunya": "dengue",
    "chikungunya/dengue": "dengue", "chikungunya/ dengue": "dengue",
    "malaria": "malaria", "malaria (pv)": "malaria", "malaria (pf)": "malaria",
    "cholera": "cholera", "suspected cholera": "cholera",
    "acute diarrhoeal disease": "acute_diarrhoeal_disease",
    "acute diarrheal disease": "acute_diarrhoeal_disease",
    "acute gastroenteritis": "acute_diarrhoeal_disease",
    "gastroenteritis": "acute_diarrhoeal_disease",
    "diarrhea": "acute_diarrhoeal_disease",
    "diarrhoea": "acute_diarrhoeal_disease",
}
TARGET_DISEASES = {"dengue", "malaria", "cholera", "acute_diarrhoeal_disease"}

def step2_epiclim(cur):
    print("\n" + "="*60)
    print("  STEP 2 — EpiClim Epidemiological Data")
    print("="*60)

    csv_path = ROOT / "data/raw/epiclim/Final_data.csv"
    if not csv_path.exists():
        csvs = list((ROOT / "data/raw/epiclim").glob("*.csv"))
        if not csvs: print("[ERR] No EpiClim CSV found"); return False
        csv_path = csvs[0]

    print(f"Loading {csv_path.name}...")
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()
    print(f"  {len(df)} rows, columns: {list(df.columns)}")

    # Normalize disease names
    df["disease"] = df["Disease"].str.strip().str.lower().map(DISEASE_MAP)
    df = df[df["disease"].isin(TARGET_DISEASES)].copy()
    print(f"  After disease filter: {len(df)} rows")

    # Get district lookup from DB
    cur.execute("SELECT id, name, state FROM districts;")
    db_districts = cur.fetchall()
    name_to_id = {row[1].lower().strip(): row[0] for row in db_districts}
    print(f"  {len(name_to_id)} districts loaded for fuzzy matching")

    # Fuzzy match district names
    candidates = list(name_to_id.keys())
    cache = {}
    def match_dist(raw_name: str):
        key = str(raw_name).strip().lower()
        key = re.sub(r"[^a-z\s]", "", key).strip()
        if key in cache: return cache[key]
        res = process.extractOne(key, candidates, scorer=fuzz.token_sort_ratio)
        val = name_to_id[res[0]] if res and res[1] >= 75 else None
        cache[key] = val
        return val

    tqdm.pandas(desc="Fuzzy matching districts")
    df["district_id"] = df["district"].progress_apply(match_dist)
    matched = df["district_id"].notna().sum()
    print(f"  Matched {matched}/{len(df)} rows ({100*matched/len(df):.1f}%)")

    # Build week dates
    def build_week(row):
        try:
            d = datetime(int(row["year"]), int(row["mon"]), min(int(row.get("day", 1)), 28))
            iso = d.isocalendar()
            week_str = f"{iso[0]}-W{iso[1]:02d}"
            week_start = d - timedelta(days=d.weekday())
            return week_str, str(week_start.date())
        except Exception:
            return None, None

    df[["iso_week", "week_start_date"]] = df.apply(build_week, axis=1, result_type="expand")
    df["cases"]  = pd.to_numeric(df["Cases"],  errors="coerce").fillna(0).astype(int)
    df["deaths"] = pd.to_numeric(df["Deaths"], errors="coerce").fillna(0).astype(int)

    df = df.dropna(subset=["district_id", "iso_week"])

    # Aggregate to weekly
    agg = df.groupby(["district_id", "disease", "iso_week", "week_start_date"]).agg(
        cases=("cases", "sum"), deaths=("deaths", "sum")
    ).reset_index()
    print(f"  {len(agg)} weekly records after aggregation")

    # Insert
    print(f"Inserting {len(agg)} records into epid_weekly...")
    records = [
        (row.district_id, row.disease, row.iso_week, row.week_start_date,
         int(row.cases), int(row.deaths), "epiclim_zenodo_14580510")
        for row in agg.itertuples()
    ]
    psycopg2.extras.execute_batch(cur, """
        INSERT INTO epid_weekly (district_id, disease, iso_week, week_start_date, cases, deaths, data_source)
        VALUES (%s, %s::disease_type, %s, %s, %s, %s, %s)
        ON CONFLICT (district_id, disease, iso_week) DO UPDATE SET
            cases=EXCLUDED.cases, deaths=EXCLUDED.deaths;
    """, records, page_size=200)

    cur.execute("SELECT disease, COUNT(*), SUM(cases) FROM epid_weekly GROUP BY disease;")
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]} weeks, {row[2]:,} cases")
    print("[OK] epid_weekly loaded")
    return True

# ─── STEP 3: Load Medicines ───────────────────────────────────────────────────
ICMR_DRUG_DISEASE_MAP = {
    "paracetamol":      ["dengue", "malaria", "acute_diarrhoeal_disease"],
    "acetaminophen":    ["dengue", "malaria"],
    "oral rehydration": ["cholera", "acute_diarrhoeal_disease", "dengue"],
    "ors":              ["cholera", "acute_diarrhoeal_disease", "dengue"],
    "ringer":           ["dengue", "cholera", "acute_diarrhoeal_disease", "malaria"],
    "normal saline":    ["dengue", "cholera", "malaria"],
    "sodium chloride":  ["dengue", "cholera", "malaria"],
    "zinc":             ["cholera", "acute_diarrhoeal_disease"],
    "chloroquine":      ["malaria"],
    "primaquine":       ["malaria"],
    "artemether":       ["malaria"],
    "lumefantrine":     ["malaria"],
    "artesunate":       ["malaria"],
    "artemisinin":      ["malaria"],
    "doxycycline":      ["cholera"],
    "azithromycin":     ["cholera"],
    "metronidazole":    ["acute_diarrhoeal_disease"],
    "cefixime":         ["acute_diarrhoeal_disease"],
    "dextrose":         ["malaria"],
}
FORMULATION_KEYWORDS = {
    "injection": "injection", "infusion": "iv_bag", "iv bag": "iv_bag",
    "vial": "vial", "ampoule": "vial", "sachet": "sachet",
    "capsule": "capsule", "tablet": "tablet", "strip": "tablet",
    "syrup": "oral_solution", "suspension": "oral_solution",
    "solution": "oral_solution", "liquid": "oral_solution",
    "powder": "powder", "cream": "topical", "ointment": "topical",
}

def step3_medicines(cur):
    print("\n" + "="*60)
    print("  STEP 3 — India Medicines Dataset")
    print("="*60)

    csv_path = ROOT / "data/raw/india_medicines/India Medicines and Drug Info Dataset.csv"
    if not csv_path.exists():
        csvs = list((ROOT / "data/raw/india_medicines").glob("*.csv"))
        if not csvs: print("[ERR] No medicines CSV found"); return False
        csv_path = csvs[0]

    print(f"Loading {csv_path.name} ({csv_path.stat().st_size // 1024 // 1024:.0f} MB)...")
    df = pd.read_csv(csv_path, low_memory=False)
    df.columns = df.columns.str.strip()
    print(f"  {len(df):,} rows")

    # Normalize to our standard column names
    df = df.rename(columns={
        "Medicine Name": "med_name",
        "Composition":   "composition_raw",
        "Price":         "price_raw",
        "Type of Medicine": "type_raw",
    })

    # Clean price
    df["price_inr"] = pd.to_numeric(
        df["price_raw"].astype(str).str.replace(r"[^\d.]", "", regex=True),
        errors="coerce"
    )

    # Determine ICMR relevance
    def get_diseases(name, comp):
        text = f"{name} {comp}".lower()
        diseases = set()
        for kw, dlist in ICMR_DRUG_DISEASE_MAP.items():
            if kw in text:
                diseases.update(dlist)
        return sorted(diseases)

    def get_formulation(name, type_raw):
        text = f"{name} {type_raw}".lower()
        for kw, ftype in FORMULATION_KEYWORDS.items():
            if kw in text:
                return ftype
        return "other"

    def extract_generic(comp):
        if not comp or pd.isna(comp): return None, None
        first = re.split(r"[+&,/]", str(comp))[0].strip()
        dose_m = re.search(r"(\d+(?:\.\d+)?)\s*(mg|mcg|g|iu|ml|%)", first, re.IGNORECASE)
        dose = float(dose_m.group(1)) if dose_m else None
        name_part = first[:dose_m.start()].strip() if dose_m else first
        generic = re.sub(r"[^a-zA-Z\s\-]", "", name_part).strip().lower()
        generic = re.sub(r"\s+", " ", generic).strip()
        return (generic or None), dose

    def extract_pack(text):
        m = re.search(r"(\d+)\s*(tablet|capsule|sachet|vial|ampoule|strip|piece)", str(text), re.IGNORECASE)
        return int(m.group(1)) if m else None

    print("  Filtering ICMR-relevant drugs...")
    tqdm.pandas(desc="Checking ICMR relevance")
    df["icmr_diseases"] = df.progress_apply(
        lambda r: get_diseases(str(r.get("med_name","")), str(r.get("composition_raw",""))), axis=1
    )
    df = df[df["icmr_diseases"].apply(len) > 0].copy()
    print(f"  After ICMR filter: {len(df):,} rows")

    print("  Extracting generics and doses...")
    tqdm.pandas(desc="Parsing composition")
    parsed = df["composition_raw"].progress_apply(extract_generic)
    df["generic_name"] = parsed.apply(lambda x: x[0])
    df["dose_mg"]      = parsed.apply(lambda x: x[1])
    df["formulation_type"] = df.apply(
        lambda r: get_formulation(str(r.get("med_name","")), str(r.get("type_raw",""))), axis=1
    )
    df["pack_size_units"] = df.apply(
        lambda r: extract_pack(str(r.get("type_raw","")) + " " + str(r.get("med_name",""))), axis=1
    )

    # Dedup: per (generic, dose, formulation) keep cheapest
    df = df.dropna(subset=["generic_name"])
    df_dedup = (
        df.sort_values("price_inr", na_position="last")
          .groupby(["generic_name", "dose_mg", "formulation_type"], dropna=False)
          .first()
          .reset_index()
    )
    print(f"  After dedup: {len(df_dedup)} unique drug SKUs")

    # Insert
    print(f"Inserting {len(df_dedup)} drugs...")
    records = []
    for _, row in df_dedup.iterrows():
        records.append((
            str(row.get("med_name", row.get("generic_name", "")))[:255],
            str(row["generic_name"])[:100],
            float(row["dose_mg"]) if pd.notna(row.get("dose_mg")) else None,
            str(row.get("formulation_type", "other"))[:50],
            int(row["pack_size_units"]) if pd.notna(row.get("pack_size_units")) else None,
            float(row["price_inr"]) if pd.notna(row.get("price_inr")) else None,
            row["icmr_diseases"],
            True,
        ))

    psycopg2.extras.execute_batch(cur, """
        INSERT INTO drugs (name, generic_name, dose_mg, formulation_type, pack_size_units, price_inr, icmr_diseases, is_active)
        VALUES (%s, %s, %s, %s::formulation_type, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING;
    """, records, page_size=100)

    cur.execute("SELECT COUNT(*) FROM drugs;")
    print(f"[OK] Drugs in DB: {cur.fetchone()[0]}")
    return True

# ─── STEP 4: Seed Hospitals + Inventory ──────────────────────────────────────
DEMO_HOSPITALS = [
    ("Rajiv Gandhi Government General Hospital", "Chennai",          "Tamil Nadu",     13.0827, 80.2707, "State",    2600),
    ("Government Stanley Medical College Hospital","Chennai",         "Tamil Nadu",     13.1061, 80.2850, "State",    1500),
    ("Government District Headquarters Hospital", "Coimbatore",      "Tamil Nadu",     11.0168, 76.9558, "District", 750),
    ("Erode Government District Hospital",        "Erode",           "Tamil Nadu",     11.3410, 77.7172, "District", 500),
    ("KEM Hospital Mumbai",                       "Mumbai",          "Maharashtra",    19.0007, 72.8337, "State",    1800),
    ("Pune District Hospital Sassoon",            "Pune",            "Maharashtra",    18.5158, 73.8569, "State",    1400),
    ("Nasik Civil Hospital",                      "Nashik",          "Maharashtra",    19.9975, 73.7898, "District", 600),
    ("Balrampur Hospital Lucknow",                "Lucknow",         "Uttar Pradesh",  26.8467, 80.9462, "State",    1200),
    ("Government District Combined Hospital",     "Varanasi",        "Uttar Pradesh",  25.3176, 82.9739, "District", 500),
    ("Government Medical College Gorakhpur",      "Gorakhpur",       "Uttar Pradesh",  26.7606, 83.3732, "District", 700),
    ("Government Medical College Thiruvananthapuram","Thiruvananthapuram","Kerala",     8.5241,  76.9366, "State",    1000),
    ("Kozhikode Government Medical College",      "Kozhikode",       "Kerala",         11.2588, 75.7804, "State",    1200),
    ("NRS Medical College and Hospital Kolkata",  "Kolkata",         "West Bengal",    22.5726, 88.3639, "State",    1500),
    ("Burdwan Medical College Hospital",          "Bardhaman",       "West Bengal",    23.2324, 87.8615, "State",    800),
    ("SMS Hospital Jaipur",                       "Jaipur",          "Rajasthan",      26.9124, 75.7873, "State",    2000),
    ("Udaipur Government Hospital",               "Udaipur",         "Rajasthan",      24.5854, 73.7125, "District", 600),
]

def step4_hospitals(cur):
    print("\n" + "="*60)
    print("  STEP 4 — Seed Hospitals + Inventory")
    print("="*60)

    # Load district name→id map from DB
    cur.execute("SELECT id, name, state FROM districts;")
    name_to_id = {row[1].lower().strip(): row[0] for row in cur.fetchall()}
    candidates = list(name_to_id.keys())

    hosp_ids = {}
    for (name, dist_name, state, lat, lon, tier, beds) in DEMO_HOSPITALS:
        key = dist_name.lower().strip()
        dist_id = name_to_id.get(key)
        if not dist_id:
            res = process.extractOne(key, candidates, scorer=fuzz.token_sort_ratio)
            dist_id = name_to_id[res[0]] if res and res[1] >= 75 else None
            if dist_id:
                print(f"  Fuzzy matched '{dist_name}' -> '{res[0]}'")
        if not dist_id:
            print(f"  [skip] Could not find district for: {dist_name}")
            continue

        cur.execute("""
            INSERT INTO hospitals (name, district_id, lat, lon, tier, bed_count)
            VALUES (%s, %s, %s, %s, %s::hospital_tier, %s)
            ON CONFLICT DO NOTHING RETURNING id;
        """, (name, dist_id, lat, lon, tier, beds))
        row = cur.fetchone()
        if row:
            hosp_ids[name] = str(row[0])
        else:
            # Already exists — get ID
            cur.execute("SELECT id FROM hospitals WHERE name=%s;", (name,))
            r = cur.fetchone()
            if r: hosp_ids[name] = str(r[0])

    cur.execute("SELECT COUNT(*) FROM hospitals;")
    print(f"[OK] Hospitals in DB: {cur.fetchone()[0]}")

    # Seed opening inventory
    print("Seeding inventory (hospital x drug)...")
    cur.execute("SELECT id FROM drugs WHERE is_active=true;")
    drug_ids = [str(r[0]) for r in cur.fetchall()]
    cur.execute("SELECT id, tier FROM hospitals;")
    hospitals_db = cur.fetchall()

    stock_by_tier = {"State": 1000, "District": 500, "CHC": 200, "PHC": 50}
    inv_records = []
    for (h_id, h_tier) in hospitals_db:
        base = stock_by_tier.get(str(h_tier), 200)
        for d_id in drug_ids:
            inv_records.append((str(h_id), d_id, base, max(10, base // 5)))

    psycopg2.extras.execute_batch(cur, """
        INSERT INTO inventory (hospital_id, drug_id, stock_units, reorder_point)
        VALUES (%s::uuid, %s::uuid, %s, %s)
        ON CONFLICT (hospital_id, drug_id) DO NOTHING;
    """, inv_records, page_size=500)

    cur.execute("SELECT COUNT(*) FROM inventory;")
    print(f"[OK] Inventory records: {cur.fetchone()[0]}")
    return True

# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Run Pharmasense Phase 0 data pipeline")
    p.add_argument("--db-password", "-p", required=True)
    p.add_argument("--steps", nargs="+", choices=["1","2","3","4","all"], default=["all"])
    args = p.parse_args()

    run_all = "all" in args.steps
    steps_to_run = set(args.steps) if not run_all else {"1","2","3","4"}

    print("\n" + "="*60)
    print("  Pharmasense Phase 0 — Full Data Pipeline")
    print("="*60)

    t0 = time.time()
    conn = get_conn(args.db_password)
    conn.autocommit = True
    cur = conn.cursor()
    print("[OK] Connected to Supabase PostgreSQL\n")

    results = {}
    if "1" in steps_to_run: results["GeoJSON"]    = step1_geojson(cur)
    if "2" in steps_to_run: results["EpiClim"]    = step2_epiclim(cur)
    if "3" in steps_to_run: results["Medicines"]  = step3_medicines(cur)
    if "4" in steps_to_run: results["Hospitals"]  = step4_hospitals(cur)

    conn.close()
    elapsed = time.time() - t0

    print("\n" + "="*60)
    print(f"  Pipeline complete in {elapsed:.0f}s")
    for step, ok in results.items():
        print(f"  {'[OK] ' if ok else '[ERR]'} {step}")
    print("="*60)

    sys.exit(0 if all(results.values()) else 1)
