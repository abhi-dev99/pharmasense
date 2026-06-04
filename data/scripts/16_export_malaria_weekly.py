"""
Pharmasense — Generate malaria_weekly.csv
=========================================
Disaggregates annual district malaria cases into weekly time series
using India's documented monsoon-driven malaria seasonality pattern.

Seasonality source:
  NVBDCP Weekly Epidemiological Data; Dhiman RC et al. (2011) Malaria
  transmission forecast by NOAA-AVHRR-based vegetation index.
  Peak: Weeks 34-40 (late Aug to early Oct, post-monsoon).
  Trough: Weeks 8-14 (Feb-Mar, dry winter).

Output: ml/data/malaria_weekly.csv
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import date, timedelta

ROOT  = Path(__file__).parent.parent.parent
SRC   = ROOT / 'ml' / 'data' / 'malaria_2010_2024.csv'
DEST  = ROOT / 'ml' / 'data' / 'malaria_weekly.csv'

np.random.seed(42)

# ── Seasonal weights (52 values, week 1-52) ─────────────────────────────────
# Cosine curve: peak at week 37 (mid-Sep), trough at week 11 (mid-Mar)
# Source: matches NVBDCP weekly incidence patterns reported in annual bulletins
WEEKS = np.arange(1, 53)
RAW_WEIGHTS = 1.0 + 0.80 * np.cos(2 * np.pi * (WEEKS - 37) / 52)
# Clip to avoid negative values in near-zero-malaria districts
SEASON_WEIGHTS = np.maximum(0.05, RAW_WEIGHTS)
# Normalize so they sum to 52 (preserves annual total when multiplied by annual/52)
SEASON_WEIGHTS = SEASON_WEIGHTS / SEASON_WEIGHTS.sum() * 52

def week_start(year, week):
    """ISO week to Monday date."""
    d = date.fromisocalendar(year, week, 1)
    return d

print("=" * 60)
print("  Pharmasense - Malaria Annual to Weekly Disaggregation")
print("=" * 60)

df = pd.read_csv(SRC)
print(f"\nLoaded: {len(df):,} rows | Years: {sorted(df.year.unique())}")

records = []
for _, row in df.iterrows():
    year    = int(row['year'])
    annual  = int(row.get('annual_cases', 0))
    state   = row.get('state', '')
    district = row.get('district', '')
    pf_cases = int(row.get('pf_cases', 0))
    pv_cases = int(row.get('pv_cases', 0))
    source  = row.get('data_source', 'nvbdcp')

    if annual <= 0:
        continue

    # Distribute annual total across 52 weeks using seasonal weights
    # Add small Gaussian noise (±4%) to avoid perfectly smooth series
    noise = np.random.normal(1.0, 0.04, 52).clip(0.88, 1.14)
    raw_weekly = SEASON_WEIGHTS * noise
    # Normalize so sum = annual_cases exactly
    raw_weekly = raw_weekly / raw_weekly.sum() * annual
    weekly_cases = np.round(raw_weekly).astype(int)
    # Correct rounding error on week 1 so total stays exact
    diff = annual - weekly_cases.sum()
    weekly_cases[0] += diff

    pf_frac = pf_cases / annual if annual > 0 else 0.5
    pv_frac = 1.0 - pf_frac

    for w_idx, cases in enumerate(weekly_cases):
        week_num = w_idx + 1
        try:
            wdate = week_start(year, week_num)
        except ValueError:
            continue  # week 53 doesn't exist in all years
        records.append({
            'week_start_date': wdate.isoformat(),
            'year': year,
            'iso_week': week_num,
            'state': state,
            'district': district,
            'disease': 'malaria',
            'cases': int(max(0, cases)),
            'pf_cases': int(max(0, round(cases * pf_frac))),
            'pv_cases': int(max(0, round(cases * pv_frac))),
            'data_source': source,
        })

out = pd.DataFrame(records)
out['week_start_date'] = pd.to_datetime(out['week_start_date'])
out = out.sort_values(['state', 'district', 'week_start_date']).reset_index(drop=True)

out.to_csv(DEST, index=False)

print(f"\nOutput: {DEST}")
print(f"Rows:   {len(out):,}")
print(f"Years:  {sorted(out.year.unique())}")
print(f"Districts: {out.district.nunique():,}")
print(f"Total cases: {out.cases.sum():,}")
print(f"\nAnnual totals (spot check):")
for yr in [2010, 2017, 2018, 2019, 2024]:
    s = out[out.year == yr].cases.sum()
    tag = ' [API-derived]' if yr in [2017, 2018] else ''
    print(f"  {yr}: {s:>10,}{tag}")
print("\nDone.")
