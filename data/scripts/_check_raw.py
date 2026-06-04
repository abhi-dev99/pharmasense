import pandas as pd

df = pd.read_excel(r'd:\hackathob\pharmasense\data\raw\nvbdcp\Malaria_2021.xlsx')

print('States in Excel:', sorted(df['State'].unique()))
print(f'Total rows: {len(df)}')
print()

# Rajasthan check
for s in df['State'].unique():
    if 'raj' in str(s).lower():
        print('Found state:', s)

# Sample rows with case counts
print()
print('First 5 rows:')
cols = ['State','District','Population_000s','Total_Cases','PV_Total','PF_Total']
print(df[cols].head(5).to_string())

# National total
total = df['Total_Cases'].sum()
print()
print(f'National Total_Cases in Excel: {total:,}')

# Check AP specifically (visible in previous data)
ap = df[df['State'] == 'Andhra Pradesh']
print(f'Andhra Pradesh: {len(ap)} districts, {ap["Total_Cases"].sum():,} total cases')
