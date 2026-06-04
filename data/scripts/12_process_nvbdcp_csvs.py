import csv
import re
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
PDF_DIR = ROOT / 'data' / 'raw' / 'nvbdcp'
OUT_DIR = ROOT / 'data' / 'processed'
OUT_CSV = OUT_DIR / 'nvbdcp_malaria_district_annual_clean.csv'

STATE_NORMALIZE = {
    'andaman & nicobar islands': 'Andaman and Nicobar Islands',
    'andaman and nicobar islands': 'Andaman and Nicobar Islands',
    'andaman and nicobar': 'Andaman and Nicobar Islands',
    'andaman and nico': 'Andaman and Nicobar Islands',
    'a&n islands': 'Andaman and Nicobar Islands',
    'a & n island': 'Andaman and Nicobar Islands',
    'andhra pradesh': 'Andhra Pradesh',
    'arunachal pradesh': 'Arunachal Pradesh',
    'assam': 'Assam',
    'bihar': 'Bihar',
    'chandigarh': 'Chandigarh',
    'chhattisgarh': 'Chhattisgarh',
    'chattisgarh': 'Chhattisgarh',
    'd&n haveli': 'Dadra and Nagar Haveli',
    'dadra & nagar haveli': 'Dadra and Nagar Haveli',
    'the dadra and nag': 'Dadra and Nagar Haveli',
    'daman & diu': 'Daman and Diu',
    'delhi': 'Delhi',
    'goa': 'Goa',
    'gujarat': 'Gujarat',
    'haryana': 'Haryana',
    'himachal pradesh': 'Himachal Pradesh',
    'j&k': 'Jammu and Kashmir',
    'jammu & kashmir': 'Jammu and Kashmir',
    'jammu and kashmir': 'Jammu and Kashmir',
    'jammu and kashmi': 'Jammu and Kashmir',
    'jharkhand': 'Jharkhand',
    'karnataka': 'Karnataka',
    'kerala': 'Kerala',
    'lakshadweep': 'Lakshadweep',
    'ladakh': 'Ladakh',
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
    'rajsthan': 'Rajasthan',
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

def clean_int(v):
    s = str(v).replace(',', '').strip()
    if not s or s.lower() in ('na', '-', 'nil'): return 0
    m = re.search(r'\d+', s)
    return int(m.group()) if m else 0

def clean_float(v):
    s = str(v).replace(',', '').strip()
    try: return float(s)
    except: return None

def normalize_state(s):
    s = str(s).strip().lower()
    return STATE_NORMALIZE.get(s, s.title() if s else '')

all_records = []

print("=== Starting 100% Deterministic NVBDCP Data Extraction ===")

for year in range(2010, 2025):
    if year in [2017, 2018]: 
        print(f"Skipping {year} (no raw case data available, rates only).")
        continue
    
    csv_path = PDF_DIR / f'malaria_{year}.csv'
    if not csv_path.exists(): 
        print(f"File not found: {csv_path}")
        continue
    
    current_state = None
    
    # Pre-read the file to define column mapping based on the header format
    if year <= 2016:
        dist_col = 0
        pop_col = 1
        pv_col = 3
        pf_col = 4
        total_col = 5
    elif year in [2019]:
        dist_col = 1
        pop_col = 2
        pv_col = 5
        pf_col = 6
        total_col = 8
    elif year in [2020]:
        dist_col = 1
        pop_col = 2
        pv_col = 9
        pf_col = 10
        total_col = 12
    elif year in [2021]:
        dist_col = 1
        pop_col = 2
        pv_col = 17
        pf_col = 18
        total_col = 20
    elif year in [2022, 2023]:
        dist_col = 1
        pop_col = 2
        pv_col = 20
        pf_col = 21
        total_col = 26
    elif year == 2024:
        dist_col = 2
        pop_col = 3
        pv_col = 24
        pf_col = 25
        total_col = 30
        
    year_records = []
    re_state = re.compile(r'(?:State:\s*([A-Za-z &]+)|Report\s+(?:of\s+)?([A-Za-z &]+?)(?:\s*-\s*\d{4}|\s*\d{4}))', re.IGNORECASE)
    re_state_total = re.compile(r'^([A-Za-z &]+?)\s+Total', re.IGNORECASE)
    
    with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f)
        buffered_rows = []
        for row in reader:
            if not row: continue
            text = ' '.join(row).strip()
            if not text: continue
            
            # Skip national summary tables to avoid duplicates
            if 'grand total' in text.lower() or 'state-wise' in text.lower() or 'summary' in text.lower():
                pass
            if year < 2024 and row[0].isdigit() and len(row) > 1 and normalize_state(row[1]) in STATE_NORMALIZE.values():
                continue # National summary row
                
            # 1. Detect State changes
            if year == 2023:
                # 2023 has no headers, only <State> Total at the end of the block
                m_tot = None
                for cell in row[:5]:
                    s = str(cell).strip()
                    m_tot = re_state_total.search(s)
                    if m_tot and normalize_state(m_tot.group(1)) in STATE_NORMALIZE.values():
                        current_state = normalize_state(m_tot.group(1))
                        break
                
                if current_state:
                    # Process buffered rows for this state
                    for brow in buffered_rows:
                        sn = str(brow[0]).strip()
                        if not sn.isdigit(): continue
                        if len(brow) <= total_col: continue
                        dist = str(brow[dist_col]).strip()
                        if not dist or 'total' in dist.lower(): continue
                        if normalize_state(dist) in STATE_NORMALIZE.values(): continue
                        cases = clean_int(brow[total_col])
                        year_records.append({
                            'year': year, 'state': current_state, 'district': dist,
                            'annual_cases': cases,
                            'pv_cases': clean_int(brow[pv_col]) if pv_col > 0 else 0,
                            'pf_cases': clean_int(brow[pf_col]) if pf_col > 0 else 0,
                            'pop_000s': clean_float(brow[pop_col]) if pop_col >= 0 else None,
                            'data_source': f'csv_{year}'
                        })
                    buffered_rows = [] # Reset buffer
                    current_state = None # Reset state
                else:
                    buffered_rows.append(row)
                continue
            else:
                for cell in row: 
                    s = str(cell).strip()
                    m = re_state.search(s)
                    if m:
                        cand = normalize_state(m.group(1) or m.group(2))
                        if cand in STATE_NORMALIZE.values():
                            current_state = cand
                            break
                
                # If 2024, state is in col 1 explicitly
                if year == 2024 and len(row) > 2 and row[0].strip().isdigit():
                    current_state = normalize_state(row[1])
                    
                if not current_state:
                    continue
                    
                # 2. Extract Data Row
                sn = str(row[0]).strip()
                if year <= 2016:
                    if len(row) <= dist_col: continue
                    if not row[dist_col] or row[dist_col].lower() in ('district', '', 'total', 'grand total'): continue
                    if row[dist_col].isdigit() or 'state:' in row[dist_col].lower(): continue
                else:
                    if not sn.isdigit(): continue
                    
                if len(row) <= total_col: continue
                
                dist = str(row[dist_col]).strip()
                if not dist or 'total' in dist.lower(): continue
                if normalize_state(dist) in STATE_NORMALIZE.values():
                    continue # Boundary artifact prevention
                    
                cases = clean_int(row[total_col])
                
                year_records.append({
                    'year': year, 'state': current_state, 'district': dist,
                    'annual_cases': cases,
                    'pv_cases': clean_int(row[pv_col]) if pv_col > 0 else 0,
                    'pf_cases': clean_int(row[pf_col]) if pf_col > 0 else 0,
                    'pop_000s': clean_float(row[pop_col]) if pop_col >= 0 else None,
                    'data_source': f'csv_{year}'
                })

    # Validate against massive outliers before adding
    state_sums = {}
    for r in year_records:
        state_sums[r['state']] = state_sums.get(r['state'], 0) + r['annual_cases']
    
    corrupt = False
    for st, total in state_sums.items():
        if total > 500_000:
            print(f"  [ERROR] {year} {st} has {total:,} cases. Validation failed. Dropping year.")
            corrupt = True
            break
        if st in ('Lakshadweep', 'Chandigarh') and total > 5_000:
            print(f"  [ERROR] {year} {st} has {total:,} cases (Impossible). Validation failed.")
            corrupt = True
            break
            
    if not corrupt:
        all_records.extend(year_records)
        print(f"  -> Added {len(year_records)} rows for {year}. (Total cases: {sum(r['annual_cases'] for r in year_records):,})")

df_out = pd.DataFrame(all_records)
df_out.to_csv(OUT_CSV, index=False)
print(f"\n[OK] Saved {len(df_out):,} absolutely clean records to {OUT_CSV}")
