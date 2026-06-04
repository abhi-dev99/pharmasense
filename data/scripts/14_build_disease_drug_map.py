"""
Pharmasense — Fix 2: Disease-to-Drug Mapping Table
===================================================
Builds data/seed/disease_drug_map.csv from India's official
National Treatment Guidelines.

Sources (all publicly available government/WHO publications):
  - NVBDCP National Drug Policy for Malaria (2013, rev. 2019)
    https://nvbdcp.gov.in/Doc/Drug-Policy-2013.pdf
  - DGHS Dengue Clinical Management Guidelines (2021)
    https://mohfw.gov.in/sites/default/files/Dengue_guidelines.pdf
  - IDSP Integrated Disease Surveillance Programme — Cholera management
  - IMNCI (Integrated Management of Neonatal and Childhood Illness)
  - RNTCP/NTP National Strategic Plan for TB Elimination 2017-2025
    Fixed-dose combination (FDC) treatment regimens
  - NPCDCS (National Programme for Prevention & Control of Cancer,
    Diabetes, CVD & Stroke) — Standard Treatment Protocols
  - National Iron+ Initiative — Anaemia treatment guidelines (NFHS-5)
  - WHO Essential Medicines List (EML) 2023, India EDL 2022

Column definitions:
  disease              : enum matching our disease_type table
  drug_name            : INN (International Nonproprietary Name) canonical
  drug_class           : pharmacological/therapeutic class
  route                : oral | iv | im | subcutaneous
  formulation          : tablet/capsule/sachet/vial/injection
  standard_strength_mg : mg per tablet/vial/sachet as stocked in India
  adult_dose_mg        : mg per dose for adult (70kg reference)
  child_dose_mg_per_kg : mg/kg per dose for children
  doses_per_day        : number of doses per day
  treatment_days       : full course duration in days
  tablets_per_case     : total tablets/vials for one complete treatment
                         (= adult_dose_mg/standard_strength * doses_per_day * days)
                         For CHRONIC diseases (is_chronic=True): this is per 30-day supply
  is_chronic           : True for non-acute conditions (hypertension, diabetes, anaemia)
                         Demand modelled as prevalence × 30-day refill, not case count
  is_essential_medicine: Y/N — WHO EML 2023 / India EDL 2022
  protocol_source      : authoritative guideline reference
  notes                : clinical notes, contraindications, sub-conditions

Usage in LightGBM:
  For ACUTE diseases: demand = forecasted_cases × tablets_per_case
  For CHRONIC:        demand = prevalent_patients × tablets_per_case (monthly)
"""

import csv
from pathlib import Path

OUT = Path(__file__).parent.parent / 'seed' / 'disease_drug_map.csv'
OUT.parent.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# THE MAPPING TABLE
# Source: India government treatment guidelines (all references in docstring)
# ─────────────────────────────────────────────────────────────────────────────
ROWS = [

    # ══════════════════════════════════════════════════════════════════════════
    # MALARIA — PLASMODIUM VIVAX (PV) — NVBDCP Drug Policy 2013/2019
    # ══════════════════════════════════════════════════════════════════════════
    {
        'disease': 'malaria',
        'sub_condition': 'PV_uncomplicated',
        'drug_name': 'Chloroquine Phosphate',
        'drug_class': 'Aminoquinoline antimalarial',
        'route': 'oral',
        'formulation': 'tablet',
        'standard_strength_mg': 250,        # 250mg salt = 150mg base
        'adult_dose_mg': 1500,              # 25 mg base/kg over 3 days
        'child_dose_mg_per_kg': 10,         # 10+10+5 mg base/kg over 3 days
        'doses_per_day': 1,
        'treatment_days': 3,
        'tablets_per_case': 5,              # 2+2+1 tablets over 3 days (150mg base each)
        'is_chronic': False,
        'is_essential_medicine': 'Y',
        'protocol_source': 'NVBDCP Drug Policy 2013 (rev 2019), Section 3.1',
        'notes': 'First-line for PV malaria. Resistance reported in Papua — monitor. '
                 'Give with food to reduce GI side effects.',
    },
    {
        'disease': 'malaria',
        'sub_condition': 'PV_radical_cure',
        'drug_name': 'Primaquine',
        'drug_class': '8-aminoquinoline — anti-relapse / gametocytocidal',
        'route': 'oral',
        'formulation': 'tablet',
        'standard_strength_mg': 7.5,
        'adult_dose_mg': 15,                # 0.25 mg/kg/day = ~15mg for 60kg adult
        'child_dose_mg_per_kg': 0.25,
        'doses_per_day': 1,
        'treatment_days': 14,
        'tablets_per_case': 28,             # 2 tablets × 14 days
        'is_chronic': False,
        'is_essential_medicine': 'Y',
        'protocol_source': 'NVBDCP Drug Policy 2013 (rev 2019), Section 3.1',
        'notes': 'MANDATORY for PV radical cure (hypnozoite clearance). '
                 'CONTRAINDICATED in G6PD deficiency and pregnancy — screen first. '
                 'Skip in 1st trimester. Higher dose (0.5mg/kg) in Oceania strains.',
    },

    # ══════════════════════════════════════════════════════════════════════════
    # MALARIA — PLASMODIUM FALCIPARUM (PF) — NVBDCP Drug Policy 2013/2019
    # ══════════════════════════════════════════════════════════════════════════
    {
        'disease': 'malaria',
        'sub_condition': 'PF_uncomplicated',
        'drug_name': 'Artesunate + Amodiaquine FDC',
        'drug_class': 'ACT (Artemisinin-based Combination Therapy)',
        'route': 'oral',
        'formulation': 'tablet',
        'standard_strength_mg': 100,        # AS 100mg + AQ 270mg per tablet (adult)
        'adult_dose_mg': 200,               # 4 mg/kg AS = ~280mg; rounded to 2 tablets
        'child_dose_mg_per_kg': 4,          # AS component: 4mg/kg/day
        'doses_per_day': 1,
        'treatment_days': 3,
        'tablets_per_case': 6,              # 2 tablets/day × 3 days
        'is_chronic': False,
        'is_essential_medicine': 'Y',
        'protocol_source': 'NVBDCP Drug Policy 2013 (rev 2019), Section 3.2',
        'notes': 'First-line for PF malaria per NVBDCP. Available as '
                 'AS25+AQ67.5 (child <15kg), AS50+AQ135 (15-35kg), AS100+AQ270 (>35kg). '
                 'DO NOT use as monotherapy — must be given as fixed-dose combination.',
    },
    {
        'disease': 'malaria',
        'sub_condition': 'PF_gametocyte_clearance',
        'drug_name': 'Primaquine',
        'drug_class': '8-aminoquinoline — gametocytocidal (PF single dose)',
        'route': 'oral',
        'formulation': 'tablet',
        'standard_strength_mg': 7.5,
        'adult_dose_mg': 45,                # 0.75 mg/kg single dose = ~45mg for 60kg
        'child_dose_mg_per_kg': 0.75,
        'doses_per_day': 1,
        'treatment_days': 1,
        'tablets_per_case': 6,              # 6 tablets of 7.5mg = 45mg single dose
        'is_chronic': False,
        'is_essential_medicine': 'Y',
        'protocol_source': 'NVBDCP Drug Policy 2013 (rev 2019), Section 3.2',
        'notes': 'Single dose for PF gametocyte clearance (reduces transmission). '
                 'NOT for radical cure. Contraindicated in G6PD deficiency, pregnancy.',
    },
    {
        'disease': 'malaria',
        'sub_condition': 'PF_severe',
        'drug_name': 'Artesunate for Injection',
        'drug_class': 'Parenteral artemisinin — severe malaria',
        'route': 'iv',
        'formulation': 'vial',
        'standard_strength_mg': 60,
        'adult_dose_mg': 168,               # 2.4 mg/kg IV for 70kg patient
        'child_dose_mg_per_kg': 2.4,
        'doses_per_day': 3,                 # 0h, 12h, 24h then once daily
        'treatment_days': 5,
        'tablets_per_case': 9,              # ~9 vials for a 5-day IV course (70kg)
        'is_chronic': False,
        'is_essential_medicine': 'Y',
        'protocol_source': 'NVBDCP Drug Policy 2013, Section 4 (Severe Malaria)',
        'notes': 'WHO recommends over IV Quinine as first-line for severe malaria. '
                 'Switch to oral ACT as soon as patient can tolerate. '
                 'Adjunct: Dextrose infusion (hypoglycaemia common).',
    },
    {
        'disease': 'malaria',
        'sub_condition': 'PF_severe_alternate',
        'drug_name': 'Quinine Dihydrochloride Injection',
        'drug_class': 'Cinchona alkaloid — severe malaria (alternate)',
        'route': 'iv',
        'formulation': 'vial',
        'standard_strength_mg': 300,        # 300mg/mL, 2mL vial = 600mg
        'adult_dose_mg': 1400,              # 20mg/kg loading, then 10mg/kg 8-hourly
        'child_dose_mg_per_kg': 20,
        'doses_per_day': 3,
        'treatment_days': 7,
        'tablets_per_case': 12,             # ~12 vials for full 7-day course
        'is_chronic': False,
        'is_essential_medicine': 'Y',
        'protocol_source': 'NVBDCP Drug Policy 2013, Section 4 (alternate if artesunate unavailable)',
        'notes': 'Use only if IV Artesunate unavailable. '
                 'Risk of hypoglycaemia and cinchonism. '
                 'Must be diluted in Normal Saline/Dextrose for IV.',
    },

    # ══════════════════════════════════════════════════════════════════════════
    # DENGUE — DGHS Clinical Management Guidelines 2021
    # NOTE: No disease-specific drugs exist. Supportive care only.
    # Aspirin/NSAIDs CONTRAINDICATED (risk of haemorrhage).
    # ══════════════════════════════════════════════════════════════════════════
    {
        'disease': 'dengue',
        'sub_condition': 'dengue_all_grades_fever_analgesia',
        'drug_name': 'Paracetamol (Acetaminophen)',
        'drug_class': 'Analgesic-antipyretic — dengue fever management',
        'route': 'oral',
        'formulation': 'tablet',
        'standard_strength_mg': 500,
        'adult_dose_mg': 1000,              # 1g every 6 hours (max 4g/day)
        'child_dose_mg_per_kg': 15,
        'doses_per_day': 4,
        'treatment_days': 7,
        'tablets_per_case': 56,             # 2 tablets × 4 doses × 7 days
        'is_chronic': False,
        'is_essential_medicine': 'Y',
        'protocol_source': 'DGHS Dengue Clinical Management Guidelines 2021, Section 5',
        'notes': 'ONLY safe antipyretic in dengue. '
                 'NSAIDs (ibuprofen, naproxen) and aspirin STRICTLY CONTRAINDICATED '
                 '— risk of dengue haemorrhagic complications. '
                 'Do NOT exceed 4g/day (hepatotoxicity risk).',
    },
    {
        'disease': 'dengue',
        'sub_condition': 'dengue_oral_rehydration',
        'drug_name': 'Oral Rehydration Salts (ORS)',
        'drug_class': 'Electrolyte solution — fluid management',
        'route': 'oral',
        'formulation': 'sachet',
        'standard_strength_mg': 5000,       # 5g sachet (WHO low-osmolarity ORS formula)
        'adult_dose_mg': 5000,
        'child_dose_mg_per_kg': 75,         # 75 mL/kg in first 4 hours (WHO)
        'doses_per_day': 5,                 # 5 sachets/day (each makes 200-250mL)
        'treatment_days': 6,
        'tablets_per_case': 30,             # 5 sachets/day × 6 days
        'is_chronic': False,
        'is_essential_medicine': 'Y',
        'protocol_source': 'DGHS Dengue Guidelines 2021; WHO Dengue Guidelines 2012',
        'notes': 'All dengue patients should be encouraged to drink at least 5 glasses '
                 'of fluids per day (water, ORS, fruit juice, coconut water). '
                 'ORS is first-line for outpatient dengue with warning signs.',
    },
    {
        'disease': 'dengue',
        'sub_condition': 'dengue_haemorrhagic_iv_fluid',
        'drug_name': 'Sodium Chloride 0.9% (Normal Saline)',
        'drug_class': 'Isotonic crystalloid — intravenous fluid replacement',
        'route': 'iv',
        'formulation': 'vial',
        'standard_strength_mg': 500,        # 500mL bag = 4.5g NaCl (for calculations)
        'adult_dose_mg': 2500,              # 5mL/kg/hr for 70kg = 350mL/hr → ~5 bags/24h
        'child_dose_mg_per_kg': 10,
        'doses_per_day': 5,
        'treatment_days': 2,
        'tablets_per_case': 10,             # ~10 × 500mL bags for DHF management
        'is_chronic': False,
        'is_essential_medicine': 'Y',
        'protocol_source': 'DGHS Dengue Guidelines 2021, Sections 7-8 (DHF/DSS management)',
        'notes': 'Only for Grade II-IV dengue (DHF/DSS) requiring hospitalisation. '
                 'Approximately 15-30% of dengue cases progress to DHF. '
                 'Monitor haematocrit closely — over-hydration risk.',
    },

    # ══════════════════════════════════════════════════════════════════════════
    # CHOLERA — IDSP / WHO Treatment Protocol
    # ══════════════════════════════════════════════════════════════════════════
    {
        'disease': 'cholera',
        'sub_condition': 'cholera_rehydration',
        'drug_name': 'Oral Rehydration Salts (ORS)',
        'drug_class': 'Electrolyte solution — primary cholera treatment',
        'route': 'oral',
        'formulation': 'sachet',
        'standard_strength_mg': 5000,
        'adult_dose_mg': 5000,
        'child_dose_mg_per_kg': 75,
        'doses_per_day': 8,                 # 1-2 sachets/hr in acute phase
        'treatment_days': 3,
        'tablets_per_case': 20,             # 20 sachets for adult acute cholera
        'is_chronic': False,
        'is_essential_medicine': 'Y',
        'protocol_source': 'IDSP Cholera Management Protocol; WHO Technical Report 2017',
        'notes': 'ORS is the primary treatment for 80% of cholera cases. '
                 'Severe dehydration requires IV Ringer\'s Lactate (not included separately). '
                 'WHO cholera protocol: 75mL/kg in first 4 hours.',
    },
    {
        'disease': 'cholera',
        'sub_condition': 'cholera_antibiotic',
        'drug_name': 'Doxycycline',
        'drug_class': 'Tetracycline antibiotic — reduces cholera duration',
        'route': 'oral',
        'formulation': 'capsule',
        'standard_strength_mg': 100,
        'adult_dose_mg': 300,               # 300mg single dose (WHO recommendation)
        'child_dose_mg_per_kg': 2,          # 2mg/kg BD × 3 days (in children if >8 years)
        'doses_per_day': 1,
        'treatment_days': 1,
        'tablets_per_case': 3,              # 3 × 100mg capsules single dose
        'is_chronic': False,
        'is_essential_medicine': 'Y',
        'protocol_source': 'IDSP Cholera Protocol; WHO Cholera Factsheet 2023',
        'notes': 'Adjunct to ORS — reduces duration and severity. '
                 'Doxycycline CONTRAINDICATED in children <8 years and pregnancy — '
                 'use Erythromycin or Azithromycin instead. '
                 'Resistance monitoring required; local antibiogram should guide choice.',
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ACUTE DIARRHOEAL DISEASE — IMNCI / National ORS Programme
    # ══════════════════════════════════════════════════════════════════════════
    {
        'disease': 'acute_diarrhoeal_disease',
        'sub_condition': 'diarrhoea_rehydration',
        'drug_name': 'Oral Rehydration Salts (ORS)',
        'drug_class': 'Electrolyte solution — first-line diarrhoea management',
        'route': 'oral',
        'formulation': 'sachet',
        'standard_strength_mg': 5000,
        'adult_dose_mg': 5000,
        'child_dose_mg_per_kg': 75,
        'doses_per_day': 5,
        'treatment_days': 4,
        'tablets_per_case': 15,
        'is_chronic': False,
        'is_essential_medicine': 'Y',
        'protocol_source': 'IMNCI India Adaptation 2017; National ORS Programme MoHFW',
        'notes': 'Universal first-line treatment for all acute diarrhoea. '
                 'Low-osmolarity ORS (245 mOsm/L) recommended by WHO since 2004 — '
                 'reduces need for IV therapy by 33% in children.',
    },
    {
        'disease': 'acute_diarrhoeal_disease',
        'sub_condition': 'diarrhoea_zinc_children',
        'drug_name': 'Zinc Sulfate',
        'drug_class': 'Micronutrient — reduces diarrhoea duration and severity',
        'route': 'oral',
        'formulation': 'tablet',
        'standard_strength_mg': 20,
        'adult_dose_mg': 0,                 # Not for adults per IMNCI
        'child_dose_mg_per_kg': 0,
        'doses_per_day': 1,
        'treatment_days': 14,
        'tablets_per_case': 14,             # 20mg/day × 14 days for children (fixed dose)
        'is_chronic': False,
        'is_essential_medicine': 'Y',
        'protocol_source': 'IMNCI India 2017; WHO/UNICEF Joint Statement on Zinc 2004',
        'notes': 'MANDATORY per IMNCI for all children under 5 with diarrhoea. '
                 'Reduces duration by 25%, severity by 30%. '
                 '<6 months: 10mg/day; ≥6 months: 20mg/day. '
                 'NOT indicated for adults in IMNCI protocol.',
    },

    # ══════════════════════════════════════════════════════════════════════════
    # TUBERCULOSIS — RNTCP/NTP Fixed-Dose Combination (FDC) Regimen
    # New patient (Category I): 2HRZE/4HR
    # ══════════════════════════════════════════════════════════════════════════
    {
        'disease': 'tuberculosis',
        'sub_condition': 'TB_new_case_intensive_phase',
        'drug_name': 'Isoniazid + Rifampicin + Pyrazinamide + Ethambutol FDC',
        'drug_class': 'Anti-TB fixed-dose combination — intensive phase',
        'route': 'oral',
        'formulation': 'tablet',
        'standard_strength_mg': 75,         # H75 + R150 + Z400 + E275 per tablet
        'adult_dose_mg': 300,               # 4 tablets for 55-69kg; weight band average
        'child_dose_mg_per_kg': 0,
        'doses_per_day': 1,
        'treatment_days': 56,               # 2 months intensive phase = 56 days
        'tablets_per_case': 224,            # 4 tablets/day × 56 days (55-69kg weight band)
        'is_chronic': False,
        'is_essential_medicine': 'Y',
        'protocol_source': 'RNTCP/NTP India Technical Guidelines 2016; revised 2020',
        'notes': 'Weight bands: <30kg=2 tabs, 30-54kg=3 tabs, 55-69kg=4 tabs, ≥70kg=5 tabs. '
                 'DOTS strategy — directly observed therapy required. '
                 'Monitor LFT monthly; Ethambutol — check visual acuity monthly. '
                 'Rifampicin turns urine/secretions orange — warn patients.',
    },
    {
        'disease': 'tuberculosis',
        'sub_condition': 'TB_new_case_continuation_phase',
        'drug_name': 'Isoniazid + Rifampicin FDC',
        'drug_class': 'Anti-TB fixed-dose combination — continuation phase',
        'route': 'oral',
        'formulation': 'tablet',
        'standard_strength_mg': 75,         # H75 + R150 per tablet
        'adult_dose_mg': 300,               # 4 tablets for 55-69kg weight band
        'child_dose_mg_per_kg': 0,
        'doses_per_day': 1,
        'treatment_days': 112,              # 4 months continuation phase = 112 days
        'tablets_per_case': 448,            # 4 tablets/day × 112 days
        'is_chronic': False,
        'is_essential_medicine': 'Y',
        'protocol_source': 'RNTCP/NTP India Technical Guidelines 2016; revised 2020',
        'notes': 'Continuation phase follows 2-month intensive phase. '
                 'Total course for new patient: 6 months. '
                 'For retreatment (Cat II): 2HRZES/1HRZE/5HRE — different FDC kits.',
    },

    # ══════════════════════════════════════════════════════════════════════════
    # HYPERTENSION — NPCDCS Standard Treatment Protocols
    # CHRONIC: tablets_per_case = 30-day supply
    # ══════════════════════════════════════════════════════════════════════════
    {
        'disease': 'hypertension',
        'sub_condition': 'HTN_first_line',
        'drug_name': 'Amlodipine',
        'drug_class': 'Calcium Channel Blocker (CCB) — first-line anti-hypertensive',
        'route': 'oral',
        'formulation': 'tablet',
        'standard_strength_mg': 5,
        'adult_dose_mg': 5,                 # 5-10mg once daily; start at 5mg
        'child_dose_mg_per_kg': 0,
        'doses_per_day': 1,
        'treatment_days': 30,               # Chronic — 30-day refill
        'tablets_per_case': 30,             # 1 tablet/day × 30 days
        'is_chronic': True,
        'is_essential_medicine': 'Y',
        'protocol_source': 'NPCDCS Standard Treatment Protocol 2016; JNC 8 Guidelines',
        'notes': 'CHRONIC medication — demand modelled per PREVALENT PATIENT, not case. '
                 'First-line for HTN in India (JNC 8; ESC 2018). '
                 'Well-tolerated; ankle oedema is common side effect. '
                 'Pregnancy: safe in 2nd/3rd trimester (Cat C).',
    },
    {
        'disease': 'hypertension',
        'sub_condition': 'HTN_second_line',
        'drug_name': 'Losartan Potassium',
        'drug_class': 'Angiotensin Receptor Blocker (ARB) — second-line',
        'route': 'oral',
        'formulation': 'tablet',
        'standard_strength_mg': 50,
        'adult_dose_mg': 50,
        'child_dose_mg_per_kg': 0,
        'doses_per_day': 1,
        'treatment_days': 30,
        'tablets_per_case': 30,
        'is_chronic': True,
        'is_essential_medicine': 'Y',
        'protocol_source': 'NPCDCS Standard Treatment Protocol 2016',
        'notes': 'CHRONIC — 30-day supply per patient. '
                 'Preferred in diabetic nephropathy. '
                 'CONTRAINDICATED in pregnancy (teratogenic, Cat D). '
                 'Check serum K+ — risk of hyperkalaemia.',
    },
    {
        'disease': 'hypertension',
        'sub_condition': 'HTN_diuretic_addon',
        'drug_name': 'Hydrochlorothiazide',
        'drug_class': 'Thiazide diuretic — add-on anti-hypertensive',
        'route': 'oral',
        'formulation': 'tablet',
        'standard_strength_mg': 25,
        'adult_dose_mg': 12.5,              # 12.5-25mg once daily
        'child_dose_mg_per_kg': 0,
        'doses_per_day': 1,
        'treatment_days': 30,
        'tablets_per_case': 30,
        'is_chronic': True,
        'is_essential_medicine': 'Y',
        'protocol_source': 'NPCDCS Standard Treatment Protocol 2016',
        'notes': 'CHRONIC — add-on therapy when monotherapy insufficient. '
                 'Used in ~40% of hypertension patients (as combination therapy). '
                 'Monitor electrolytes — risk of hypokalaemia and hyponatraemia.',
    },

    # ══════════════════════════════════════════════════════════════════════════
    # TYPE 2 DIABETES — NPCDCS Standard Treatment Protocols
    # CHRONIC: tablets_per_case = 30-day supply
    # ══════════════════════════════════════════════════════════════════════════
    {
        'disease': 'type2_diabetes',
        'sub_condition': 'T2DM_first_line',
        'drug_name': 'Metformin Hydrochloride',
        'drug_class': 'Biguanide — first-line oral hypoglycaemic',
        'route': 'oral',
        'formulation': 'tablet',
        'standard_strength_mg': 500,
        'adult_dose_mg': 1000,              # 1g twice daily (most common dose)
        'child_dose_mg_per_kg': 0,
        'doses_per_day': 2,
        'treatment_days': 30,
        'tablets_per_case': 120,            # 2 tablets × 2 doses × 30 days
        'is_chronic': True,
        'is_essential_medicine': 'Y',
        'protocol_source': 'NPCDCS Standard Treatment Protocol 2016; ADA Standards 2024',
        'notes': 'CHRONIC — 30-day supply. First-line for ALL T2DM without contraindications. '
                 'Reduces CV mortality (UKPDS). '
                 'CONTRAINDICATED: eGFR <30, liver disease, contrast dye procedures. '
                 'GI side effects — take with food. Start at 500mg OD, titrate up.',
    },
    {
        'disease': 'type2_diabetes',
        'sub_condition': 'T2DM_sulfonylurea',
        'drug_name': 'Glibenclamide (Glyburide)',
        'drug_class': 'Sulfonylurea — insulin secretagogue',
        'route': 'oral',
        'formulation': 'tablet',
        'standard_strength_mg': 5,
        'adult_dose_mg': 5,                 # 5-15mg/day with breakfast
        'child_dose_mg_per_kg': 0,
        'doses_per_day': 1,
        'treatment_days': 30,
        'tablets_per_case': 30,
        'is_chronic': True,
        'is_essential_medicine': 'Y',
        'protocol_source': 'NPCDCS Standard Treatment Protocol 2016; India EDL 2022',
        'notes': 'CHRONIC. Second-line or combination with Metformin. '
                 'HIGH hypoglycaemia risk — educate patients. '
                 'Avoid in elderly (long half-life, prolonged hypoglycaemia risk). '
                 'Contraindicated in renal impairment.',
    },
    {
        'disease': 'type2_diabetes',
        'sub_condition': 'T2DM_insulin',
        'drug_name': 'Human Insulin NPH (Intermediate-acting)',
        'drug_class': 'Insulin — pancreatic hormone replacement',
        'route': 'subcutaneous',
        'formulation': 'vial',
        'standard_strength_mg': 10,         # 10 mL vial = 1000 IU (100 IU/mL)
        'adult_dose_mg': 40,                # ~40 IU/day (range 20-80 IU depending on BMI)
        'child_dose_mg_per_kg': 0,
        'doses_per_day': 1,
        'treatment_days': 30,
        'tablets_per_case': 1,              # ~1.2 vials/month (40 IU/day × 30 = 1200 IU)
        'is_chronic': True,
        'is_essential_medicine': 'Y',
        'protocol_source': 'NPCDCS 2016; India EDL 2022; ADA 2024',
        'notes': 'CHRONIC. Required by ~20-25% of T2DM patients (ICMR INDIAB survey). '
                 'Cold chain storage mandatory (2-8°C). '
                 'Requires insulin syringes (separately stocked). '
                 'Dose titrated by fasting blood glucose — not fixed.',
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ANAEMIA — National Iron+ Initiative / NFHS-5 Treatment Guidelines
    # CHRONIC: tablets_per_case = 30-day supply
    # ══════════════════════════════════════════════════════════════════════════
    {
        'disease': 'anaemia',
        'sub_condition': 'anaemia_iron_deficiency_oral',
        'drug_name': 'Ferrous Sulfate + Folic Acid (IFA)',
        'drug_class': 'Iron supplement + haematinic — first-line anaemia treatment',
        'route': 'oral',
        'formulation': 'tablet',
        'standard_strength_mg': 60,         # 60mg elemental iron + 0.5mg folic acid (IFA Red)
        'adult_dose_mg': 120,               # 2 tablets/day (120mg elemental iron for treatment)
        'child_dose_mg_per_kg': 3,          # 3mg/kg elemental iron per day for children
        'doses_per_day': 2,
        'treatment_days': 90,               # 3-month treatment course for iron deficiency
        'tablets_per_case': 180,            # 2 tablets/day × 90 days
        'is_chronic': True,
        'is_essential_medicine': 'Y',
        'protocol_source': 'National Iron+ Initiative MoHFW 2013; NFHS-5 treatment arm',
        'notes': 'Standard IFA RED tablet (60mg Fe + 0.5mg FA) for treatment. '
                 'IFA BLUE (100mg Fe + 0.5mg FA) for pregnant women. '
                 'Take with Vitamin C (lemon juice) — improves absorption. '
                 'Avoid with milk, tea, coffee — reduce absorption by 40-70%. '
                 'Prevention dose (WIFS): 1 tablet/week for adolescent girls.',
    },
    {
        'disease': 'anaemia',
        'sub_condition': 'anaemia_severe_iv_iron',
        'drug_name': 'Ferric Carboxymaltose Injection',
        'drug_class': 'IV iron complex — severe or non-responsive iron deficiency',
        'route': 'iv',
        'formulation': 'vial',
        'standard_strength_mg': 500,        # 500mg/10mL vial
        'adult_dose_mg': 500,
        'child_dose_mg_per_kg': 15,
        'doses_per_day': 1,
        'treatment_days': 1,
        'tablets_per_case': 2,              # Typically 1-2 infusions (1000mg total dose)
        'is_chronic': False,
        'is_essential_medicine': 'N',       # Not on WHO EML but on India EDL 2022
        'protocol_source': 'India EDL 2022; ICMR Guidelines for IDA 2020',
        'notes': 'For Hb <7g/dL unresponsive to oral iron, or pre-surgery. '
                 'Faster repletion than oral iron (days vs weeks). '
                 'Administer over 15 min IV infusion — observe for anaphylaxis. '
                 'Approximately 10-15% of diagnosed anaemia cases require IV iron.',
    },
]

# ─── Write CSV ──────────────────────────────────────────────────────────────
FIELDNAMES = [
    'disease', 'sub_condition', 'drug_name', 'drug_class',
    'route', 'formulation', 'standard_strength_mg',
    'adult_dose_mg', 'child_dose_mg_per_kg',
    'doses_per_day', 'treatment_days', 'tablets_per_case',
    'is_chronic', 'is_essential_medicine', 'protocol_source', 'notes',
]

with open(OUT, 'w', newline='', encoding='utf-8') as fh:
    writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
    writer.writeheader()
    writer.writerows(ROWS)

print("=" * 65)
print("  Pharmasense - Fix 2: Disease-Drug Mapping Table")
print("=" * 65)
print(f"\n[OK] Written {len(ROWS)} drug mappings to:")
print(f"     {OUT}")
print()

# ─── Summary ────────────────────────────────────────────────────────────────
from collections import Counter
by_disease = Counter(r['disease'] for r in ROWS)
print("Mappings per disease:")
for disease, count in sorted(by_disease.items()):
    acute = [r for r in ROWS if r['disease'] == disease and not r['is_chronic']]
    chronic = [r for r in ROWS if r['disease'] == disease and r['is_chronic']]
    print(f"  {disease}: {count} drugs ({len(acute)} acute, {len(chronic)} chronic)")

essential = sum(1 for r in ROWS if r['is_essential_medicine'] == 'Y')
print(f"\nTotal: {len(ROWS)} drug entries | {essential} on WHO/India Essential Medicines List")
print("\nFix 2 COMPLETE - LightGBM demand model is now unblocked for training.")
