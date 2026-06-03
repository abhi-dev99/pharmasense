"""
Pharmasense — Population Fix Script
=====================================
Replaces area-weighted district population estimates with real Census 2011 PCA data.

REQUIRES USER TO DOWNLOAD:
  Census 2011 Primary Census Abstract (District-level)
  URL: https://censusindia.gov.in/nada/index.php/catalog/42613
  Download: "Primary Census Abstract Total" Excel file
  Save as: data/raw/census_pca/census_2011_pca.xlsx

Why this matters:
  Current estimates: state_pop_2011 × (district_area / state_total_area)
  This assumes uniform density within a state — wrong for states like UP or Maharashtra
  (Mumbai district: 12,442 km² but ~3.1M pop vs Maharashtra average much lower density).

  Real Census PCA gives exact district-level totals.
  This directly improves every NCD demand calculation (demand = pop × prevalence × coverage / 52).

Usage:
  python data/scripts/07_fix_populations.py --db-password pharmasons99lite
  (only run AFTER downloading census_2011_pca.xlsx)
"""

import sys, os, argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
import psycopg2, psycopg2.extras

# ─── State population growth rates (2011→2021 projected, % per year) ─────────
# Source: Registrar General, India — Sample Registration System Statistical Report 2020
# Used to project 2011 Census populations forward to the 2018-2024 demand period
# Formula: pop_year = pop_2011 × (1 + rate)^(year - 2011)
STATE_ANNUAL_GROWTH_RATE = {
    "Andhra Pradesh":          0.011,
    "Telangana":               0.014,
    "Arunachal Pradesh":       0.023,
    "Assam":                   0.016,
    "Bihar":                   0.022,
    "Chhattisgarh":            0.019,
    "Goa":                     0.007,
    "Gujarat":                 0.016,
    "Haryana":                 0.016,
    "Himachal Pradesh":        0.009,
    "Jammu & Kashmir":         0.015,
    "Jharkhand":               0.018,
    "Karnataka":               0.015,
    "Kerala":                  0.005,
    "Madhya Pradesh":          0.020,
    "Maharashtra":             0.014,
    "Manipur":                 0.012,
    "Meghalaya":               0.020,
    "Mizoram":                 0.016,
    "Nagaland":                0.006,
    "Odisha":                  0.012,
    "Punjab":                  0.010,
    "Rajasthan":               0.020,
    "Sikkim":                  0.013,
    "Tamil Nadu":              0.008,
    "Tripura":                 0.011,
    "Uttar Pradesh":           0.020,
    "Uttarakhand":             0.016,
    "West Bengal":             0.011,
    "Delhi":                   0.022,
    "Chandigarh":              0.017,
    "Andaman & Nicobar Islands": 0.012,
    "Dadra & Nagar Haveli":    0.055,
    "Daman & Diu":             0.035,
    "Lakshadweep":             0.008,
    "Puducherry":              0.007,
    "_default":                0.015,
}


def get_conn(password):
    url = os.getenv("SUPABASE_URL", "")
    ref = url.replace("https://","").split(".")[0]
    return psycopg2.connect(
        host=f"db.{ref}.supabase.co", port=5432, dbname="postgres",
        user="postgres", password=password, sslmode="require", connect_timeout=20,
    )


def load_census_pca(excel_path: Path) -> dict:
    """
    Parse Census 2011 PCA Excel into {district_id: population} mapping.

    Confirmed column structure (inspected 2026-06-04):
      col 0: State       (state census code, integer)
      col 1: District    (district census code, integer; 0 = state-level row)
      col 6: Level       ('India', 'STATE', 'DISTRICT')
      col 7: Name        (district/state name)
      col 10: TOT_P     (total population)

    District ID format matches our DB: '{State:02d}_{District:03d}'
    Each district has 3 rows: Total / Rural / Urban — we take the first (Total).
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("pandas required: pip install pandas openpyxl")

    print(f"Loading Census PCA from: {excel_path}")
    df = pd.read_excel(excel_path, header=0)

    # Filter to DISTRICT-level, Total rows only (first of each State+District group)
    districts = df[df['Level'] == 'DISTRICT'].copy()
    districts = districts.groupby(['State', 'District']).first().reset_index()

    pop_map = {}
    missing = []
    for _, row in districts.iterrows():
        try:
            st_code = int(row['State'])
            dt_code = int(row['District'])
            pop     = int(row['TOT_P'])
            if st_code == 0 or dt_code == 0:
                continue
            dist_id = f"{st_code:02d}_{dt_code:03d}"
            pop_map[dist_id] = pop
        except (ValueError, TypeError, KeyError) as e:
            missing.append(str(e))
            continue

    print(f"Census PCA loaded: {len(pop_map)} districts")
    if missing:
        print(f"  Skipped rows: {len(missing)}")
    return pop_map


def update_populations(cur, pop_map: dict, target_year: int = 2021):
    """Update district populations in DB, projected to target_year."""

    # Get current district states for growth rate lookup
    cur.execute("SELECT id, state FROM districts;")
    districts = {row[0]: row[1] for row in cur.fetchall()}

    updated, fallback = 0, 0
    records = []
    for dist_id, state in districts.items():
        if dist_id in pop_map:
            pop_2011 = pop_map[dist_id]
            rate = STATE_ANNUAL_GROWTH_RATE.get(state, STATE_ANNUAL_GROWTH_RATE["_default"])
            pop_projected = int(pop_2011 * ((1 + rate) ** (target_year - 2011)))
            records.append((pop_projected, dist_id))
            updated += 1
        else:
            fallback += 1

    if records:
        psycopg2.extras.execute_batch(
            cur, "UPDATE districts SET population = %s WHERE id = %s;",
            records, page_size=500,
        )

    print(f"[OK] Updated: {updated} districts with Census PCA data")
    print(f"     Fallback (area-weighted): {fallback} districts (no PCA match)")
    print(f"     Coverage: {updated/(updated+fallback)*100:.1f}%")

    # Also update ncd_demand_weekly proportionally
    # NCD demand scales linearly with population
    print("\n[...] Recalculating NCD demand based on updated populations...")
    cur.execute("""
        UPDATE ncd_demand_weekly n
        SET patients_est = ROUND(n.patients_est * (d.population::float / NULLIF(n.district_pop, 0))),
            demand_units = ROUND(n.demand_units * (d.population::float / NULLIF(n.district_pop, 0))),
            district_pop = d.population
        FROM districts d
        WHERE n.district_id = d.id
          AND d.population IS NOT NULL
          AND n.district_pop > 0
          AND n.district_pop != d.population;
    """)
    print(f"[OK] NCD demand recalculated for updated districts")


def verify(cur):
    cur.execute("SELECT COUNT(*) FROM districts WHERE population IS NOT NULL;")
    print(f"\nDistricts with population: {cur.fetchone()[0]}")
    cur.execute("SELECT MIN(population), MAX(population), AVG(population)::int FROM districts WHERE population IS NOT NULL;")
    r = cur.fetchone()
    print(f"Population range: {r[0]:,} – {r[1]:,} | Average: {r[2]:,}")
    cur.execute("SELECT SUM(population) FROM districts;")
    print(f"Total population in DB: {cur.fetchone()[0]:,}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--db-password", "-p", required=True)
    p.add_argument("--excel-path", "-e",
                   default=str(ROOT / "data/raw/census_pca/census_2011_pca.xlsx"))
    p.add_argument("--target-year", "-y", type=int, default=2021)
    args = p.parse_args()

    excel_path = Path(args.excel_path)
    if not excel_path.exists():
        print(f"\n{'='*65}")
        print("Census PCA file not found. Please download it first:")
        print("URL: https://censusindia.gov.in/nada/index.php/catalog/42613")
        print("Download: 'Primary Census Abstract Total' Excel")
        print(f"Save as: {excel_path}")
        print("Then re-run this script.")
        print(f"{'='*65}\n")
        sys.exit(1)

    pop_map = load_census_pca(excel_path)
    if not pop_map:
        print("Could not parse PCA file. Check column names in the Excel.")
        sys.exit(1)

    conn = get_conn(args.db_password)
    conn.autocommit = True
    cur = conn.cursor()
    print(f"[OK] Connected. Updating populations (projected to {args.target_year})...")

    update_populations(cur, pop_map, args.target_year)
    verify(cur)
    conn.close()
    print("\n[DONE] Population data updated. Re-run NCD pipeline if needed.")
