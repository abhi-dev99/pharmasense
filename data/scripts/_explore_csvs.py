import csv
from pathlib import Path
import re

PDF_DIR = Path(r'd:\hackathob\pharmasense\data\raw\nvbdcp')

def sample_csv(year):
    print(f'\n--- {year} ---')
    try:
        with open(PDF_DIR / f'malaria_{year}.csv', 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.reader(f)
            found_header = False
            for row in reader:
                text = ' '.join(row).lower()
                
                # Check for state context
                if 'state:' in text or 'report of' in text:
                    print(f'STATE ROW: {row[:5]}')
                
                # Check for table header
                if 'district' in text and not found_header:
                    print(f'HEADER ROW: {row[:10]}')
                    found_header = True
                
                # Sample a data row
                if found_header and len(row) > 2 and row[0].strip().isdigit():
                    print(f'DATA ROW: {row[:10]}')
                    break
    except Exception as e:
        print(f'Error: {e}')

for y in [2010, 2016, 2019, 2020, 2022, 2024]:
    sample_csv(y)
