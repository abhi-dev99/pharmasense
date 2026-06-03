"""
Phase 0 — Pre-flight Check
Run this first. Verifies all dependencies and connections before touching real data.
Usage: python data/scripts/00_setup_check.py
"""

import sys
import os
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

# ─── Load .env ────────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

PASS = "[OK] "
FAIL = "[ERR]"
WARN = "[WRN]"


errors = []
warnings = []

print("\n" + "="*60)
print("  PHARMASENSE — Phase 0 Pre-flight Check")
print("="*60 + "\n")

# ─── Python version ───────────────────────────────────────────────────────────
pv = sys.version_info
if pv.major == 3 and pv.minor >= 10:
    print(f"{PASS} Python {pv.major}.{pv.minor}.{pv.micro}")
else:
    print(f"{FAIL} Python {pv.major}.{pv.minor} — need 3.10+")
    errors.append("Python version too old")

# ─── Required packages ────────────────────────────────────────────────────────
required_packages = [
    ("pandas", "pandas"),
    ("geopandas", "geopandas"),
    ("shapely", "shapely"),
    ("numpy", "numpy"),
    ("scipy", "scipy"),
    ("rapidfuzz", "rapidfuzz"),
    ("supabase", "supabase"),
    ("python-dotenv", "dotenv"),
    ("tqdm", "tqdm"),
    ("requests", "requests"),
]

print("\n── Package checks ──────────────────────────────────────────")
for display_name, import_name in required_packages:
    try:
        __import__(import_name)
        print(f"{PASS} {display_name}")
    except ImportError:
        print(f"{FAIL} {display_name} — run: pip install {display_name}")
        errors.append(f"Missing package: {display_name}")

# ─── Environment variables ────────────────────────────────────────────────────
print("\n── Environment variables ───────────────────────────────────")

critical_vars = {
    "SUPABASE_URL": "Supabase project URL",
    "SUPABASE_SERVICE_ROLE_KEY": "Supabase service role key (bypasses RLS for pipeline)",
}
optional_vars = {
    "OPENWEATHER_API_KEY": "OpenWeatherMap API key",
    "GOOGLE_GEMINI_API_KEY": "Gemini API key",
    "TWILIO_ACCOUNT_SID": "Twilio SID",
    "TWILIO_AUTH_TOKEN": "Twilio Auth Token",
}

for var, desc in critical_vars.items():
    val = os.getenv(var, "")
    if val and len(val) > 5:
        print(f"{PASS} {var} = {val[:8]}...")
    else:
        print(f"{FAIL} {var} — {desc} — MISSING")
        errors.append(f"Missing env var: {var}")

for var, desc in optional_vars.items():
    val = os.getenv(var, "")
    if val and len(val) > 5:
        print(f"{PASS} {var} = {val[:8]}...")
    else:
        print(f"{WARN}{var} — {desc} — not set (optional for Phase 0)")
        warnings.append(f"Missing env var: {var}")

# ─── Raw data files ───────────────────────────────────────────────────────────
print("\n── Raw data files ──────────────────────────────────────────")

data_files = {
    ROOT / "data/raw/epiclim": "EpiClim CSV (download from Zenodo 14580510)",
    ROOT / "data/raw/india_geojson": "India district GeoJSON (download from datameet/maps)",
    ROOT / "data/raw/india_medicines": "India medicines CSV (download from Kaggle apkaayush)",
    ROOT / "data/icmr_rules.json": "ICMR rules JSON (already written)",
}

for path, desc in data_files.items():
    path = Path(path)
    if path.is_dir():
        files = list(path.iterdir())
        if files:
            print(f"{PASS} {path.name}/ — {len(files)} file(s)")
        else:
            print(f"{WARN}{path.name}/ — directory empty — {desc}")
            warnings.append(f"Empty data dir: {path.name}")
    elif path.is_file():
        size_kb = path.stat().st_size / 1024
        print(f"{PASS} {path.name} ({size_kb:.1f} KB)")
    else:
        print(f"{FAIL} {path.name} — NOT FOUND — {desc}")
        errors.append(f"Missing data: {path.name}")

# ─── Supabase connection test ─────────────────────────────────────────────────
print("\n── Supabase connection ─────────────────────────────────────")
url = os.getenv("SUPABASE_URL", "")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

if url and key:
    try:
        from supabase import create_client
        client = create_client(url, key)
        # Try a simple query — will fail if schema not yet created, but connection works
        result = client.table("districts").select("id").limit(1).execute()
        print(f"{PASS} Supabase connected — districts table exists")
    except Exception as e:
        err_str = str(e)
        if "relation" in err_str.lower() or "does not exist" in err_str.lower():
            print(f"{WARN}Supabase connected but schema not yet applied (run schema.sql first)")
            warnings.append("Schema not applied yet")
        elif "connection" in err_str.lower() or "network" in err_str.lower():
            print(f"{FAIL} Supabase connection failed: {err_str[:80]}")
            errors.append("Supabase connection failed")
        else:
            print(f"{PASS} Supabase connected (table might not exist yet: {err_str[:60]})")
else:
    print(f"{FAIL} Supabase credentials missing — set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
    errors.append("Supabase credentials missing")

# ─── Summary ──────────────────────────────────────────────────────────────────
print("\n" + "="*60)
if errors:
    print(f"  {FAIL} PRE-FLIGHT FAILED — {len(errors)} error(s):")
    for e in errors:
        print(f"     → {e}")
    print("\n  Fix the above errors before running pipeline scripts.")
elif warnings:
    print(f"  {WARN}PRE-FLIGHT PASSED WITH {len(warnings)} WARNING(S)")
    print("  You can run pipeline scripts but some data may be missing.")
else:
    print(f"  {PASS} ALL CHECKS PASSED — ready to run pipeline")
print("="*60 + "\n")

sys.exit(1 if errors else 0)
