"""
Pharmasense — NVBDCP Malaria Annual Report PDF Extractor
========================================================
Reads all 15 NVBDCP Malaria Annual Report PDFs (2010-2024) using pdfplumber,
handles all 3 format generations, and outputs a clean CSV with district-level
annual malaria case counts.

FORMAT GENERATIONS (discovered from PDF analysis):
  Format A (2010-2016): 13 cols, per-state tables, "State: Gujarat" headers
                        Cols: SN, District, Pop(000s), BSC, BSE, PV, PF, Mixed, Others, Total, PF%, API, Deaths
  Format B (2017-2018): 10 cols, per-state tables, indicators only
                        Cols: SN, District, [cols], PF%, ABER, API, SPR, AFI, SFR, RT, Death_PV, Death_PF
                        NOTE: Only has rates (API), so cases = API * Pop_000s rounded to int
  Format C (2019-2021): 18 cols, per-state tables, has case counts
                        Cols: SN, District, Pop(000s), BSC, BSE, PV, PF, Mixed, Total, PF%, API, SPR, AFI, SFR, RT, Death
  Format D (2022-2024): 40 cols, all-states single table
                        Cols: SN, State, District, Pop(000s), BSC, RDT, BSE, RDT, TotalBSC, TotalBSE,
                              [PV/PF/Mixed/Pm/Po/Others/Total × 3 (Indigenous, Imported, Grand)],
                              PF%, ABER, API, SPR, AFI, SFR, RT, Death_PV, Death_PF

OUTPUT:
  data/processed/nvbdcp_malaria_district_annual.csv
    Columns: year, state, district, annual_cases, pv_cases, pf_cases, pop_000s, api, data_source

Usage:
  python data/scripts/10_extract_nvbdcp_pdfs.py
"""

import sys, re, warnings
from pathlib import Path

warnings.filterwarnings('ignore')

ROOT    = Path(__file__).parent.parent.parent
PDF_DIR = ROOT / 'data' / 'raw' / 'nvbdcp'
OUT_DIR = ROOT / 'data' / 'processed'
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_CSV = OUT_DIR / 'nvbdcp_malaria_district_annual.csv'

try:
    import pdfplumber
except ImportError:
    import subprocess, sys as _sys
    subprocess.run([_sys.executable, '-m', 'pip', 'install', '-q', 'pdfplumber'], check=True)
    import pdfplumber

import pandas as pd
import numpy as np

# ── State name normalization map ──────────────────────────────────────────────
# NVBDCP reports use varied state names; normalize to match our districts table
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

def clean_int(v):
    """Convert a table cell to int, return None if not parseable."""
    if v is None:
        return None
    s = str(v).strip().replace(',', '').replace(' ', '')
    if s in ('', '-', 'NA', 'N/A', 'NIL', 'nil'):
        return 0
    m = re.search(r'[\d]+', s)
    if m:
        return int(m.group())
    return None

def clean_float(v):
    """Convert a table cell to float, return None if not parseable."""
    if v is None:
        return None
    s = str(v).strip().replace(',', '')
    try:
        return float(s)
    except ValueError:
        return None

def is_state_total_row(row):
    """True if this row is a state subtotal (not a district row)."""
    if not row or not row[0]:
        return False
    # State total rows: SN is empty or contains word 'Total'
    sn = str(row[0]).strip().lower()
    dist = str(row[2] if len(row) > 2 else '').strip().lower() if len(row) > 2 else ''
    name = str(row[1] if len(row) > 1 else '').strip().lower() if len(row) > 1 else ''
    return 'total' in sn or 'total' in dist or ('total' in name and not name.replace('total','').strip())

def is_header_row(row):
    """True if this is a header row (contains column names)."""
    if not row:
        return False
    vals = [str(v).strip().lower() for v in row if v]
    return any(v in ('sn', 'district', 'state', 'pop. in', 'b.s.c.', 'bsc') for v in vals)


# ═══════════════════════════════════════════════════════════════════════════════
# FORMAT A: 2010-2016 (13 columns, per-state tables)
# ═══════════════════════════════════════════════════════════════════════════════
# Expected columns: SN | District | Pop(000s) | BSC | BSE | PV | PF | Mixed |
#                   Others | Total | PF% | API | Deaths
# State name is in the table title row: "State: Gujarat"

def extract_format_a(pdf, year):
    """
    Extract district malaria data from Format A PDFs (2010-2016).
    Format A column layout (0-indexed, NO SN column):
      0: District name
      1: Pop (000s)
      2: BSE
      3: PV Cases
      4: PF Cases
      5: Total Cases   <-- what we want
      6: PF%
      7: ABER
      (may have more cols for API, SPR etc.)
    State name appears in the first row of each table: 'State: Gujarat'
    """
    records = []
    current_state = None

    for pg in pdf.pages:
        tables = pg.extract_tables()
        for table in tables:
            if not table or len(table) < 2:
                continue

            # Check if first row is a state header: "State: Gujarat" pattern
            # pdfplumber may truncate: "State: Chandiga" for Chandigarh
            first_cell = str(table[0][0] or '').strip()
            state_match = re.match(r'^State[:\s]+(.+)$', first_cell, re.IGNORECASE)
            if state_match:
                raw_state  = state_match.group(1).strip()
                # Try exact match first, then prefix match for truncated names
                normalized = normalize_state(raw_state)
                if normalized == raw_state:  # no match found, try prefix
                    for key, val in STATE_NORMALIZE.items():
                        if key.startswith(raw_state.lower()[:8]):
                            normalized = val
                            break
                current_state = normalized
                continue

            if not current_state:
                continue

            # Detect the "Total Cases" column index dynamically from the header row
            total_col = 5   # default for Format A
            pv_col    = 3
            pf_col    = 4
            pop_col   = 1
            api_col   = None

            for hdr_row in table[:3]:
                if not hdr_row:
                    continue
                for ci, cell in enumerate(hdr_row):
                    s = str(cell or '').strip().lower()
                    if 'total' in s and 'bse' not in s and 'bsc' not in s:
                        total_col = ci
                    elif 'pv' in s or 'p.v' in s:
                        pv_col = ci
                    elif 'pf' in s or 'p.f' in s and 'pf%' not in s:
                        pf_col = ci
                    elif "pop" in s:
                        pop_col = ci
                    elif 'a.p.i' in s or s == 'api':
                        api_col = ci

            for row in table:
                if not row:
                    continue

                # Format A: col 0 is district name (no SN)
                district = str(row[0] or '').strip()

                # Skip header rows and state total rows
                if not district or district.lower() in ('district', ''):
                    continue
                if 'total' in district.lower() or 'state' in district.lower():
                    continue
                # Skip if it looks like a number (probably a table artifact)
                if district.replace('.','').isdigit():
                    continue

                pop_000s = clean_float(row[pop_col]) if len(row) > pop_col else None
                pv_cases = clean_int(row[pv_col])    if len(row) > pv_col  else None
                pf_cases = clean_int(row[pf_col])    if len(row) > pf_col  else None
                total    = clean_int(row[total_col]) if len(row) > total_col else None
                api      = clean_float(row[api_col]) if api_col is not None and len(row) > api_col else None

                # Fallback: compute total from PV + PF if Total column missing
                if (total is None or total == 0) and (pv_cases or pf_cases):
                    total = (pv_cases or 0) + (pf_cases or 0)

                if total is None:
                    continue

                records.append({
                    'year': year, 'state': current_state, 'district': district,
                    'annual_cases': max(0, total),
                    'pv_cases': max(0, pv_cases or 0),
                    'pf_cases': max(0, pf_cases or 0),
                    'pop_000s': pop_000s,
                    'api': api,
                    'data_source': f'nvbdcp_pdf_{year}',
                    'format': 'A',
                })

    return records


# ═══════════════════════════════════════════════════════════════════════════════
# FORMAT B: 2017-2018 (10 columns, per-state, indicators only)
# ═══════════════════════════════════════════════════════════════════════════════
# Columns: SN | District | POP(000s) | BSC | BSE | Total_POS | PF | ... | PF% | API | ...
# The 2017/2018 reports may have case counts hidden in additional columns.
# We look for any column that looks like "Total" positive cases.

def extract_format_b(pdf, year):
    """Extract district data from Format B PDFs (2017-2018)."""
    records = []
    current_state = None
    STATE_PAGE_PATTERN = re.compile(r'(?:State|District.*?Report.*?[-:]\s*)(.+?)(?:\s+\d{4})?$', re.IGNORECASE)

    for pg in pdf.pages:
        # Extract state name from page text (it's in the page header for 2017)
        page_text = pg.extract_text() or ''
        for line in page_text.split('\n')[:10]:
            # Look for "STATE: ASSAM" or "Districtwise Annual Report 2017 - ASSAM"
            for pattern in [
                re.compile(r'(?:state\s*[:\-]\s*)([A-Za-z &]+)', re.IGNORECASE),
                re.compile(r'Annual Report \d{4}[\s\-]+([A-Za-z &]+)', re.IGNORECASE),
                re.compile(r'^([A-Za-z &]{5,30})\s*$'),
            ]:
                m = pattern.search(line.strip())
                if m:
                    candidate = normalize_state(m.group(1).strip())
                    if candidate in STATE_NORMALIZE.values():
                        current_state = candidate
                        break

        tables = pg.extract_tables()
        for table in tables:
            if not table or len(table) < 3:
                continue

            # Detect the column index for Total positive cases
            # Look in header rows (first 2 rows)
            total_col  = None
            pv_col     = None
            pf_col     = None
            pop_col    = None
            api_col    = None
            dist_col   = 1  # SN is col 0, District is col 1

            for hdr_row in table[:3]:
                if not hdr_row:
                    continue
                for ci, cell in enumerate(hdr_row):
                    s = str(cell or '').strip().lower()
                    if 'total' in s and 'bse' not in s and 'bsc' not in s and total_col is None:
                        total_col = ci
                    if s in ('p.v.', 'pv') and pv_col is None:
                        pv_col = ci
                    if s in ('p.f.', 'pf') and pf_col is None:
                        pf_col = ci
                    if "pop" in s and pop_col is None:
                        pop_col = ci
                    if s == 'a.p.i.' or s == 'api':
                        api_col = ci

            for row in table:
                if not row or not row[0]:
                    continue
                sn = str(row[0]).strip()
                if not sn.isdigit():
                    continue

                district = str(row[dist_col] or '').strip() if len(row) > dist_col else ''
                if not district or 'total' in district.lower():
                    continue

                pop_000s   = clean_float(row[pop_col])  if pop_col  is not None and len(row) > pop_col  else None
                total      = clean_int(row[total_col])  if total_col is not None and len(row) > total_col else None
                pv_cases   = clean_int(row[pv_col])     if pv_col   is not None and len(row) > pv_col   else None
                pf_cases   = clean_int(row[pf_col])     if pf_col   is not None and len(row) > pf_col   else None
                api        = clean_float(row[api_col])  if api_col  is not None and len(row) > api_col  else None

                # If total still None but we have API + pop, estimate
                if total is None and api is not None and pop_000s is not None and pop_000s > 0:
                    total = max(0, int(round(api * pop_000s)))

                records.append({
                    'year': year, 'state': current_state or 'Unknown', 'district': district,
                    'annual_cases': total or 0,
                    'pv_cases': pv_cases or 0,
                    'pf_cases': pf_cases or 0,
                    'pop_000s': pop_000s,
                    'api': api,
                    'data_source': f'nvbdcp_pdf_{year}',
                    'format': 'B',
                })

    return records


# ═══════════════════════════════════════════════════════════════════════════════
# FORMAT C: 2019-2021 (18 columns, per-state)
# ═══════════════════════════════════════════════════════════════════════════════
# Cols: SN | District | Pop(000s) | BSC | BSE | PV | PF | Mixed | Total | PF% | API | SPR | AFI | SFR | RT | Deaths

def extract_format_c(pdf, year):
    """Extract district data from Format C PDFs (2019-2021)."""
    records = []
    current_state = None
    # Same pattern as Format B: state is in table[0][0]
    # e.g. 'Epidemiological Situation Report of Bihar 2019'
    STATE_FROM_HDR = re.compile(
        r'Report\s+(?:of\s+)?([A-Za-z &]+?)\s+\d{4}',
        re.IGNORECASE
    )

    for pg in pdf.pages:
        tables = pg.extract_tables()
        for table in tables:
            if not table or len(table) < 3:
                continue

            # Detect state from table first row
            first_cell = str(table[0][0] or '').strip() if table[0] else ''
            m = STATE_FROM_HDR.search(first_cell)
            if m:
                raw = m.group(1).strip()
                candidate = normalize_state(raw)
                if candidate != raw:
                    current_state = candidate
                else:
                    for key, val in STATE_NORMALIZE.items():
                        if key.startswith(raw.lower()[:8]) or raw.lower().startswith(key[:8]):
                            current_state = val
                            break

            if not current_state:
                continue

            # Identify columns dynamically (Format C is consistent 18-col)
            # Defaults: SN=0, District=1, Pop=2, BSC=3, BSE=4, PV=5, PF=6, Mixed=7, Total=8
            total_col = 8
            pv_col    = 5
            pf_col    = 6
            pop_col   = 2
            api_col   = 11
            dist_col  = 1

            for hdr in table[:3]:
                if not hdr:
                    continue
                for ci, cell in enumerate(hdr):
                    s = str(cell or '').strip().lower()
                    if s == 'total' and total_col == 8:
                        total_col = ci
                    if s in ('p.v.', 'pv') and pv_col == 5:
                        pv_col = ci
                    if s in ('p.f.', 'pf') and pf_col == 6:
                        pf_col = ci
                    if 'pop' in s and pop_col == 2:
                        pop_col = ci
                    if 'a.p.i' in s or s == 'api':
                        api_col = ci

            for row in table:
                if not row or not row[0]:
                    continue
                sn = str(row[0]).strip()
                if not sn.isdigit():
                    continue
                district = str(row[dist_col] or '').strip() if len(row) > dist_col else ''
                if not district or 'total' in district.lower():
                    continue

                pop_000s = clean_float(row[pop_col]) if len(row) > pop_col else None
                total    = clean_int(row[total_col])  if len(row) > total_col else None
                pv_cases = clean_int(row[pv_col])     if len(row) > pv_col   else None
                pf_cases = clean_int(row[pf_col])     if len(row) > pf_col   else None
                api      = clean_float(row[api_col])  if len(row) > api_col  else None

                records.append({
                    'year': year, 'state': current_state, 'district': district,
                    'annual_cases': max(0, total or 0),
                    'pv_cases': max(0, pv_cases or 0),
                    'pf_cases': max(0, pf_cases or 0),
                    'pop_000s': pop_000s,
                    'api': api,
                    'data_source': f'nvbdcp_pdf_{year}',
                    'format': 'C',
                })

    return records



# ═══════════════════════════════════════════════════════════════════════════════
# FORMAT D: 2022-2024 (40 columns, all-states single table)
# ═══════════════════════════════════════════════════════════════════════════════
# Confirmed columns: 0=SN, 1=State, 2=District, 3=Pop(000s),
#                    24=PV_total, 25=PF_total, 30=Grand_Total
# Grand Total (col 30) = PV+PF+Mixed+Pm+Po+Others (indigenous + imported)

def extract_format_d(pdf, year):
    """
    Extract district data from Format D PDFs (2022-2024).

    2024 (40 cols — confirmed from PDF scan):
      SN(0) | State(1) | District(2) | Pop(3) | BSC | RDT | BSE | RDT |
      TotBSC | TotBSE | [PV PF Mix Pm Po Oth Tot] × 3 (Indig/Imp/Grand) |
      PF% | ABER | API | SPR | AFI | SFR | RT | Death_PV | Death_PF
      Grand Total = col 30

    2022-2023 (36 cols):
      SN(0) | District(1) | Pop(2) | ...
      Grand Total = col 26
      Per-state pages — detect state from page text.
    """
    records = []
    current_state = None

    # Pattern to extract state from page-level text (for 2022-2023 per-state pages)
    STATE_FROM_HDR = re.compile(
        r'Report\s+(?:of\s+)?([A-Za-z &]+?)\s+\d{4}',
        re.IGNORECASE
    )

    for pg in pdf.pages:
        page_text = pg.extract_text() or ''
        for line in page_text.split('\n')[:12]:
            line = line.strip()
            for key, val in STATE_NORMALIZE.items():
                if line.lower() == key or line.lower().startswith(key[:10]):
                    current_state = val
                    break

        tables = pg.extract_tables()
        for table in tables:
            if not table or len(table) < 3:
                continue

            # Detect column count (determines 40-col vs 36-col layout)
            n_cols = max((len(r) for r in table if r), default=0)

            if n_cols >= 38:
                # ── FORMAT D40 (2024): hardcoded column positions confirmed by scan ──
                # SN=0, State=1, District=2, Pop=3
                # PV_grand=24, PF_grand=25, Grand_Total=30, API=33
                for row in table:
                    if not row or len(row) < 31:
                        continue
                    sn = str(row[0] or '').strip()
                    if not sn.isdigit():
                        continue

                    state    = normalize_state(str(row[1] or '').strip())
                    district = str(row[2] or '').strip()
                    if not district or 'total' in district.lower():
                        continue
                    # Skip rows where district looks like a state name
                    # (table boundary artifacts at state transitions)
                    if district in STATE_NORMALIZE.values() or normalize_state(district) != district:
                        state    = state or normalize_state(district)
                        continue

                    pop_000s = clean_float(row[3])
                    pv_cases = clean_int(row[24]) if len(row) > 24 else None
                    pf_cases = clean_int(row[25]) if len(row) > 25 else None
                    total    = clean_int(row[30]) if len(row) > 30 else None
                    api      = clean_float(row[33]) if len(row) > 33 else None

                    records.append({
                        'year': year, 'state': state or 'Unknown', 'district': district,
                        'annual_cases': max(0, total or 0),
                        'pv_cases': max(0, pv_cases or 0),
                        'pf_cases': max(0, pf_cases or 0),
                        'pop_000s': pop_000s,
                        'api': api,
                        'data_source': f'nvbdcp_pdf_{year}',
                        'format': 'D40',
                    })

            else:
                # ── FORMAT D36 (2022-2023): per-state pages, no State column ──
                # Also try to detect state from table header row
                first_cell = str(table[0][0] or '').strip() if table[0] else ''
                m = STATE_FROM_HDR.search(first_cell)
                if m:
                    raw = m.group(1).strip()
                    candidate = normalize_state(raw)
                    if candidate != raw:
                        current_state = candidate
                    else:
                        for key, val in STATE_NORMALIZE.items():
                            if key.startswith(raw.lower()[:8]) or raw.lower().startswith(key[:8]):
                                current_state = val
                                break

                # D36 column positions: SN=0, District=1, Pop=2
                # Grand Total = col 26, PV=20, PF=21, API=29
                for row in table:
                    if not row or len(row) < 27:
                        continue
                    sn = str(row[0] or '').strip()
                    if not sn.isdigit():
                        continue

                    district = str(row[1] or '').strip()
                    if not district or 'total' in district.lower():
                        continue

                    pop_000s = clean_float(row[2])
                    pv_cases = clean_int(row[20]) if len(row) > 20 else None
                    pf_cases = clean_int(row[21]) if len(row) > 21 else None
                    total    = clean_int(row[26]) if len(row) > 26 else None
                    api      = clean_float(row[29]) if len(row) > 29 else None

                    records.append({
                        'year': year, 'state': current_state or 'Unknown', 'district': district,
                        'annual_cases': max(0, total or 0),
                        'pv_cases': max(0, pv_cases or 0),
                        'pf_cases': max(0, pf_cases or 0),
                        'pop_000s': pop_000s,
                        'api': api,
                        'data_source': f'nvbdcp_pdf_{year}',
                        'format': 'D36',
                    })

    return records



# ═══════════════════════════════════════════════════════════════════════════════
# MAIN EXTRACTION LOOP
# ═══════════════════════════════════════════════════════════════════════════════

YEAR_FORMAT = {
    2010: 'A', 2011: 'A', 2012: 'A', 2013: 'A',
    2014: 'A', 2015: 'A', 2016: 'A',
    2017: 'B', 2018: 'B',
    2019: 'C', 2020: 'C', 2021: 'C',
    2022: 'D', 2023: 'D', 2024: 'D',
}

EXTRACTORS = {
    'A': extract_format_a,
    'B': extract_format_b,
    'C': extract_format_c,
    'D': extract_format_d,
}

all_records = []
total_stats = {}

print('='*65)
print('  Pharmasense — NVBDCP Malaria PDF Extractor')
print('='*65)

for year in sorted(YEAR_FORMAT.keys()):
    pdf_path = PDF_DIR / f'malaria_{year}.pdf'
    if not pdf_path.exists():
        print(f'[SKIP] {year}: file not found')
        continue

    fmt      = YEAR_FORMAT[year]
    extractor = EXTRACTORS[fmt]

    try:
        with pdfplumber.open(pdf_path) as pdf:
            records = extractor(pdf, year)

        # Filter out zero-case junk rows
        records = [r for r in records if r['district'] and len(r['district']) > 1]

        # Post-process: clamp negatives, compute total if missing
        for r in records:
            r['annual_cases'] = max(0, r['annual_cases'] or 0)
            r['pv_cases']     = max(0, r['pv_cases'] or 0)
            r['pf_cases']     = max(0, r['pf_cases'] or 0)

        n_districts = len(records)
        n_nonzero   = sum(1 for r in records if r['annual_cases'] > 0)
        total_cases = sum(r['annual_cases'] for r in records)

        total_stats[year] = {
            'fmt': fmt, 'districts': n_districts,
            'nonzero': n_nonzero, 'total_cases': total_cases
        }
        all_records.extend(records)

        print(f'[{year}] Format {fmt} | {n_districts:>4} districts | '
              f'{n_nonzero:>3} with cases | total={total_cases:>8,}')

    except Exception as e:
        print(f'[{year}] ERROR: {e}')
        import traceback; traceback.print_exc()

# ── Save output ────────────────────────────────────────────────────────────────
df = pd.DataFrame(all_records)
df = df.sort_values(['year', 'state', 'district']).reset_index(drop=True)

# Remove obvious junk rows (district name is a number, very short, or contains 'total')
df = df[~df['district'].str.lower().str.contains('total|subtotal|grand', na=False)]
df = df[df['district'].str.len() >= 3]
df = df[~df['district'].str.match(r'^\d+$')]

df.to_csv(OUT_CSV, index=False)

print()
print(f'[OK] Saved {len(df):,} records -> {OUT_CSV}')
print()
print('SUMMARY BY YEAR:')
print(f"  {'Year':<6} {'Fmt':<4} {'Districts':>10} {'With Cases':>12} {'Total Cases':>14}")
print(f"  {'-'*50}")
for year, s in sorted(total_stats.items()):
    print(f"  {year:<6} {s['fmt']:<4} {s['districts']:>10,} {s['nonzero']:>12,} {s['total_cases']:>14,}")

print()
print('NATIONAL TOTALS BY YEAR:')
yearly = df.groupby('year')['annual_cases'].sum()
for yr, total in yearly.items():
    # Cross-reference with known NVBDCP national totals
    known = {
        2010: 1599400, 2011: 1310190, 2012: 1067824, 2013: 882099,
        2014: 1102205, 2015: 1136986, 2016: 1089724, 2017: 844558,
        2018: 429928,  2019: 338494,  2020: 186532,  2021: 171306,
        2022: 173000,  2023: 170000,
    }
    expected = known.get(yr, 0)
    match_pct = (total / expected * 100) if expected > 0 else 0
    flag = 'OK' if 70 < match_pct < 130 else 'REVIEW'
    print(f'  {yr}: extracted={total:>9,}  expected={expected:>9,}  match={match_pct:>6.1f}%  [{flag}]')

print()
print('TOP 10 HIGHEST-BURDEN DISTRICTS (all years combined):')
top10 = df.groupby(['state','district'])['annual_cases'].sum().nlargest(10).reset_index()
for _, row in top10.iterrows():
    print(f'  {row.state:<20} {row.district:<25} {row.annual_cases:>10,}')

print()
print('Next step: run data/scripts/09_load_nvbdcp.py with this CSV once Supabase is back to read-write mode.')
