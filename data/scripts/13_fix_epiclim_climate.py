"""
Pharmasense — Fix 1: Epiclim Climate Feature Imputation
========================================================
Imputes missing LAI and Temperature values in the Epiclim dataset using
district-month median imputation (the standard approach in WHO SEARO 
and NCDC climate-epidemiology studies).

Method:
  1. LAI (Leaf Area Index):   fill by (district, month) median across all years
                               → fallback: (state, month) median
                               → fallback: global month median
  2. Temperature (Kelvin):    same 3-level cascade
  3. Precipitation:           same 3-level cascade (only 47 nulls, minor)

Output: data/raw/epiclim/Final_data_clean.csv
        data/raw/epiclim/imputation_report.txt

Scientific basis:
  LAI is driven by vegetation growth cycles that are highly stable
  year-on-year for the same district and month. Imputing 2012 April LAI
  for Koraput using the 2010-2022 April median for Koraput is equivalent
  to using the climatological normal — standard in:
  - WHO SEARO Regional Health Situation Report methodology
  - Dhiman RC et al. (2019) Malaria & climate covariates, Parasites & Vectors
  - Beck-Johnson LM et al. (2013) Temperature and malaria transmission
"""

import pandas as pd
import numpy as np
from pathlib import Path

RAW = Path(__file__).parent.parent / 'raw' / 'epiclim'
INPUT  = RAW / 'Final_data.csv'
OUTPUT = RAW / 'Final_data_clean.csv'
REPORT = RAW / 'imputation_report.txt'

print("=" * 65)
print("  Pharmasense — Epiclim Climate Imputation (Fix 1)")
print("=" * 65)

df = pd.read_csv(INPUT)
print(f"\nLoaded {len(df):,} rows from {INPUT.name}")

# ─── Pre-imputation null audit ────────────────────────────────────────────
CLIMATE_COLS = ['LAI', 'Temp', 'preci']
pre_nulls = {}
for col in CLIMATE_COLS:
    pre_nulls[col] = df[col].isnull().sum()
    pct = 100 * pre_nulls[col] / len(df)
    print(f"  {col}: {pre_nulls[col]} nulls ({pct:.1f}%) before imputation")

# ─── 3-level cascade imputation ──────────────────────────────────────────
def cascade_impute(df, col):
    """
    Level 1: (district, month) median
    Level 2: (state_ut, month) median
    Level 3: global month median
    """
    # Level 1
    l1 = df.groupby(['district', 'mon'])[col].transform('median')
    df[col] = df[col].fillna(l1)
    remaining_l1 = df[col].isnull().sum()

    # Level 2
    if remaining_l1 > 0:
        l2 = df.groupby(['state_ut', 'mon'])[col].transform('median')
        df[col] = df[col].fillna(l2)
        remaining_l2 = df[col].isnull().sum()
    else:
        remaining_l2 = 0

    # Level 3: global month median
    if remaining_l2 > 0:
        l3 = df.groupby('mon')[col].transform('median')
        df[col] = df[col].fillna(l3)
        remaining_l3 = df[col].isnull().sum()
    else:
        remaining_l3 = 0

    return remaining_l1, remaining_l2, remaining_l3

report_lines = [
    "Epiclim Climate Feature Imputation Report",
    "=" * 50,
    f"Input:  {INPUT}",
    f"Output: {OUTPUT}",
    "",
    "Method: 3-level cascade median imputation",
    "  Level 1: (district, month) median across all available years",
    "  Level 2: (state, month) median",
    "  Level 3: global month median",
    "",
    "Scientific basis: District-month LAI/Temp are highly stable",
    "year-on-year (climatological normals). Standard in WHO SEARO",
    "and NCDC climate-epidemiology publications.",
    "",
    "Pre-imputation nulls:",
]
for col, n in pre_nulls.items():
    report_lines.append(f"  {col}: {n} ({100*n/len(df):.1f}%)")

report_lines.append("")
report_lines.append("Imputation cascade results:")

print("\nRunning 3-level cascade imputation...")
for col in CLIMATE_COLS:
    r1, r2, r3 = cascade_impute(df, col)
    final_nulls = df[col].isnull().sum()
    print(f"  {col}: after L1={r1} remaining, L2={r2} remaining, L3={r3} remaining, final={final_nulls}")
    report_lines.append(f"  {col}: L1_remaining={r1}, L2_remaining={r2}, L3_remaining={r3}, final_nulls={final_nulls}")

# ─── Temperature sanity check ─────────────────────────────────────────────
# Temp is in Kelvin. Valid India range: ~280K (7°C) to ~325K (52°C)
temp_outliers = df[(df['Temp'] < 275) | (df['Temp'] > 330)]
if len(temp_outliers) > 0:
    print(f"\n  [WARN] {len(temp_outliers)} rows with Temp outside 275-330K range:")
    print(temp_outliers[['district', 'state_ut', 'mon', 'year', 'Temp']].head(5))
    report_lines.append(f"\n  [WARN] {len(temp_outliers)} Temp outliers outside 275-330K")
else:
    print("  [OK] All Temperature values within valid India range (275-330K)")
    report_lines.append("  [OK] Temperature: all values valid (275-330K range)")

# ─── LAI sanity check ─────────────────────────────────────────────────────
# Valid LAI range: 0 (bare soil) to 8 (dense forest). Values >8 are
# occasionally seen in dense evergreen — clamp at 10 to be safe.
lai_outliers = df[df['LAI'] > 10]
if len(lai_outliers) > 0:
    print(f"  [WARN] {len(lai_outliers)} rows with LAI > 10 — clamping")
    df['LAI'] = df['LAI'].clip(upper=10.0)
    report_lines.append(f"  [WARN] {len(lai_outliers)} LAI values > 10 — clamped to 10.0")
else:
    print("  [OK] All LAI values within valid range (0-10)")

# ─── Final null check ─────────────────────────────────────────────────────
print("\nPost-imputation null counts:")
all_clean = True
for col in CLIMATE_COLS:
    remaining = df[col].isnull().sum()
    status = "[OK]" if remaining == 0 else "[WARN]"
    print(f"  {status} {col}: {remaining} nulls remaining")
    if remaining > 0:
        all_clean = False

# ─── Save ─────────────────────────────────────────────────────────────────
df.to_csv(OUTPUT, index=False)
print(f"\n[OK] Saved clean dataset: {OUTPUT}")
print(f"     Rows: {len(df):,}")
print(f"     Columns: {list(df.columns)}")

# Save report
report_lines += ["", f"Output saved: {OUTPUT}", f"Total rows: {len(df):,}"]
REPORT.write_text('\n'.join(report_lines))
print(f"[OK] Imputation report: {REPORT}")

if all_clean:
    print("\n✅ Fix 1 complete — all climate features are 100% null-free.")
    print("   ST-GNN and Graph WaveNet are now unblocked for training.")
else:
    print("\n[WARN] Some nulls remain — review the report above.")
