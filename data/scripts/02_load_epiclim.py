"""
Phase 0 — Script 2: Load EpiClim Dataset into Supabase
Downloads EpiClim from Zenodo if not present, cleans + normalizes, fuzzy-joins
district names to districts table, loads into epid_weekly table.

Usage: python data/scripts/02_load_epiclim.py
Pre-req: Script 01 (districts table populated)
"""

import sys
import os
import re
import json
import time
import hashlib
import requests
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import pandas as pd
import numpy as np
from tqdm import tqdm
from rapidfuzz import process, fuzz
from supabase import create_client

# ─── Config ───────────────────────────────────────────────────────────────────
EPICLIM_PATH    = ROOT / "data/raw/epiclim"
PROCESSED_PATH  = ROOT / "data/processed"
ZENODO_DOI      = "10.5281/zenodo.14580510"
ZENODO_API      = "https://zenodo.org/api/records/14580510"
FUZZY_THRESHOLD = 80     # minimum match score for district name join (out of 100)
BATCH_SIZE      = 200    # rows per Supabase upsert

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# EpiClim disease name → our normalized name
DISEASE_MAP = {
    "dengue":                        "dengue",
    "malaria":                       "malaria",
    "cholera":                       "cholera",
    "acute diarrhoeal disease":      "acute_diarrhoeal_disease",
    "acute diarrheal disease":       "acute_diarrhoeal_disease",
    "acute diarrhoea":               "acute_diarrhoeal_disease",
    "add":                           "acute_diarrhoeal_disease",
    "aes":                           None,   # Acute Encephalitis Syndrome — not in our scope
    "leptospirosis":                 None,
    "typhoid":                       None,
    "viral hepatitis":               None,
    "scrub typhus":                  None,
}

TARGET_DISEASES = {"dengue", "malaria", "cholera", "acute_diarrhoeal_disease"}

# ─── Download EpiClim ─────────────────────────────────────────────────────────
def download_epiclim():
    EPICLIM_PATH.mkdir(parents=True, exist_ok=True)

    existing_csvs = list(EPICLIM_PATH.glob("*.csv"))
    if existing_csvs:
        print(f"✅ EpiClim files already present: {[f.name for f in existing_csvs]}")
        return existing_csvs[0]

    print(f"⬇️  Fetching EpiClim metadata from Zenodo API...")
    try:
        r = requests.get(ZENODO_API, timeout=30)
        r.raise_for_status()
        meta = r.json()
        files = meta.get("files", [])
        print(f"   Found {len(files)} file(s) in record:")
        for f in files:
            print(f"   - {f['key']} ({f['size'] / 1024:.0f} KB)")

        # Pick the CSV file
        csv_files = [f for f in files if f["key"].lower().endswith(".csv")]
        if not csv_files:
            print("   No CSV found — checking for zip...")
            csv_files = [f for f in files if f["key"].lower().endswith(".zip")]

        if not csv_files:
            print("❌ No downloadable CSV/zip in Zenodo record. Files available:", [f["key"] for f in files])
            _manual_download_instructions()
            sys.exit(1)

        target_file = csv_files[0]
        download_url = target_file["links"]["self"]
        fname = target_file["key"]
        out_path = EPICLIM_PATH / fname

        print(f"\n⬇️  Downloading {fname} ({target_file['size'] / 1024:.0f} KB)...")
        r2 = requests.get(download_url, stream=True, timeout=180)
        r2.raise_for_status()

        with open(out_path, "wb") as f:
            for chunk in r2.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"✅ Downloaded → {out_path}")
        return out_path

    except requests.RequestException as e:
        print(f"❌ Zenodo API request failed: {e}")
        _manual_download_instructions()
        sys.exit(1)

def _manual_download_instructions():
    print("\n📌 Manual download instructions:")
    print(f"   1. Go to: https://zenodo.org/records/14580510")
    print(f"   2. Download the CSV file")
    print(f"   3. Save to: {EPICLIM_PATH}/")

# ─── Load + clean EpiClim CSV ─────────────────────────────────────────────────
def load_and_clean_epiclim(csv_path: Path) -> pd.DataFrame:
    print(f"\n📂 Loading EpiClim from {csv_path.name}...")
    df = pd.read_csv(csv_path)
    print(f"   Raw shape: {df.shape}")
    print(f"   Columns: {list(df.columns)}")
    print(f"   Diseases: {df['Disease'].unique() if 'Disease' in df.columns else 'N/A'}")

    # Normalize column names
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

    # Rename columns to our standard names
    rename_map = {
        "state_ut": "state",
        "district": "district_raw",
        "disease": "disease_raw",
        "cases": "cases",
        "deaths": "deaths",
        "day": "day",
        "mon": "month",
        "year": "year",
        "latitude": "lat",
        "longitude": "lon",
        "preci": "rain_mm",
        "lai": "lai",
        "temp": "temp_kelvin",
        "week_of_outbreak": "week_label",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # Normalize disease names
    df["disease_raw_lower"] = df["disease_raw"].str.strip().str.lower()
    df["disease"] = df["disease_raw_lower"].map(DISEASE_MAP)

    # Filter to our target diseases
    before = len(df)
    df = df[df["disease"].isin(TARGET_DISEASES)].copy()
    print(f"   After disease filter: {len(df)} rows (removed {before - len(df)} non-target diseases)")

    # Clean numeric columns
    df["cases"]  = pd.to_numeric(df["cases"], errors="coerce").fillna(0).astype(int)
    df["deaths"] = pd.to_numeric(df["deaths"], errors="coerce").fillna(0).astype(int)

    # Convert temperature Kelvin → Celsius
    if "temp_kelvin" in df.columns:
        df["temp_celsius"] = (pd.to_numeric(df["temp_kelvin"], errors="coerce") - 273.15).round(2)
    else:
        df["temp_celsius"] = None

    # Build proper date from day/month/year
    def build_date(row):
        try:
            return datetime(int(row["year"]), int(row["month"]), min(int(row.get("day", 1)), 28))
        except Exception:
            return None

    df["record_date"] = df.apply(build_date, axis=1)
    df = df.dropna(subset=["record_date"])

    # Compute ISO week string: "2023-W24"
    df["iso_week"] = df["record_date"].apply(
        lambda d: f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"
    )
    df["week_start_date"] = df["record_date"].apply(
        lambda d: d - timedelta(days=d.weekday())  # Monday of that week
    )

    # Clean district names for fuzzy matching
    df["district_clean"] = (
        df["district_raw"]
        .str.strip()
        .str.lower()
        .str.replace(r"[^a-z\s]", "", regex=True)
        .str.replace(r"\s+", " ", regex=True)
    )
    df["state_clean"] = (
        df["state"]
        .str.strip()
        .str.lower()
        .str.replace(r"[^a-z\s]", "", regex=True)
    )

    print(f"   Final shape: {df.shape}")
    print(f"   Date range: {df['record_date'].min()} → {df['record_date'].max()}")
    print(f"\n   Disease counts:")
    for dis, count in df["disease"].value_counts().items():
        print(f"     {dis}: {count:,} records, {df[df['disease']==dis]['cases'].sum():,} cases")

    return df

# ─── Fuzzy join district names ────────────────────────────────────────────────
def build_district_name_lookup(client) -> dict[str, str]:
    """Fetch all districts from Supabase and build a name → id lookup."""
    print(f"\n🔎 Fetching district list from Supabase for fuzzy matching...")
    result = client.table("districts").select("id,name,state").execute()
    districts = result.data

    if not districts:
        print("❌ No districts in Supabase — run Script 01 first")
        sys.exit(1)

    print(f"   {len(districts)} districts loaded from Supabase")

    # Build normalized lookup: clean_name → id
    lookup = {}
    for d in districts:
        key = d["name"].lower().strip()
        key = re.sub(r"[^a-z\s]", "", key)
        key = re.sub(r"\s+", " ", key).strip()
        lookup[key] = d["id"]

    return lookup

def fuzzy_join_districts(df: pd.DataFrame, district_lookup: dict) -> pd.DataFrame:
    """Fuzzy-match each (state, district) pair to a census code ID."""
    print(f"\n🔗 Fuzzy-joining {df['district_clean'].nunique()} unique districts to census IDs...")

    candidates = list(district_lookup.keys())
    district_cache = {}   # cache for performance: clean_name → (census_code, score)
    unmatched = []

    def match_district(clean_name: str) -> str:
        if clean_name in district_cache:
            return district_cache[clean_name]

        result = process.extractOne(clean_name, candidates, scorer=fuzz.token_sort_ratio)
        if result and result[1] >= FUZZY_THRESHOLD:
            match_key, score, _ = result
            district_id = district_lookup[match_key]
            district_cache[clean_name] = district_id
            return district_id
        else:
            district_cache[clean_name] = None
            if clean_name not in unmatched:
                unmatched.append((clean_name, result[1] if result else 0))
            return None

    tqdm.pandas(desc="Matching districts")
    df["district_id"] = df["district_clean"].progress_apply(match_district)

    matched   = df["district_id"].notna().sum()
    unmatched_count = df["district_id"].isna().sum()
    print(f"   Matched:   {matched:,} rows ({100*matched/len(df):.1f}%)")
    print(f"   Unmatched: {unmatched_count:,} rows ({100*unmatched_count/len(df):.1f}%)")

    if unmatched:
        unmatched_sorted = sorted(unmatched, key=lambda x: x[1])
        print(f"\n   Worst matches (lowest score):")
        for name, score in unmatched_sorted[:15]:
            print(f"     '{name}' → no match (score={score})")

        # Save full unmatched list for review
        unmatched_path = ROOT / "data/processed/epiclim_unmatched_districts.txt"
        with open(unmatched_path, "w") as f:
            for name, score in sorted(unmatched, key=lambda x: -x[1]):
                f.write(f"{score:3.0f}  {name}\n")
        print(f"\n   Full unmatched list saved to: {unmatched_path}")

    # Drop unmatched rows
    df = df.dropna(subset=["district_id"])
    print(f"   Rows after dropping unmatched: {len(df):,}")

    return df

# ─── Aggregate to weekly + deduplicate ───────────────────────────────────────
def aggregate_to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """
    EpiClim may have multiple rows for same (district, disease, week).
    Aggregate by summing cases/deaths.
    """
    print(f"\n📊 Aggregating to weekly granularity...")
    before = len(df)

    agg = df.groupby(["district_id", "disease", "iso_week", "week_start_date"]).agg(
        cases=("cases", "sum"),
        deaths=("deaths", "sum"),
    ).reset_index()

    print(f"   {before:,} rows → {len(agg):,} weekly aggregates")
    return agg

# ─── Upload to Supabase ───────────────────────────────────────────────────────
def upload_epid_weekly(df: pd.DataFrame, client):
    print(f"\n📤 Uploading {len(df):,} weekly records to Supabase epid_weekly...")

    records = []
    for _, row in df.iterrows():
        records.append({
            "district_id":     row["district_id"],
            "disease":         row["disease"],
            "iso_week":        row["iso_week"],
            "week_start_date": str(row["week_start_date"].date()),
            "cases":           int(row["cases"]),
            "deaths":          int(row["deaths"]),
            "data_source":     "epiclim_zenodo_14580510",
        })

    success = 0
    for i in tqdm(range(0, len(records), BATCH_SIZE), desc="Uploading"):
        batch = records[i:i + BATCH_SIZE]
        try:
            client.table("epid_weekly").upsert(
                batch,
                on_conflict="district_id,disease,iso_week"
            ).execute()
            success += len(batch)
        except Exception as e:
            print(f"\n   ❌ Batch {i//BATCH_SIZE} failed: {str(e)[:100]}")
            time.sleep(2)
            try:
                client.table("epid_weekly").upsert(
                    batch,
                    on_conflict="district_id,disease,iso_week"
                ).execute()
                success += len(batch)
            except Exception as e2:
                print(f"   ❌ Retry failed: {str(e2)[:100]}")

    print(f"\n✅ Uploaded {success:,}/{len(records):,} rows to epid_weekly")

# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*60)
    print("  Script 02 — Load EpiClim Epidemiological Data")
    print("="*60)

    # Find or download CSV
    existing = list(EPICLIM_PATH.glob("*.csv")) if EPICLIM_PATH.exists() else []
    if existing:
        csv_path = existing[0]
        print(f"✅ Using existing file: {csv_path.name}")
    else:
        csv_path = download_epiclim()

    df = load_and_clean_epiclim(csv_path)

    if SUPABASE_URL and SUPABASE_KEY:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        district_lookup = build_district_name_lookup(client)
        df = fuzzy_join_districts(df, district_lookup)
        df = aggregate_to_weekly(df)
        upload_epid_weekly(df, client)
    else:
        print("\n⚠️  Supabase credentials not set — saving processed CSV locally only")
        df_out = df[["district_clean", "disease", "iso_week", "week_start_date", "cases", "deaths"]].copy()
        out = ROOT / "data/processed/epiclim_processed.csv"
        df_out.to_csv(out, index=False)
        print(f"   Saved to {out}")

    print("\n✅ Script 02 complete.")
