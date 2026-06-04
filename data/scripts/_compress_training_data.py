import gzip, shutil, pandas as pd
from pathlib import Path

data_dir = Path(r'd:\hackathob\pharmasense\ml\data')

# Compress malaria_weekly.csv to gz
src = data_dir / 'malaria_weekly.csv'
dst = data_dir / 'malaria_weekly.csv.gz'
with open(src, 'rb') as f_in, gzip.open(dst, 'wb') as f_out:
    shutil.copyfileobj(f_in, f_out)
print(f'malaria_weekly.csv.gz: {dst.stat().st_size/1e6:.1f} MB (was 29.3 MB)')

# Extract district_populations.csv
census = pd.read_excel(r'd:\hackathob\pharmasense\data\raw\census_pca\census_2011_pca.xlsx')
dist = census[(census['Level'] == 'DISTRICT') & (census['TRU'] == 'Total')][['Name','State','TOT_P']].copy()
dist.columns = ['district','state_code','pop_2011']
state_map = {
    1:'Jammu and Kashmir', 2:'Himachal Pradesh', 3:'Punjab', 4:'Chandigarh',
    5:'Uttarakhand', 6:'Haryana', 7:'Delhi', 8:'Rajasthan', 9:'Uttar Pradesh',
    10:'Bihar', 11:'Sikkim', 12:'Arunachal Pradesh', 13:'Nagaland', 14:'Manipur',
    15:'Mizoram', 16:'Tripura', 17:'Meghalaya', 18:'Assam', 19:'West Bengal',
    20:'Jharkhand', 21:'Odisha', 22:'Chhattisgarh', 23:'Madhya Pradesh',
    24:'Gujarat', 25:'Daman and Diu', 26:'Dadra and Nagar Haveli', 27:'Maharashtra',
    28:'Andhra Pradesh', 29:'Karnataka', 30:'Goa', 31:'Lakshadweep', 32:'Kerala',
    33:'Tamil Nadu', 34:'Puducherry', 35:'Andaman and Nicobar Islands',
}
dist['state'] = dist['state_code'].map(state_map).fillna('Other')
dist['population'] = (dist['pop_2011'] * (1.0128**10)).astype(int)
out = dist[['district','state','population']].reset_index(drop=True)
pop_out = data_dir / 'district_populations.csv'
out.to_csv(pop_out, index=False)
print(f'district_populations.csv: {pop_out.stat().st_size/1024:.0f} KB | {len(out)} districts')

# Verify gz reads
test = pd.read_csv(dst, nrows=5)
print(f'gz reads OK: {list(test.columns)}')

# Delete uncompressed large files from ml/data (keep gz)
src.unlink()
ncd_big = data_dir / 'ncd_demand_weekly.csv'
if ncd_big.exists():
    ncd_big.unlink()
    print('Removed ncd_demand_weekly.csv (generated inline in Colab)')
print('malaria_weekly.csv removed (gz version retained)')
print('Done.')
