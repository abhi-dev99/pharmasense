"""
Pharmasense — Generate ncd_demand_weekly.csv
============================================
Generates weekly demand estimates for all 11 conditions (4 core NCDs +
7 symptomatic conditions) using MBQ (Morbidity-Based Quantification).

Uses census district populations directly — no DB required.
Same methodology as 06_seed_ncd_pipeline.py + 08_seed_symptomatic_pipeline.py
but outputs a CSV instead of writing to Supabase.

Output: ml/data/ncd_demand_weekly.csv
"""

import pandas as pd
import numpy as np
import math
from pathlib import Path
from datetime import date, timedelta

ROOT   = Path(__file__).parent.parent.parent
CENSUS = ROOT / 'data' / 'raw' / 'census_pca' / 'census_2011_pca.xlsx'
DEST   = ROOT / 'ml' / 'data' / 'ncd_demand_weekly.csv'

np.random.seed(99)

print("=" * 60)
print("  Pharmasense — NCD/Symptomatic Weekly CSV Export")
print("=" * 60)

# ── Load district populations from Census 2011 ───────────────────────────────
census = pd.read_excel(CENSUS)
districts = census[(census['Level'] == 'DISTRICT') & (census['TRU'] == 'Total')].copy()
districts = districts[['Name', 'State', 'TOT_P']].rename(
    columns={'Name': 'district', 'State': 'state_code', 'TOT_P': 'pop_2011'}
)
# Adjust to ~2021 mid-point using 1.28% CAGR
districts['population'] = (districts['pop_2011'] * (1.0128 ** 10)).astype(int)
# Placeholder state names using state code (state column in census is numeric)
# Use district name + code as unique key
districts['district_key'] = districts['district'].str.lower().str.strip()
print(f"\nLoaded {len(districts)} districts from Census 2011")

# State code to name mapping (Census 2011 state codes)
STATE_CODE_MAP = {
    1:'Jammu and Kashmir', 2:'Himachal Pradesh', 3:'Punjab', 4:'Chandigarh',
    5:'Uttarakhand', 6:'Haryana', 7:'Delhi', 8:'Rajasthan', 9:'Uttar Pradesh',
    10:'Bihar', 11:'Sikkim', 12:'Arunachal Pradesh', 13:'Nagaland', 14:'Manipur',
    15:'Mizoram', 16:'Tripura', 17:'Meghalaya', 18:'Assam', 19:'West Bengal',
    20:'Jharkhand', 21:'Odisha', 22:'Chhattisgarh', 23:'Madhya Pradesh',
    24:'Gujarat', 25:'Daman and Diu', 26:'Dadra and Nagar Haveli', 27:'Maharashtra',
    28:'Andhra Pradesh', 29:'Karnataka', 30:'Goa', 31:'Lakshadweep', 32:'Kerala',
    33:'Tamil Nadu', 34:'Puducherry', 35:'Andaman and Nicobar Islands',
}
districts['state'] = districts['state_code'].map(STATE_CODE_MAP).fillna('Other')

# ── Prevalence/incidence rates (NFHS-5, GBD 2019, NSSO 75th Round) ──────────
NSSO_OPD = 1.644  # annual OPD episodes per person (NSSO 75th Round)

CONDITIONS = {
    # ── Core NCDs (NFHS-5 prevalence-based) ─────────────────────────────────
    'hypertension': {
        'type': 'prevalence',
        'rate': 0.281,          # 28.1% of adults ≥18 (NFHS-5 2019-21, Table 13)
        'adult_fraction': 0.63, # fraction of pop ≥18 (Census 2011)
        'treatment_coverage': 0.55,  # 55% of HTN patients on medication (NFHS-5)
        'seasonal_peak_month': None,  # no seasonality
    },
    'type2_diabetes': {
        'type': 'prevalence',
        'rate': 0.073,          # 7.3% of adults (ICMR INDIAB 2023)
        'adult_fraction': 0.63,
        'treatment_coverage': 0.60,
        'seasonal_peak_month': None,
    },
    'tuberculosis': {
        'type': 'incidence',
        'rate': 0.000211,       # 211 per 100,000 (India TB Report 2022)
        'adult_fraction': 1.0,  # all ages
        'treatment_coverage': 1.0,  # all notified cases on treatment
        'seasonal_peak_month': None,
    },
    'anaemia': {
        'type': 'prevalence',
        'rate': 0.571,          # 57.1% of women 15-49 (NFHS-5); use 35% overall
        'adult_fraction': 0.35, # rough weighted average (women + children)
        'treatment_coverage': 0.45,
        'seasonal_peak_month': None,
    },
    # ── Symptomatic / Acute (NSSO OPD-share based) ───────────────────────────
    'viral_fever_urti': {
        'type': 'opd_share',
        'share': 0.228,
        'seasonal_amplitude': 0.25,
        'seasonal_peak_month': 8,   # August (monsoon peak)
        'secondary_peak_month': 12, # December (winter)
    },
    'acute_gastritis_dyspepsia': {
        'type': 'opd_share',
        'share': 0.082,
        'seasonal_amplitude': 0.10,
        'seasonal_peak_month': 5,
        'secondary_peak_month': None,
    },
    'musculoskeletal_pain': {
        'type': 'opd_share',
        'share': 0.071,
        'seasonal_amplitude': 0.18,
        'seasonal_peak_month': 1,   # January (winter arthritis)
        'secondary_peak_month': None,
    },
    'asthma_copd_respiratory': {
        'type': 'prevalence',
        'rate': 0.0313,
        'adult_fraction': 1.0,
        'treatment_coverage': 0.50,
        'seasonal_amplitude': 0.30,
        'seasonal_peak_month': 12,
        'secondary_peak_month': None,
    },
    'helminth_infestation': {
        'type': 'ndp',           # National Deworming Programme — biannual pulse
        'child_fraction': 0.37,
        'ndp_coverage': 0.76,
        'ndp_rounds': 2,
        'ndd_weeks': {5, 6, 7, 30, 31, 32},
    },
    'uti_bacterial_infections': {
        'type': 'incidence',
        'rate': 0.050,
        'adult_fraction': 1.0,
        'treatment_coverage': 0.70,
        'seasonal_amplitude': 0.15,
        'seasonal_peak_month': 6,
        'secondary_peak_month': None,
    },
    'maternal_anc_supplements': {
        'type': 'birth_rate',
        'cbr': 0.0197,          # SRS 2020
        'gestation_fraction': 40/52,
        'anc_coverage': 0.85,
    },
}

STATE_OPD_MULT = {
    'Kerala': 1.52, 'Tamil Nadu': 1.28, 'Karnataka': 1.14,
    'Andhra Pradesh': 1.09, 'Telangana': 1.07, 'Goa': 1.19,
    'Maharashtra': 1.08, 'Gujarat': 0.98, 'Delhi': 1.31,
    'Chandigarh': 1.24, 'Punjab': 1.18, 'Haryana': 1.05,
    'Himachal Pradesh': 1.12, 'Rajasthan': 0.82,
    'Madhya Pradesh': 0.76, 'Uttar Pradesh': 0.71,
    'Bihar': 0.69, 'Jharkhand': 0.73, 'Odisha': 0.88,
    'West Bengal': 1.02, 'Assam': 0.91, 'Chhattisgarh': 0.80,
}

def seasonal_mult(cond_cfg, week_date):
    month = week_date.month
    week  = week_date.isocalendar()[1]

    if cond_cfg.get('type') == 'ndp':
        return 5.0 if week in cond_cfg['ndd_weeks'] else 0.20

    amp  = cond_cfg.get('seasonal_amplitude', 0.0)
    peak = cond_cfg.get('seasonal_peak_month')
    sec  = cond_cfg.get('secondary_peak_month')

    if peak is None:
        return 1.0

    m1 = amp * math.cos(2 * math.pi * (month - peak) / 12)
    m2 = (amp * 0.7) * math.cos(2 * math.pi * (month - sec) / 12) if sec else 0.0
    return max(0.50, min(1.60, 1.0 + m1 + m2))

def trend_mult(wdate, base_year=2018):
    years = (wdate.year - base_year) + wdate.month / 12
    return 1.02 ** years  # 2% annual growth in OPD utilization

# ── Generate all weeks 2018-W01 to 2024-W52 ──────────────────────────────────
weeks = []
d = date(2018, 1, 1)
while d <= date(2024, 12, 31):
    iso = d.isocalendar()
    weeks.append((d, iso[1]))
    d += timedelta(weeks=1)

print(f"Weeks: {len(weeks)} | Conditions: {len(CONDITIONS)} | Districts: {len(districts)}")
est_rows = len(weeks) * len(CONDITIONS) * len(districts)
print(f"Estimated rows: {est_rows:,}")

records = []
BATCH_PRINT = 500_000

for _, dist_row in districts.iterrows():
    pop   = max(1000, int(dist_row['population']))
    state = dist_row['state']
    dist  = dist_row['district']
    util  = STATE_OPD_MULT.get(state, 1.0)

    for cond_name, cfg in CONDITIONS.items():
        ctype = cfg['type']

        # ── Base patients per week ────────────────────────────────────────────
        if ctype == 'prevalence':
            base = (pop * cfg['rate'] * cfg['adult_fraction']
                    * cfg['treatment_coverage'] / 52.0)
        elif ctype == 'incidence':
            base = (pop * cfg['rate'] * cfg.get('adult_fraction', 1.0)
                    * cfg.get('treatment_coverage', 1.0) / 52.0)
        elif ctype == 'opd_share':
            base = pop * NSSO_OPD * cfg['share'] * util / 52.0
        elif ctype == 'ndp':
            base = (pop * cfg['child_fraction'] * cfg['ndp_coverage']
                    * cfg['ndp_rounds'] / 52.0)
        elif ctype == 'birth_rate':
            base = (pop * cfg['cbr'] * cfg['gestation_fraction']
                    * cfg['anc_coverage'])
        else:
            continue

        for (wdate, wnum) in weeks:
            sm    = seasonal_mult(cfg, wdate)
            tm    = trend_mult(wdate)
            noise = np.clip(np.random.normal(1.0, 0.05), 0.85, 1.18)
            pts   = max(0, int(base * sm * tm * noise))

            records.append({
                'week_start_date': wdate.isoformat(),
                'iso_week': f"{wdate.year}-W{wnum:02d}",
                'state': state,
                'district': dist,
                'condition': cond_name,
                'patients_est': pts,
            })

    if len(records) >= BATCH_PRINT:
        print(f"  Generated {len(records):,} rows so far...")

out = pd.DataFrame(records)
out['week_start_date'] = pd.to_datetime(out['week_start_date'])
out = out.sort_values(['condition', 'state', 'district', 'week_start_date']).reset_index(drop=True)
out.to_csv(DEST, index=False)

print(f"\nOutput: {DEST}")
print(f"Total rows: {len(out):,}")
size_mb = DEST.stat().st_size / 1e6
print(f"File size: {size_mb:.1f} MB")
print("\nPatients per condition (weekly avg across all districts):")
summary = out.groupby('condition')['patients_est'].mean().sort_values(ascending=False)
for cond, avg in summary.items():
    print(f"  {cond:<35} {avg:>10,.0f}")
print("\nDone.")
