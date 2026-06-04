import pandas as pd
from pathlib import Path

df = pd.read_csv(r'd:\hackathob\pharmasense\data\processed\nvbdcp_malaria_district_annual_clean.csv')

print('=== DEEP VALIDATION: nvbdcp_malaria_district_annual_clean.csv ===')
print()

missing_years = [y for y in range(2010, 2025) if y not in df.year.unique()]
print(f'Missing years: {missing_years}')

nulls = df.isnull().sum()
print('Null values per column:')
for c, n in nulls.items():
    if n > 0:
        pct = round(100*n/len(df), 1)
        print(f'  {c}: {n} ({pct}%)')

neg = df[df.annual_cases < 0]
print(f'Negative case counts: {len(neg)}')

print()
print('States per year:')
HIGH_BURDEN = ['Odisha','Jharkhand','Chhattisgarh','Madhya Pradesh','West Bengal']
for y in sorted(df.year.unique()):
    dy = df[df.year == y]
    states = sorted(dy.state.unique())
    missing = [s for s in HIGH_BURDEN if s not in states]
    m_str = ', '.join(missing) if missing else 'None'
    print(f'  {y}: {len(states)} states | High-burden missing: {m_str}')

print()
print('High-burden state totals (all years):')
for st in ['Odisha','Jharkhand','Chhattisgarh','Madhya Pradesh','West Bengal','Uttar Pradesh']:
    sdf = df[df.state == st]
    total = sdf.annual_cases.sum()
    yrs = sorted(sdf.year.unique())
    print(f'  {st}: {total:,} total | years: {yrs}')
