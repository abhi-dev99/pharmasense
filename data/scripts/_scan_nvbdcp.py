import pdfplumber
from pathlib import Path

PDF_DIR = Path(r'd:\hackathob\pharmasense\data\raw\nvbdcp')

def row_str(row, n=12):
    return [str(v)[:n] if v else '' for v in row]

print('=== 2010 DATA ROWS ===')
with pdfplumber.open(PDF_DIR / 'malaria_2010.pdf') as pdf:
    for pg_num in range(2, 6):
        pg = pdf.pages[pg_num]
        tables = pg.extract_tables()
        for t in tables:
            if t and len(t) > 2:
                print(f'\n  Page {pg_num+1}, {len(t)} rows x {len(t[0])} cols:')
                for row in t[:5]:
                    print(f'    {row_str(row, 18)}')

print()
print('=== 2017 SCAN ===')
with pdfplumber.open(PDF_DIR / 'malaria_2017.pdf') as pdf:
    print(f'  Pages: {len(pdf.pages)}')
    for pg_num in range(1, 5):
        pg = pdf.pages[pg_num]
        tables = pg.extract_tables()
        print(f'\n  Page {pg_num+1}: {len(tables)} tables')
        for ti, t in enumerate(tables[:2]):
            if t:
                print(f'    Table {ti}: {len(t)} rows x {len(t[0]) if t[0] else 0} cols')
                for row in t[:5]:
                    print(f'      {row_str(row, 14)[:14]}')

print()
print('=== 2022 SCAN ===')
with pdfplumber.open(PDF_DIR / 'malaria_2022.pdf') as pdf:
    print(f'  Pages: {len(pdf.pages)}')
    for pg_num in range(0, min(6, len(pdf.pages))):
        pg = pdf.pages[pg_num]
        tables = pg.extract_tables()
        print(f'  Page {pg_num+1}: {len(tables)} tables')
        for t in tables[:2]:
            if t and len(t) > 2:
                print(f'    ncols={len(t[0])} hdr={row_str(t[0], 14)[:8]}')
                if len(t) > 4:
                    print(f'    row4={row_str(t[4], 14)[:8]}')
