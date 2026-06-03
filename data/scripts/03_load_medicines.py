"""
Phase 0 — Script 3: Load India Medicines Dataset into Supabase
Downloads from Kaggle (or uses local file), filters to ICMR-relevant drugs,
deduplicates, and seeds the drugs table.

Usage: python data/scripts/03_load_medicines.py
Pre-req: Script 01 complete (Supabase connection working)

If you have Kaggle API: pip install kaggle, set up ~/.kaggle/kaggle.json
If not: manually download from kaggle.com/datasets/apkaayush/india-medicines-and-drug-info-dataset
        and save to data/raw/india_medicines/
"""

import sys
import os
import re
import json
import time
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import pandas as pd
import numpy as np
from tqdm import tqdm
from supabase import create_client

MEDICINES_PATH = ROOT / "data/raw/india_medicines"
SUPABASE_URL   = os.getenv("SUPABASE_URL")
SUPABASE_KEY   = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
BATCH_SIZE     = 100

# ─── Drug → disease mapping (ICMR relevance filter) ────────────────────────────
# Maps generic name keywords → which diseases use this drug
ICMR_DRUG_DISEASE_MAP = {
    "paracetamol":               ["dengue", "malaria", "acute_diarrhoeal_disease"],
    "acetaminophen":             ["dengue", "malaria"],
    "ors":                       ["cholera", "acute_diarrhoeal_disease", "dengue"],
    "oral rehydration":          ["cholera", "acute_diarrhoeal_disease", "dengue"],
    "ringer":                    ["dengue", "cholera", "acute_diarrhoeal_disease", "malaria"],
    "ringer lactate":            ["dengue", "cholera", "acute_diarrhoeal_disease", "malaria"],
    "normal saline":             ["dengue", "cholera", "malaria"],
    "sodium chloride":           ["dengue", "cholera", "malaria"],
    "zinc":                      ["cholera", "acute_diarrhoeal_disease"],
    "chloroquine":               ["malaria"],
    "primaquine":                ["malaria"],
    "artemether":                ["malaria"],
    "lumefantrine":              ["malaria"],
    "artesunate":                ["malaria"],
    "artemisinin":               ["malaria"],
    "coartem":                   ["malaria"],
    "doxycycline":               ["cholera"],
    "azithromycin":              ["cholera"],
    "metronidazole":             ["acute_diarrhoeal_disease"],
    "cefixime":                  ["acute_diarrhoeal_disease"],
    "dextrose":                  ["malaria"],
    "iv fluid":                  ["dengue", "cholera", "malaria"],
}

# Formulation type standardization
FORMULATION_MAP = {
    "tablet":              "tablet",
    "tablets":             "tablet",
    "capsule":             "capsule",
    "capsules":            "capsule",
    "syrup":               "oral_solution",
    "suspension":          "oral_solution",
    "solution":            "oral_solution",
    "liquid":              "oral_solution",
    "injection":           "injection",
    "infusion":            "iv_bag",
    "sachet":              "sachet",
    "sachets":             "sachet",
    "powder":              "powder",
    "cream":               "topical",
    "ointment":            "topical",
    "drops":               "drops",
    "inhaler":             "inhaler",
    "patch":               "patch",
    "strip":               "tablet",   # "strip of 10 tablets" → tablet
    "vial":                "vial",
    "ampoule":             "vial",
    "ampule":              "vial",
}

# ─── Download via Kaggle CLI ───────────────────────────────────────────────────
def try_kaggle_download():
    MEDICINES_PATH.mkdir(parents=True, exist_ok=True)
    existing = list(MEDICINES_PATH.glob("*.csv"))
    if existing:
        print(f"✅ Medicine files already present: {[f.name for f in existing]}")
        return True

    print("⬇️  Attempting Kaggle download...")
    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"

    if not kaggle_json.exists():
        print("⚠️  ~/.kaggle/kaggle.json not found — Kaggle CLI not configured")
        print("   Manual download instructions:")
        print("   1. Go to: https://www.kaggle.com/datasets/apkaayush/india-medicines-and-drug-info-dataset")
        print("   2. Download the dataset")
        print(f"  3. Extract CSV(s) to: {MEDICINES_PATH}/")
        return False

    try:
        result = subprocess.run([
            "kaggle", "datasets", "download",
            "apkaayush/india-medicines-and-drug-info-dataset",
            "-p", str(MEDICINES_PATH), "--unzip"
        ], capture_output=True, text=True, timeout=120)

        if result.returncode == 0:
            print(f"✅ Kaggle download successful")
            return True
        else:
            print(f"❌ Kaggle download failed: {result.stderr[:200]}")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"❌ Kaggle CLI error: {e}")
        return False

# ─── Load medicines CSV ────────────────────────────────────────────────────────
def load_medicines_csv() -> pd.DataFrame:
    csv_files = list(MEDICINES_PATH.glob("*.csv"))
    if not csv_files:
        print(f"❌ No CSV files in {MEDICINES_PATH}")
        print("   Download manually: https://www.kaggle.com/datasets/apkaayush/india-medicines-and-drug-info-dataset")
        sys.exit(1)

    # Merge all CSV files (dataset may have multiple files)
    dfs = []
    for f in csv_files:
        print(f"   Loading {f.name}...")
        try:
            df = pd.read_csv(f, encoding="utf-8", low_memory=False)
            dfs.append(df)
            print(f"     {len(df):,} rows, columns: {list(df.columns[:8])}...")
        except Exception as e:
            print(f"   ⚠️  Could not load {f.name}: {e}")

    if not dfs:
        sys.exit(1)

    combined = pd.concat(dfs, ignore_index=True)
    print(f"\n   Combined shape: {combined.shape}")
    return combined

# ─── Clean + normalize ─────────────────────────────────────────────────────────
def clean_medicines(df: pd.DataFrame) -> pd.DataFrame:
    print(f"\n🧹 Cleaning medicines dataset...")

    # Normalize column names
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_").str.replace(r"[^a-z0-9_]", "", regex=True)
    print(f"   Columns: {list(df.columns)}")

    # Handle different column name variants
    col_map = {
        "name": "med_name",
        "medicine_name": "med_name",
        "price": "price_inr",
        "mrp": "price_inr",
        "is_discontinued": "is_discontinued",
        "discontinued": "is_discontinued",
        "manufacturer_name": "manufacturer",
        "type": "med_type",
        "pack_size_label": "pack_label",
        "short_composition1": "composition1",
        "short_composition2": "composition2",
        "sub_category": "subcategory",
        "id": "source_id",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    # Filter out discontinued
    if "is_discontinued" in df.columns:
        before = len(df)
        df["is_discontinued"] = df["is_discontinued"].astype(str).str.lower().isin(
            ["true", "1", "yes", "discontinued"]
        )
        df = df[~df["is_discontinued"]].copy()
        print(f"   After removing discontinued: {len(df):,} rows (removed {before - len(df):,})")

    # Ensure we have composition column
    comp_col = "composition1" if "composition1" in df.columns else None
    if not comp_col:
        # Try to find any composition-like column
        comp_cols = [c for c in df.columns if "compos" in c or "ingredient" in c or "active" in c]
        comp_col = comp_cols[0] if comp_cols else None

    if not comp_col:
        print("⚠️  No composition column found — will use medicine name for generic extraction")
        df["composition1"] = df.get("med_name", "")

    df["composition_raw"] = df[comp_col].fillna("").astype(str)

    return df

# ─── Extract generic name + dose ─────────────────────────────────────────────
def extract_generic_info(composition: str) -> dict:
    """
    Parses composition like 'Paracetamol 500mg' → {generic: 'paracetamol', dose_mg: 500.0}
    Handles multi-ingredient like 'Artemether 80mg + Lumefantrine 480mg'
    """
    if not composition or pd.isna(composition):
        return {"generic_name": None, "dose_mg": None}

    composition = str(composition).strip()

    # Take first ingredient if combination drug
    first_part = re.split(r"[+&,/]", composition)[0].strip()

    # Extract dose
    dose_match = re.search(r"(\d+(?:\.\d+)?)\s*(mg|mcg|g|iu|ml|%)", first_part, re.IGNORECASE)
    dose_mg = float(dose_match.group(1)) if dose_match else None

    # Extract name (everything before the dose number)
    if dose_match:
        name_part = first_part[:dose_match.start()].strip()
    else:
        name_part = first_part

    generic_name = re.sub(r"[^a-zA-Z\s\-]", "", name_part).strip().lower()
    generic_name = re.sub(r"\s+", " ", generic_name).strip()

    return {"generic_name": generic_name if generic_name else None, "dose_mg": dose_mg}

# ─── Determine formulation type ───────────────────────────────────────────────
def extract_formulation(med_type: str, pack_label: str) -> str:
    text = f"{med_type} {pack_label}".lower()
    for keyword, ftype in FORMULATION_MAP.items():
        if keyword in text:
            return ftype
    return "other"

# ─── Determine ICMR relevance ─────────────────────────────────────────────────
def get_icmr_diseases(generic_name: str, composition: str) -> list[str]:
    """Returns list of diseases this drug is used for per ICMR guidelines."""
    if not generic_name:
        return []
    combined = f"{generic_name} {composition}".lower()
    diseases = set()
    for keyword, disease_list in ICMR_DRUG_DISEASE_MAP.items():
        if keyword in combined:
            diseases.update(disease_list)
    return sorted(list(diseases))

# ─── Extract pack size ────────────────────────────────────────────────────────
def extract_pack_size(pack_label: str) -> int | None:
    if not pack_label or pd.isna(pack_label):
        return None
    match = re.search(r"(\d+)\s*(tablet|capsule|sachet|vial|ampoule|strip|piece)", str(pack_label), re.IGNORECASE)
    return int(match.group(1)) if match else None

# ─── Filter and deduplicate ───────────────────────────────────────────────────
def filter_and_dedup(df: pd.DataFrame) -> pd.DataFrame:
    print(f"\n🔬 Applying ICMR relevance filter and deduplication...")

    # Extract info
    print("   Extracting generic names and doses...")
    tqdm.pandas(desc="Parsing composition")
    parsed = df["composition_raw"].progress_apply(extract_generic_info)
    df["generic_name"] = parsed.apply(lambda x: x["generic_name"])
    df["dose_mg"]      = parsed.apply(lambda x: x["dose_mg"])

    df["formulation_type"] = df.apply(
        lambda r: extract_formulation(
            str(r.get("med_type", "")),
            str(r.get("pack_label", ""))
        ), axis=1
    )

    df["pack_size_units"] = df.get("pack_label", pd.Series(dtype=str)).apply(extract_pack_size)

    df["icmr_diseases"] = df.apply(
        lambda r: get_icmr_diseases(r["generic_name"], r["composition_raw"]), axis=1
    )

    # Filter: only ICMR-relevant drugs
    before = len(df)
    df = df[df["icmr_diseases"].apply(len) > 0].copy()
    print(f"   After ICMR filter: {len(df):,} rows (removed {before - len(df):,})")

    # Price cleanup
    price_col = "price_inr" if "price_inr" in df.columns else None
    if price_col:
        df["price_inr"] = pd.to_numeric(df[price_col], errors="coerce")
    else:
        df["price_inr"] = None

    # Deduplicate: per (generic_name, dose_mg, formulation_type) → keep cheapest
    print("   Deduplicating by (generic, dose, formulation) — keeping cheapest...")
    dedup_key = ["generic_name", "dose_mg", "formulation_type"]
    df_dedup = (
        df.dropna(subset=["generic_name"])
          .sort_values("price_inr", na_position="last")
          .groupby(dedup_key, dropna=False)
          .first()
          .reset_index()
    )
    print(f"   After dedup: {len(df_dedup)} unique drug SKUs")

    # Show summary
    print(f"\n   ICMR-relevant drugs by disease:")
    disease_counts = {}
    for diseases in df_dedup["icmr_diseases"]:
        for d in diseases:
            disease_counts[d] = disease_counts.get(d, 0) + 1
    for d, c in sorted(disease_counts.items()):
        print(f"     {d}: {c} SKUs")

    return df_dedup

# ─── Upload to Supabase ───────────────────────────────────────────────────────
def upload_drugs(df: pd.DataFrame, client):
    print(f"\n📤 Uploading {len(df)} drugs to Supabase...")

    records = []
    for _, row in df.iterrows():
        records.append({
            "name":             str(row.get("med_name", row.get("generic_name", "")))[:255],
            "generic_name":     str(row["generic_name"])[:100],
            "dose_mg":          float(row["dose_mg"]) if pd.notna(row.get("dose_mg")) else None,
            "formulation_type": str(row.get("formulation_type", "other"))[:50],
            "pack_size_units":  int(row["pack_size_units"]) if pd.notna(row.get("pack_size_units")) else None,
            "price_inr":        float(row["price_inr"]) if pd.notna(row.get("price_inr")) else None,
            "manufacturer_name": str(row.get("manufacturer", ""))[:255] if pd.notna(row.get("manufacturer")) else None,
            "icmr_diseases":    row["icmr_diseases"],
            "is_active":        True,
            "external_1mg_id":  int(row["source_id"]) if pd.notna(row.get("source_id")) else None,
        })

    success = 0
    for i in tqdm(range(0, len(records), BATCH_SIZE), desc="Uploading"):
        batch = records[i:i + BATCH_SIZE]
        try:
            client.table("drugs").insert(batch).execute()
            success += len(batch)
        except Exception as e:
            print(f"\n   ⚠️  Batch {i//BATCH_SIZE} insert failed, retrying as upsert: {str(e)[:80]}")
            time.sleep(1)
            try:
                # Try one by one on failure
                for rec in batch:
                    try:
                        client.table("drugs").insert(rec).execute()
                        success += 1
                    except Exception:
                        pass
            except Exception:
                pass

    print(f"\n✅ Uploaded {success}/{len(records)} drug SKUs to Supabase")

# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*60)
    print("  Script 03 — Load India Medicines Dataset")
    print("="*60)

    downloaded = try_kaggle_download()
    if not downloaded and not list(MEDICINES_PATH.glob("*.csv")):
        print("\n❌ No medicine data available. Please download manually.")
        print("   URL: https://www.kaggle.com/datasets/apkaayush/india-medicines-and-drug-info-dataset")
        sys.exit(1)

    df_raw = load_medicines_csv()
    df_clean = clean_medicines(df_raw)
    df_final = filter_and_dedup(df_clean)

    # Save locally regardless
    out_path = ROOT / "data/processed/icmr_drugs.csv"
    df_final.to_csv(out_path, index=False)
    print(f"\n💾 Saved processed drugs to {out_path}")

    if SUPABASE_URL and SUPABASE_KEY:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        upload_drugs(df_final, client)
    else:
        print("\n⚠️  Supabase credentials not set — saved CSV only")

    print("\n✅ Script 03 complete.")
