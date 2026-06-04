import pandas as pd, numpy as np
from pathlib import Path

RAW  = Path(r'd:\hackathob\pharmasense\data\raw')
PROC = Path(r'd:\hackathob\pharmasense\data\processed')

sep = lambda t: print(f'\n{"="*70}\n  {t}\n{"="*70}')
ok  = lambda m: print(f'  [OK]   {m}')
warn= lambda m: print(f'  [WARN] {m}')
err = lambda m: print(f'  [ERR!] {m}')

all_anomalies = []

# ─── 3. EPICLIM (Dengue + multi-disease district-level) ────────────────────
sep('3. EPICLIM Final_data.csv (Dengue spatial training data)')
ep = pd.read_csv(RAW / 'epiclim' / 'Final_data.csv')
print(f'  Rows: {len(ep):,}')
print(f'  Columns: {list(ep.columns)}')
print(f'  Years: {sorted(ep.year.unique())}')
print(f'  States: {ep.state_ut.nunique()}')
print(f'  Districts: {ep.district.nunique()}')

# Check for nulls
null_cols = ep.isnull().sum()
null_cols = null_cols[null_cols > 0]
if not null_cols.empty:
    warn(f'Null values found:')
    for c, n in null_cols.items():
        pct = 100*n/len(ep)
        print(f'       {c}: {n} ({pct:.1f}%)')
    all_anomalies.append(('epiclim', 'WARN', f'Nulls in {list(null_cols.index)}'))
else:
    ok('No null values')

# Disease breakdown
dengue_terms = [d for d in ep.Disease.unique() if 'dengue' in str(d).lower()]
dengue_df = ep[ep.Disease.isin(dengue_terms)]
print(f'  Dengue rows: {len(dengue_df):,}')
print(f'  Dengue years: {sorted(dengue_df.year.unique())}')
print(f'  Dengue districts: {dengue_df.district.nunique()}')
print(f'  Dengue states: {dengue_df.state_ut.nunique()}')

# Check climate features
for col in ['Temp', 'preci', 'LAI']:
    nulls = dengue_df[col].isnull().sum()
    mn, mx = dengue_df[col].min(), dengue_df[col].max()
    print(f'  {col}: min={mn:.2f}, max={mx:.2f}, nulls={nulls}')
    if nulls > len(dengue_df) * 0.1:
        warn(f'{col} has {nulls} nulls (>{10}%)')
        all_anomalies.append(('epiclim', 'WARN', f'{col} has too many nulls'))

# Cases outlier check
dengue_df = dengue_df.copy()
dengue_df['Cases'] = pd.to_numeric(dengue_df['Cases'], errors='coerce')
if dengue_df.Cases.max() > 10000:
    warn(f'Max single-row dengue cases = {dengue_df.Cases.max()} (check if valid)')
    all_anomalies.append(('epiclim', 'WARN', f'Dengue outlier: max cases={dengue_df.Cases.max()}'))
else:
    ok(f'Dengue case values look sane (max={dengue_df.Cases.max()})')

# ─── 4. District Index (spatial graph adjacency) ───────────────────────────
sep('4. district_index.json (spatial graph, 736 nodes)')
import json
with open(PROC / 'district_index.json') as f:
    di = json.load(f)
print(f'  Total districts in index: {len(di):,}')
# Check for required fields
sample = list(di.values())[0] if isinstance(di, dict) else di[0]
print(f'  Sample entry keys: {list(sample.keys()) if isinstance(sample, dict) else type(sample)}')

# ─── 5. Census / Population ────────────────────────────────────────────────
sep('5. Census / District Population (demographic features)')
census_dir = RAW / 'census_pca'
pop_dir    = RAW / 'district_population'
for d in [census_dir, pop_dir]:
    if d.exists():
        files = list(d.iterdir())
        print(f'  {d.name}: {len(files)} files -> {[f.name for f in files[:5]]}')
    else:
        warn(f'{d.name} directory missing')
        all_anomalies.append((d.name, 'WARN', 'directory missing'))

# ─── 6. India GeoJSON (spatial graph construction) ─────────────────────────
sep('6. India GeoJSON (graph adjacency edges)')
geo_dir = RAW / 'india_geojson'
if geo_dir.exists():
    files = list(geo_dir.iterdir())
    print(f'  Files: {[f.name for f in files]}')
    for f in files:
        if f.suffix == '.json' or f.suffix == '.geojson':
            with open(f) as fp:
                g = json.load(fp)
            features = g.get('features', [])
            print(f'  {f.name}: {len(features)} features')
            if features:
                sample_props = list(features[0].get('properties',{}).keys())
                print(f'  Property keys: {sample_props}')
else:
    err('india_geojson directory missing!')
    all_anomalies.append(('geojson', 'ERR', 'missing geojson directory'))

# ─── 7. India Medicines (drug database) ────────────────────────────────────
sep('7. India Medicines (drug/demand forecasting features)')
med_dir = RAW / 'india_medicines'
if med_dir.exists():
    files = list(med_dir.iterdir())
    print(f'  Files: {[f.name for f in files[:8]]}')
    for f in files:
        if f.suffix in ('.csv', '.xlsx'):
            try:
                df = pd.read_csv(f) if f.suffix == '.csv' else pd.read_excel(f)
                print(f'  {f.name}: {len(df):,} rows x {len(df.columns)} cols')
                print(f'    Cols: {list(df.columns[:8])}')
            except Exception as e:
                warn(f'{f.name}: could not read ({e})')
else:
    warn('india_medicines directory missing')
    all_anomalies.append(('medicines', 'WARN', 'directory missing'))

# ─── SUMMARY ───────────────────────────────────────────────────────────────
sep('OVERALL AUDIT SUMMARY')
if not all_anomalies:
    ok('ALL DATASETS CLEAN - No anomalies detected')
else:
    print(f'  Total anomalies flagged: {len(all_anomalies)}')
    for src, sev, msg in all_anomalies:
        print(f'  [{sev}] {src}: {msg}')
