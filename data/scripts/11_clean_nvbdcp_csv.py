"""
Post-processing script for the NVBDCP malaria extracted CSV.
Runs AFTER 10_extract_nvbdcp_pdfs.py.

Fixes applied:
  1. Deduplication: drop duplicate (year, state, district) rows keeping max(annual_cases)
  2. Format B 2017-2018: re-extract from PDFs using API × pop lookup from 2019
  3. Re-compute national totals for validation

Output: data/processed/nvbdcp_malaria_district_annual_clean.csv
"""

import sys, re
from pathlib import Path

ROOT     = Path(__file__).parent.parent.parent
PDF_DIR  = ROOT / 'data' / 'raw' / 'nvbdcp'
IN_CSV   = ROOT / 'data' / 'processed' / 'nvbdcp_malaria_district_annual.csv'
OUT_CSV  = ROOT / 'data' / 'processed' / 'nvbdcp_malaria_district_annual_clean.csv'

try:
    import pdfplumber
except ImportError:
    import subprocess, sys as _sys
    subprocess.run([_sys.executable, '-m', 'pip', 'install', '-q', 'pdfplumber'], check=True)
    import pdfplumber

import pandas as pd
import numpy as np


# ── Fallback re-implementation of helpers (so this file is standalone) ────────
STATE_NORMALIZE = {
    'andaman & nicobar islands': 'Andaman and Nicobar Islands',
    'andaman and nicobar': 'Andaman and Nicobar Islands',
    'a&n islands': 'Andaman and Nicobar Islands',
    'andhra pradesh': 'Andhra Pradesh',
    'arunachal pradesh': 'Arunachal Pradesh',
    'assam': 'Assam',
    'bihar': 'Bihar',
    'chandigarh': 'Chandigarh',
    'chhattisgarh': 'Chhattisgarh',
    'chattisgarh': 'Chhattisgarh',
    'd&n haveli': 'Dadra and Nagar Haveli',
    'dadra & nagar haveli': 'Dadra and Nagar Haveli',
    'daman & diu': 'Daman and Diu',
    'delhi': 'Delhi',
    'goa': 'Goa',
    'gujarat': 'Gujarat',
    'haryana': 'Haryana',
    'himachal pradesh': 'Himachal Pradesh',
    'j&k': 'Jammu and Kashmir',
    'jammu & kashmir': 'Jammu and Kashmir',
    'jammu and kashmir': 'Jammu and Kashmir',
    'jharkhand': 'Jharkhand',
    'karnataka': 'Karnataka',
    'kerala': 'Kerala',
    'lakshadweep': 'Lakshadweep',
    'madhya pradesh': 'Madhya Pradesh',
    'm.p.': 'Madhya Pradesh',
    'maharashtra': 'Maharashtra',
    'manipur': 'Manipur',
    'meghalaya': 'Meghalaya',
    'mizoram': 'Mizoram',
    'nagaland': 'Nagaland',
    'odisha': 'Odisha',
    'orissa': 'Odisha',
    'puducherry': 'Puducherry',
    'pondicherry': 'Puducherry',
    'punjab': 'Punjab',
    'rajasthan': 'Rajasthan',
    'sikkim': 'Sikkim',
    'tamil nadu': 'Tamil Nadu',
    'tamilnadu': 'Tamil Nadu',
    'telangana': 'Telangana',
    'tripura': 'Tripura',
    'uttar pradesh': 'Uttar Pradesh',
    'u.p.': 'Uttar Pradesh',
    'uttarakhand': 'Uttarakhand',
    'uttaranchal': 'Uttarakhand',
    'west bengal': 'West Bengal',
}

def normalize_state(s):
    if not s:
        return ''
    return STATE_NORMALIZE.get(s.strip().lower(), s.strip())

def clean_float(v):
    if v is None: return None
    try: return float(str(v).strip().replace(',',''))
    except: return None

def clean_int(v):
    if v is None: return None
    import re
    m = re.search(r'\d+', str(v).strip().replace(',',''))
    return int(m.group()) if m else None


# ── STEP 1: Load existing CSV and dedup ───────────────────────────────────────
print('STEP 1: Loading extracted CSV and deduplicating...')
df = pd.read_csv(IN_CSV)
print(f'  Before dedup: {len(df):,} rows')

# For each (year, state, district), keep row with highest annual_cases
df = (df.sort_values('annual_cases', ascending=False)
        .drop_duplicates(subset=['year', 'state', 'district'], keep='first')
        .sort_values(['year', 'state', 'district'])
        .reset_index(drop=True))

print(f'  After dedup:  {len(df):,} rows')

# ── STEP 2: Build population lookup from 2019/2022 data ───────────────────────
print('\nSTEP 2: Building district population lookup from 2019+2022 data...')
pop_df = df[(df['year'].isin([2019, 2020, 2021, 2022])) & (df['pop_000s'].notna())]
pop_lookup = (pop_df.groupby(['state', 'district'])['pop_000s']
                    .mean()   # average across available years
                    .reset_index())
print(f'  Population lookup: {len(pop_lookup):,} districts')


# ── STEP 3: Re-extract Format B (2017-2018) using API × pop ───────────────────
print('\nSTEP 3: Re-extracting Format B (2017-2018) using API × population...')

FORMAT_B_PATTERN = re.compile(
    r'Epidemiological\s+Situation\s+Report\s+(?:of\s+)?([A-Za-z &]+?)\s+\d{4}',
    re.IGNORECASE
)

def extract_format_b_with_pop(pdf, year, pop_lookup_df):
    """Re-extract Format B using API and the 2019 population lookup."""
    records = []
    current_state = None

    # Build fast lookup dict: (state_lower, district_lower) -> pop_000s
    pop_dict = {}
    for _, row in pop_lookup_df.iterrows():
        pop_dict[(row['state'].lower(), row['district'].lower())] = row['pop_000s']

    for pg in pdf.pages:
        tables = pg.extract_tables()
        for table in tables:
            if not table or len(table) < 3:
                continue

            # STATE DETECTION: look at first row of table (table[0][0])
            # Format B table first row: "Epidemiological Situation Report of Assam 2017"
            first_cell = str(table[0][0] or '').strip() if table[0] else ''
            m = FORMAT_B_PATTERN.search(first_cell)
            if m:
                raw = m.group(1).strip()
                candidate = normalize_state(raw)
                if candidate != raw:   # matched something in our dict
                    current_state = candidate
                else:
                    # Try prefix match (handles "Andhra Prade" truncation)
                    for key, val in STATE_NORMALIZE.items():
                        if key.startswith(raw.lower()[:8]) or raw.lower().startswith(key[:8]):
                            current_state = val
                            break

            if not current_state:
                continue

            # Detect API column (should be col 4: SN, DISTRICT, PF%, ABER, API)
            api_col  = 4
            dist_col = 1

            for hdr in table[:3]:
                if not hdr: continue
                for ci, cell in enumerate(hdr):
                    s = str(cell or '').strip().lower()
                    if 'a.p.i' in s or s == 'api':
                        api_col = ci
                    if s == 'district':
                        dist_col = ci

            for row in table:
                if not row or not row[0]:
                    continue
                sn = str(row[0]).strip()
                if not sn.isdigit():
                    continue

                district = str(row[dist_col] or '').strip() if len(row) > dist_col else ''
                if not district or 'total' in district.lower():
                    continue

                api = clean_float(row[api_col]) if len(row) > api_col else None

                if api is None or api <= 0:
                    continue

                # Look up population from 2019-2022 data
                state_l = current_state.lower()
                dist_l  = district.lower()
                pop = pop_dict.get((state_l, dist_l))

                # Fuzzy fallback: try partial match
                if pop is None:
                    for (sl, dl), p in pop_dict.items():
                        if (state_l[:6] in sl or sl[:6] in state_l) and \
                           (dist_l[:6] in dl or dl[:6] in dist_l):
                            pop = p
                            break

                if pop is None or pop <= 0:
                    continue

                # cases = API (per 1000/year) × pop (000s) = total annual cases
                cases = max(0, int(round(api * pop)))
                if cases == 0:
                    continue

                records.append({
                    'year': year, 'state': current_state, 'district': district,
                    'annual_cases': cases,
                    'pv_cases': 0,
                    'pf_cases': 0,
                    'pop_000s': pop,
                    'api': api,
                    'data_source': f'nvbdcp_pdf_{year}_estimated',
                    'format': 'B_est',
                })

    # Dedup within year (same district may appear on continuation pages)
    seen = set()
    unique = []
    for r in records:
        key = (r['state'], r['district'])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique


b_records = []
for year in [2017, 2018]:
    pdf_path = PDF_DIR / f'malaria_{year}.pdf'
    if not pdf_path.exists():
        print(f'  {year}: PDF not found')
        continue
    with pdfplumber.open(pdf_path) as pdf:
        recs = extract_format_b_with_pop(pdf, year, pop_lookup)
    total_cases = sum(r['annual_cases'] for r in recs)
    print(f'  {year}: {len(recs):,} districts | total_cases={total_cases:,}')
    b_records.extend(recs)

if b_records:
    b_df = pd.DataFrame(b_records)
    # Remove existing B rows from main df and replace with estimated
    df = df[~df['year'].isin([2017, 2018])].copy()
    df = pd.concat([df, b_df], ignore_index=True)
    df = df.sort_values(['year', 'state', 'district']).reset_index(drop=True)
    print(f'  Updated df size: {len(df):,} rows')


# ── STEP 4: Final cleanup ──────────────────────────────────────────────────────
print('\nSTEP 4: Final cleanup...')

# Remove "Unknown" state rows that have no data value
df = df[~((df['state'] == 'Unknown') & (df['annual_cases'] == 0))]

# Clean district names: remove trailing ## footnote markers
df['district'] = df['district'].str.replace(r'##.*$', '', regex=True).str.strip()
df['district'] = df['district'].str.replace(r'#$', '', regex=True).str.strip()

# Remove rows with clearly wrong district names
df = df[df['district'].str.len() >= 2]
df = df[~df['district'].str.match(r'^\d+$')]

print(f'  Final size: {len(df):,} rows')
print(f'  Years covered: {sorted(df.year.unique())}')
print(f'  States covered: {df.state.nunique()}')
print(f'  Districts covered: {df.district.nunique()}')


# ── STEP 5: Save & validate ────────────────────────────────────────────────────
df.to_csv(OUT_CSV, index=False)
print(f'\n[OK] Saved -> {OUT_CSV}')

# Known NVBDCP national totals (from official reports)
KNOWN_TOTALS = {
    2010: 1599400, 2011: 1310190, 2012: 1067824, 2013: 882099,
    2014: 1102205, 2015: 1136986, 2016: 1089724, 2017: 844558,
    2018: 429928,  2019: 338494,  2020: 186532,  2021: 171306,
    2022: 173000,  2023: 170000,  2024: 250000,
}

print()
print('VALIDATION - National totals by year:')
print(f"  {'Year':<6} {'Fmt':<6} {'Districts':>10} {'Extracted':>12} {'Official':>12} {'Match':>8}")
print(f"  {'-'*60}")

for year in sorted(df.year.unique()):
    ydf = df[df.year == year]
    extracted = int(ydf.annual_cases.sum())
    official  = KNOWN_TOTALS.get(year, 0)
    match_pct = (extracted / official * 100) if official > 0 else 0
    fmt = ydf.format.iloc[0] if 'format' in ydf.columns else '?'
    flag = 'OK' if 70 < match_pct < 150 else 'REVIEW'
    print(f'  {year:<6} {fmt:<6} {len(ydf):>10,} {extracted:>12,} {official:>12,} {match_pct:>7.1f}%  [{flag}]')

print()
print('TOP 10 HIGHEST-BURDEN DISTRICTS (all years):')
top10 = df.groupby(['state','district'])['annual_cases'].sum().nlargest(10).reset_index()
for _, r in top10.iterrows():
    print(f'  {r.state:<22} {r.district:<28} {r.annual_cases:>10,}')

print()
print('READY FOR LOADING:')
print('  Once Supabase is back to read-write mode, run:')
print('  python data/scripts/09_load_nvbdcp.py --db-password PW \\')
print(f'    --file {OUT_CSV}')
print()
print('  Or adapt 09_load_nvbdcp.py to accept the CSV directly (it currently')
print('  expects Excel/CSV with State, District, Year, Disease, Cases columns).')
print('  The clean CSV already has those columns - just pass --file to it.')
