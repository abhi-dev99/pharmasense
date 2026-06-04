"""
Phase 0 Extension — Symptomatic & Essential Condition Demand Pipeline
=====================================================================
Covers 7 additional condition types omitted from Phase 0 NCD pipeline.

METHODOLOGY: Morbidity-Based Quantification (MBQ) — same method used by GoI/NHM
for annual drug procurement planning. Rates sourced from authoritative publications:

  Condition                 | Primary Source
  --------------------------|---------------------------------------------------------
  viral_fever_urti          | NSSO 75th Round (2017-18) Schedule 25.0; WHO India 2023
  acute_gastritis_dyspepsia | NSSO 75th Round (GI ailment share 8%); ICMR GBD India
  musculoskeletal_pain      | GBD 2019 India (LBP 7.1%, arthritis 5.5%, headache 39%)
  asthma_copd_respiratory   | GBD 2019 India (asthma 3.5%, COPD 7.4% of adults ≥40)
  helminth_infestation      | WHO NTD India 2022; National Deworming Programme data
  uti_bacterial_infections  | ICMR AMR Surveillance Network 2017-2023
  maternal_anc_supplements  | NFHS-5 (2019-21); SRS 2020 Crude Birth Rate = 19.7/1000

NOTE ON RELIABILITY:
  These are population-level planning priors, not ground-truth. For chronic NCDs
  (HTN, T2DM, TB, Anaemia) the NFHS-5 rates are from a validated 636,699-household
  survey — high confidence. For symptomatic acute conditions, rates are from cross-
  sectional surveys and GBD modelling — confidence is moderate. In a production
  system these would be replaced by actual HMIS consumption data as it accumulates.
  GoI/NHM uses MBQ for ALL conditions as the standard cold-start method.

TIME SERIES: 2018-W01 through 2024-W52 (same as NCD pipeline)
SCHEMA: Extends ncd_demand_weekly table (drops and recreates CHECK constraint)

Usage: python data/scripts/08_seed_symptomatic_pipeline.py --db-password pharmasons99lite
"""

import sys, os, argparse, math, json, random
from pathlib import Path
from datetime import date, timedelta

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
import psycopg2, psycopg2.extras
import numpy as np

random.seed(99)
np.random.seed(99)

# ─── NSSO 75th Round (2017-18) — Total OPD ailment rate ──────────────────────
# Source: MoSPI, Government of India, NSSO 75th Round Report (2019)
# "Key Indicators of Social Consumption in India: Health"
# Table 5.2: Ailment rate per 1000 persons per 15 days (rural+urban combined)
# National average: 89 per 1000 per 15 days
# Treatment-seeking (OPD) rate: 77% of ailment episodes seek formal care
# Annual OPD episodes per person = (89/1000) × 24 fortnights × 0.77 = 1.644

NSSO_ANNUAL_OPD_EPISODES = 1.644  # per person per year

# Disease share of total OPD visits (NSSO 75th Round, Table 5.3 + WHO India)
DISEASE_SHARE_OF_OPD = {
    "viral_fever_urti":          0.228,   # fever+cold+URTI = largest single category (~22.8%)
    "acute_gastritis_dyspepsia": 0.082,   # GI complaints (acidity, dyspepsia, nausea) = 8.2%
    "musculoskeletal_pain":      0.071,   # arthritis, LBP, body ache, headache = 7.1%
    "asthma_copd_respiratory":   0.000,   # handled separately via GBD prevalence, not OPD share
    "helminth_infestation":      0.000,   # handled separately via NDP coverage data
    "uti_bacterial_infections":  0.050,   # UTI + skin/wound/RTI = 5.0%
    "maternal_anc_supplements":  0.000,   # handled separately via birth rate
}

# ─── GBD 2019 India — Chronic Respiratory Disease Prevalence ─────────────────
# Source: GBD 2019 Diseases and Injuries Collaborators, Lancet 2020
# India-specific: Institute for Health Metrics and Evaluation (IHME) GBD Compare
# Asthma age-standardized prevalence: 3.47% (all ages)
# COPD age-standardized prevalence: 7.46% (adults ≥40, India 2019)
# Weighted to total population (≥40 = ~38% of India pop by Census 2011):
# Effective treatment-seeking prevalence ≈ 0.0347 × 0.50 + 0.38 × 0.0746 × 0.50 = 3.13%
# Treatment coverage (on regular medication): 50% (many self-treat or use home remedies)
ASTHMA_COPD_PREVALENCE_RATE = 0.0313  # fraction of total population on regular treatment
ASTHMA_COPD_TREATMENT_COV   = 0.50

# ─── WHO NTD India / National Deworming Programme ────────────────────────────
# Source: WHO Preventive Chemotherapy Data Portal (2022)
# National Deworming Day (NDD) India: biannual (Feb + Aug)
# Target population: children 1–19 years (school + anganwadi)
# India children 1-19 = 37% of population (Census 2011)
# NDD coverage: 76% of targeted children (MoHFW NDD Coverage Report 2021-22)
# Adults in endemic areas also eligible (additionally ~15% of adult population annually)
# Doses: Single dose albendazole 400mg per child per round
HELMINTH_CHILD_POP_FRACTION = 0.37
HELMINTH_NDD_COVERAGE       = 0.76
HELMINTH_NDD_ROUNDS_PER_YEAR = 2
# Demand concentrated in Feb (weeks 5-7) and Aug (weeks 30-32)
HELMINTH_PEAK_WEEKS = {5, 6, 7, 30, 31, 32}

# ─── ICMR AMR Surveillance + NSSO — Bacterial Infections ─────────────────────
# Source: ICMR Annual Report on Antimicrobial Resistance Surveillance 2023
# Community-acquired UTI: ~5% of women per year, ~1% of men → weighted 3% of adults
# Skin/soft tissue infections: ~2% of adults seek OPD care annually
# Acute RTI requiring antibiotics: ~3% of adults annually
# Total OPD-seeking bacterial infection episodes: 5% of population per year
# Treatment coverage: ~70% of those seeking care receive antibiotics
UTI_BACTERIAL_INFECTION_RATE = 0.050
UTI_BACTERIAL_TREATMENT_COV  = 0.70

# ─── NFHS-5 / SRS 2020 — Maternal ANC Supplements ───────────────────────────
# Source: Sample Registration System (SRS) Statistical Report 2020, RGI India
# Crude Birth Rate: 19.7 per 1000 population
# At any given week, pregnant women ≈ CBR × (40 weeks gestation / 52 weeks) = 15.15/1000
# ANC registration: 90% in most states, use 85% as national weighted average
# Calcium supplementation: recommended from 14 weeks, so covers ~65% of pregnancy
# Vitamin D: recommended but lower coverage, use 40%
MATERNAL_BIRTH_RATE     = 0.0197   # per person per year
MATERNAL_ANC_FRACTION   = 40 / 52  # fraction of year that's pregnancy
MATERNAL_ANC_COVERAGE   = 0.85
MATERNAL_CALCIUM_COV    = 0.65     # fraction of pregnant women receiving calcium
MATERNAL_VITD_COV       = 0.40     # fraction of pregnant women receiving Vit D

# ─── Drug demand per episode/patient ─────────────────────────────────────────
# Units = individual tablets/sachets/units per patient per week
# Source: WHO Model Formulary; ICMR Standard Treatment Workflows (STWs) 2016-2023
WEEKLY_DRUG_UNITS = {
    "viral_fever_urti": [
        # Paracetamol 500mg: 3 tabs/day × 5 days → 15 tabs per episode
        # Duration ~5 days, each episode costs 15 tabs, weekly patient demand at peak = 3 tabs/week average
        ("paracetamol_500mg",       3),    # avg weekly use (3/day × 5 days / 5 day episode)
        ("cetirizine_10mg",         1),    # 1 tab/day × 5 days → avg 1/week during episode
    ],
    "acute_gastritis_dyspepsia": [
        ("pantoprazole_40mg",       7),    # 1 tab/day standard 7-14 day course
        ("antacid_suspension",      1),    # 1 bottle per episode (symptomatic relief)
    ],
    "musculoskeletal_pain": [
        ("ibuprofen_400mg",        14),    # 2 tabs/day chronic patients (LBP/arthritis)
        ("diclofenac_50mg",         7),    # 1 tab/day alternate analgesic
    ],
    "asthma_copd_respiratory": [
        ("salbutamol_inhaler_100mcg", 0.13),  # 1 inhaler/100-200 puffs; 2-4 puffs/day → 0.125-0.25/wk
        ("budesonide_200mcg_inhaler", 0.08),  # 1 inhaler/60 actuations; 2/day → 0.23/wk; only 40% on ICS
    ],
    "helminth_infestation": [
        ("albendazole_400mg",       0.08), # biannual dosing: 2 doses/year / 52 weeks = 0.038; plus ~2x for stock
    ],
    "uti_bacterial_infections": [
        ("ciprofloxacin_500mg",    14),    # 2 tabs/day × 7 days = 14 tabs per episode
        ("amoxicillin_500mg",      21),    # 3 tabs/day × 7 days = 21 per episode
        ("cotrimoxazole_480mg",    10),    # 2 tabs/day × 5 days = 10 per episode
    ],
    "maternal_anc_supplements": [
        ("calcium_carbonate_500mg", 14),   # 2 tabs/day during pregnancy
        ("vitamin_d3_60kiu",        0.25), # monthly sachet → 0.25/week
    ],
}

# ─── State-level modifiers (NSSO region-level OPD utilisation, Table 5.4) ────
# Source: NSSO 75th Round — OPD ailment rate varies significantly by state
# These are relative multipliers (1.0 = national average)
# Higher in southern states (better healthcare access/seeking) and urban states
STATE_OPD_UTILISATION_MULTIPLIER = {
    "Kerala":          1.52,   # highest healthcare access + seeking in India
    "Tamil Nadu":      1.28,
    "Karnataka":       1.14,
    "Andhra Pradesh":  1.09,
    "Telangana":       1.07,
    "Goa":             1.19,
    "Maharashtra":     1.08,
    "Gujarat":         0.98,
    "Delhi":           1.31,
    "Chandigarh":      1.24,
    "Punjab":          1.18,
    "Haryana":         1.05,
    "Himachal Pradesh":1.12,
    "Rajasthan":       0.82,
    "Madhya Pradesh":  0.76,
    "Uttar Pradesh":   0.71,   # lowest OPD utilisation (access constraints)
    "Bihar":           0.69,
    "Jharkhand":       0.73,
    "Odisha":          0.88,
    "West Bengal":     1.02,
    "Assam":           0.91,
    "Chhattisgarh":    0.80,
    "Uttarakhand":     1.01,
    "Jammu & Kashmir": 1.03,
    "Sikkim":          1.09,
    "Manipur":         0.94,
    "Meghalaya":       0.85,
    "Mizoram":         0.97,
    "Nagaland":        0.88,
    "Tripura":         0.92,
    "Arunachal Pradesh":0.80,
    "_default":        1.00,
}

# ─── Seasonal multipliers per condition ──────────────────────────────────────
# Source: NSSO 75th Round Table 5.5 (seasonal ailment distribution);
#         IMD seasonal disease correlation studies;
#         NCDC India surveillance reports
def get_seasonal_mult(condition: str, week_date: date) -> float:
    month = week_date.month
    week  = week_date.isocalendar()[1]

    if condition == "viral_fever_urti":
        # Two peaks: monsoon season (Jul-Sep, dengue + viral fever) and winter (Nov-Jan, URTI/flu)
        # Source: NCDC ILI surveillance, 2015-2022
        # Peak monsoon: month 7-9 (mult ~1.35)
        # Peak winter: month 11-1 (mult ~1.25)
        # Trough: April-May (pre-monsoon dry season, mult ~0.75)
        angle_monsoon = 2 * math.pi * (month - 8) / 12   # centered on Aug
        angle_winter  = 2 * math.pi * (month - 12) / 12  # centered on Dec
        monsoon_comp  = 0.175 * math.cos(angle_monsoon)
        winter_comp   = 0.130 * math.cos(angle_winter)
        return max(0.60, min(1.50, 1.0 + monsoon_comp + winter_comp))

    elif condition == "acute_gastritis_dyspepsia":
        # Slightly elevated in summer (spicy food, dehydration) and festival seasons (Oct-Nov)
        # Relatively flat; mild peak in summer months (Apr-Jun)
        angle = 2 * math.pi * (month - 5) / 12   # centered on May
        return max(0.85, min(1.20, 1.0 + 0.10 * math.cos(angle)))

    elif condition == "musculoskeletal_pain":
        # Peaks in winter: cold exacerbates arthritis, LBP, joint pain
        # Source: Arthritis Foundation India, seasonal OPD data
        angle = 2 * math.pi * (month - 1) / 12   # centered on Jan
        return max(0.80, min(1.30, 1.0 + 0.18 * math.cos(angle)))

    elif condition == "asthma_copd_respiratory":
        # Strong winter peak (Oct-Feb): cold air triggers bronchospasm; pollution peaks
        # Strong monsoon trough (Jun-Aug): humidity reduces allergen loads
        # Source: GBD 2019 India respiratory disease seasonality supplement
        angle = 2 * math.pi * (month - 12) / 12  # centered on Dec
        return max(0.65, min(1.45, 1.0 + 0.30 * math.cos(angle)))

    elif condition == "helminth_infestation":
        # Biannual pulse — National Deworming Day (NDD): Feb (W6-7) and Aug (W30-32)
        # Demand spikes massively in those 2 weeks, then flat for rest of year
        # Regular non-NDD demand: low background (~20% of NDD peak)
        if week in HELMINTH_PEAK_WEEKS:
            return 5.0   # 5x the base rate during NDD weeks (stocking for mass distribution)
        else:
            return 0.20  # background rate (private sector + catch-up doses)

    elif condition == "uti_bacterial_infections":
        # UTI peaks in summer (dehydration, heat); RTI peaks in winter; skin infections year-round
        # Net effect: moderate summer peak
        angle = 2 * math.pi * (month - 6) / 12   # centered on Jun
        return max(0.80, min(1.25, 1.0 + 0.15 * math.cos(angle)))

    elif condition == "maternal_anc_supplements":
        # No seasonal variation (conception is year-round; supplements needed throughout pregnancy)
        return 1.0

    return 1.0


# ─── DB connection (direct, port 5432 — fine for local scripts) ──────────────
def get_conn(password: str):
    url = os.getenv("SUPABASE_URL", "")
    ref = url.replace("https://", "").split(".")[0]
    return psycopg2.connect(
        host=f"db.{ref}.supabase.co", port=5432, dbname="postgres",
        user="postgres", password=password, sslmode="require", connect_timeout=30
    )


# ─── Step 1: Expand ncd_demand_weekly CHECK constraint ───────────────────────
def expand_check_constraint(cur):
    print("\n[1/4] Expanding ncd_demand_weekly CHECK constraint...")
    # Drop existing constraint (name from schema.sql)
    cur.execute("""
        ALTER TABLE ncd_demand_weekly
        DROP CONSTRAINT IF EXISTS ncd_demand_weekly_ncd_type_check;
    """)
    # Recreate with all condition types
    cur.execute("""
        ALTER TABLE ncd_demand_weekly
        ADD CONSTRAINT ncd_demand_weekly_ncd_type_check
        CHECK (ncd_type IN (
            'hypertension', 'type2_diabetes', 'tuberculosis', 'anaemia',
            'viral_fever_urti', 'acute_gastritis_dyspepsia', 'musculoskeletal_pain',
            'asthma_copd_respiratory', 'helminth_infestation', 'uti_bacterial_infections',
            'maternal_anc_supplements'
        ));
    """)
    print("[OK] CHECK constraint updated to include 7 new condition types")


# ─── Step 2: Generate symptomatic demand time series ────────────────────────
def generate_symptomatic_demand(cur):
    print("\n[2/4] Generating symptomatic demand time series (2018–2024)...")

    cur.execute("SELECT id, state, population FROM districts;")
    districts = {row[0]: {"state": row[1], "pop": row[2] or 50000} for row in cur.fetchall()}

    # Generate all weeks 2018-W01 through 2024-W52
    start = date(2018, 1, 1)
    end   = date(2024, 12, 31)
    weeks = []
    d = start
    while d <= end:
        iso = d.isocalendar()
        weeks.append((d, f"{iso[0]}-W{iso[1]:02d}"))
        d += timedelta(weeks=1)

    CONDITIONS = [
        "viral_fever_urti", "acute_gastritis_dyspepsia", "musculoskeletal_pain",
        "asthma_copd_respiratory", "helminth_infestation", "uti_bacterial_infections",
        "maternal_anc_supplements",
    ]

    print(f"     Weeks: {len(weeks)}  |  Districts: {len(districts)}  |  Conditions: {len(CONDITIONS)}")
    print(f"     Estimated records: ~{len(weeks) * len(districts) * len(CONDITIONS):,}")

    # Annual trend: symptomatic OPD visits growing ~2%/year (urbanisation + access)
    BASE_YEAR = 2018
    def trend_mult(week_date):
        years = (week_date.year - BASE_YEAR) + week_date.month / 12
        return 1.02 ** years

    records = []
    BATCH   = 2000
    total   = 0

    for dist_id, dinfo in districts.items():
        pop   = dinfo["pop"]
        state = dinfo["state"] or "_default"
        util  = STATE_OPD_UTILISATION_MULTIPLIER.get(state, STATE_OPD_UTILISATION_MULTIPLIER["_default"])

        for cond in CONDITIONS:
            # ── Base patients per week ─────────────────────────────────────────
            if cond in DISEASE_SHARE_OF_OPD and DISEASE_SHARE_OF_OPD[cond] > 0:
                # OPD-share-based conditions
                annual_episodes = pop * NSSO_ANNUAL_OPD_EPISODES * DISEASE_SHARE_OF_OPD[cond] * util
                base_patients   = annual_episodes / 52.0

            elif cond == "asthma_copd_respiratory":
                # GBD prevalence-based
                base_patients = pop * ASTHMA_COPD_PREVALENCE_RATE * ASTHMA_COPD_TREATMENT_COV

            elif cond == "helminth_infestation":
                # NDD coverage: 2 rounds/year × pop × child_fraction × NDD_coverage
                annual_doses  = pop * HELMINTH_CHILD_POP_FRACTION * HELMINTH_NDD_COVERAGE * HELMINTH_NDD_ROUNDS_PER_YEAR
                base_patients = annual_doses / 52.0

            elif cond == "uti_bacterial_infections":
                # ICMR AMR-based
                base_patients = pop * UTI_BACTERIAL_INFECTION_RATE * UTI_BACTERIAL_TREATMENT_COV / 52.0

            elif cond == "maternal_anc_supplements":
                # Birth rate × gestation fraction × ANC coverage
                pregnant_women_this_week = pop * MATERNAL_BIRTH_RATE * MATERNAL_ANC_FRACTION * MATERNAL_ANC_COVERAGE
                base_patients = pregnant_women_this_week  # all get some supplements

            else:
                continue

            # Primary drug units per patient per week
            primary_drug = WEEKLY_DRUG_UNITS[cond][0]  # (drug_name, units_per_patient_per_week)
            units_per_pt = primary_drug[1]

            for (wdate, iso_week) in weeks:
                s_mult = get_seasonal_mult(cond, wdate)
                t_mult = trend_mult(wdate)
                # Noise: tighter range (±5%) — symptomatic demand more predictable than epidemic
                noise  = 1 + np.random.normal(0, 0.05)
                noise  = max(0.85, min(1.20, noise))

                patients = max(0, int(base_patients * s_mult * t_mult * noise))
                demand   = max(0, int(patients * units_per_pt))

                records.append((
                    dist_id, cond, iso_week, str(wdate),
                    pop, patients, demand, 0.0,  # prevalence_rate = 0 (episode-based, not prevalence)
                ))

                if len(records) >= BATCH:
                    _flush(cur, records)
                    total += len(records)
                    records = []

    if records:
        _flush(cur, records)
        total += len(records)

    print(f"\n[OK] Symptomatic demand records inserted: {total:,}")

    # Summary
    cur.execute("""
        SELECT ncd_type, COUNT(*), SUM(patients_est), SUM(demand_units)
        FROM ncd_demand_weekly
        WHERE ncd_type IN (
            'viral_fever_urti','acute_gastritis_dyspepsia','musculoskeletal_pain',
            'asthma_copd_respiratory','helminth_infestation','uti_bacterial_infections',
            'maternal_anc_supplements'
        )
        GROUP BY 1 ORDER BY 2 DESC;
    """)
    rows = cur.fetchall()
    print(f"\n  {'Condition':<35} {'Weeks':>8} {'Est Patients':>15} {'Drug Units':>12}")
    print(f"  {'-'*73}")
    for row in rows:
        print(f"  {row[0]:<35} {row[1]:>8,} {row[2]:>15,} {row[3]:>12,}")


def _flush(cur, records):
    psycopg2.extras.execute_batch(cur, """
        INSERT INTO ncd_demand_weekly
            (district_id, ncd_type, iso_week, week_start_date,
             district_pop, patients_est, demand_units, prevalence_rate)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (district_id, ncd_type, iso_week) DO UPDATE SET
            patients_est=EXCLUDED.patients_est,
            demand_units=EXCLUDED.demand_units;
    """, records, page_size=500)


# ─── Step 3: Seed missing essential drugs ────────────────────────────────────
SYMPTOMATIC_DRUGS = [
    # ── Fever / Pain / Antipyretic ──────────────────────────────────────────
    # Paracetamol 500mg ORAL tablet — THE most prescribed drug in India.
    # NOTE: 05_seed_critical_drugs.py added paracetamol IV (1g/100ml) for inpatient use.
    # This adds the oral tablet for OPD/community prescriptions.
    {"name": "Paracetamol 500mg Tablet",
     "generic_name": "paracetamol", "dose_mg": 500.0, "formulation_type": "tablet",
     "pack_size_units": 30, "price_inr": 14.0,
     "icmr_diseases": ["dengue", "malaria", "viral_fever_urti", "acute_diarrhoeal_disease"]},

    {"name": "Ibuprofen 400mg Tablet",
     "generic_name": "ibuprofen", "dose_mg": 400.0, "formulation_type": "tablet",
     "pack_size_units": 30, "price_inr": 22.0,
     "icmr_diseases": ["musculoskeletal_pain", "viral_fever_urti"]},

    {"name": "Diclofenac Sodium 50mg Tablet",
     "generic_name": "diclofenac", "dose_mg": 50.0, "formulation_type": "tablet",
     "pack_size_units": 30, "price_inr": 18.0,
     "icmr_diseases": ["musculoskeletal_pain"]},

    {"name": "Cetirizine Hydrochloride 10mg Tablet",
     "generic_name": "cetirizine", "dose_mg": 10.0, "formulation_type": "tablet",
     "pack_size_units": 30, "price_inr": 16.0,
     "icmr_diseases": ["viral_fever_urti"]},

    # ── Gastric / GI ────────────────────────────────────────────────────────
    {"name": "Pantoprazole 40mg Gastro-resistant Tablet",
     "generic_name": "pantoprazole", "dose_mg": 40.0, "formulation_type": "tablet",
     "pack_size_units": 14, "price_inr": 28.0,
     "icmr_diseases": ["acute_gastritis_dyspepsia"]},

    {"name": "Omeprazole 20mg Capsule",
     "generic_name": "omeprazole", "dose_mg": 20.0, "formulation_type": "capsule",
     "pack_size_units": 14, "price_inr": 22.0,
     "icmr_diseases": ["acute_gastritis_dyspepsia"]},

    {"name": "Antacid Suspension 200ml (Magaldrate + Simethicone)",
     "generic_name": "magaldrate simethicone", "dose_mg": None, "formulation_type": "oral_solution",
     "pack_size_units": 1, "price_inr": 45.0,
     "icmr_diseases": ["acute_gastritis_dyspepsia"]},

    # Zinc 20mg for diarrhoea co-management (WHO/UNICEF recommended alongside ORS)
    {"name": "Zinc Sulphate 20mg Tablet (Dispersible)",
     "generic_name": "zinc sulphate", "dose_mg": 20.0, "formulation_type": "tablet",
     "pack_size_units": 14, "price_inr": 12.0,
     "icmr_diseases": ["acute_diarrhoeal_disease", "cholera"]},

    # Metronidazole 400mg tablet (oral; IV already seeded in script 05)
    {"name": "Metronidazole 400mg Tablet",
     "generic_name": "metronidazole", "dose_mg": 400.0, "formulation_type": "tablet",
     "pack_size_units": 20, "price_inr": 18.0,
     "icmr_diseases": ["acute_diarrhoeal_disease", "acute_gastritis_dyspepsia"]},

    # ── Antibiotics (oral, community-level) ─────────────────────────────────
    {"name": "Amoxicillin 500mg Capsule",
     "generic_name": "amoxicillin", "dose_mg": 500.0, "formulation_type": "capsule",
     "pack_size_units": 21, "price_inr": 38.0,
     "icmr_diseases": ["uti_bacterial_infections", "viral_fever_urti"]},

    {"name": "Co-trimoxazole 480mg Tablet (Trimethoprim + Sulfamethoxazole)",
     "generic_name": "trimethoprim sulfamethoxazole", "dose_mg": 480.0, "formulation_type": "tablet",
     "pack_size_units": 10, "price_inr": 14.0,
     "icmr_diseases": ["uti_bacterial_infections"]},

    {"name": "Ciprofloxacin 500mg Tablet",
     "generic_name": "ciprofloxacin", "dose_mg": 500.0, "formulation_type": "tablet",
     "pack_size_units": 14, "price_inr": 32.0,
     "icmr_diseases": ["uti_bacterial_infections", "acute_diarrhoeal_disease", "cholera"]},

    {"name": "Doxycycline Hyclate 100mg Capsule",
     "generic_name": "doxycycline", "dose_mg": 100.0, "formulation_type": "capsule",
     "pack_size_units": 10, "price_inr": 25.0,
     "icmr_diseases": ["uti_bacterial_infections", "cholera", "malaria"]},

    {"name": "Amoxicillin + Clavulanate 625mg Tablet",
     "generic_name": "amoxicillin clavulanate", "dose_mg": 625.0, "formulation_type": "tablet",
     "pack_size_units": 10, "price_inr": 118.0,
     "icmr_diseases": ["uti_bacterial_infections"]},

    # ── Respiratory / Asthma / COPD ─────────────────────────────────────────
    {"name": "Salbutamol 100mcg Metered Dose Inhaler 200 doses",
     "generic_name": "salbutamol", "dose_mg": 0.1, "formulation_type": "other",
     "pack_size_units": 1, "price_inr": 82.0,
     "icmr_diseases": ["asthma_copd_respiratory"]},

    {"name": "Salbutamol Nebulizer Solution 5mg/ml 5ml",
     "generic_name": "salbutamol", "dose_mg": 5.0, "formulation_type": "oral_solution",
     "pack_size_units": 5, "price_inr": 22.0,
     "icmr_diseases": ["asthma_copd_respiratory"]},

    {"name": "Budesonide 200mcg Metered Dose Inhaler 200 doses",
     "generic_name": "budesonide", "dose_mg": 0.2, "formulation_type": "other",
     "pack_size_units": 1, "price_inr": 198.0,
     "icmr_diseases": ["asthma_copd_respiratory"]},

    {"name": "Aminophylline 100mg Tablet",
     "generic_name": "aminophylline", "dose_mg": 100.0, "formulation_type": "tablet",
     "pack_size_units": 30, "price_inr": 28.0,
     "icmr_diseases": ["asthma_copd_respiratory"]},

    # ── Antiparasitic / Deworming ────────────────────────────────────────────
    {"name": "Albendazole 400mg Chewable Tablet",
     "generic_name": "albendazole", "dose_mg": 400.0, "formulation_type": "tablet",
     "pack_size_units": 1, "price_inr": 3.5,
     "icmr_diseases": ["helminth_infestation"]},

    {"name": "Mebendazole 500mg Tablet",
     "generic_name": "mebendazole", "dose_mg": 500.0, "formulation_type": "tablet",
     "pack_size_units": 1, "price_inr": 4.5,
     "icmr_diseases": ["helminth_infestation"]},

    {"name": "Ivermectin 12mg Tablet",
     "generic_name": "ivermectin", "dose_mg": 12.0, "formulation_type": "tablet",
     "pack_size_units": 1, "price_inr": 12.0,
     "icmr_diseases": ["helminth_infestation"]},

    # ── Maternal / ANC Supplements ───────────────────────────────────────────
    # IFA (Iron + Folic Acid) already in NCD pipeline — do not re-add
    {"name": "Calcium Carbonate 500mg Tablet",
     "generic_name": "calcium carbonate", "dose_mg": 500.0, "formulation_type": "tablet",
     "pack_size_units": 30, "price_inr": 12.0,
     "icmr_diseases": ["maternal_anc_supplements"]},

    {"name": "Vitamin D3 60000 IU Sachet",
     "generic_name": "cholecalciferol", "dose_mg": 60000.0, "formulation_type": "sachet",
     "pack_size_units": 4, "price_inr": 85.0,
     "icmr_diseases": ["maternal_anc_supplements"]},

    {"name": "Calcium Carbonate + Vitamin D3 Tablet",
     "generic_name": "calcium carbonate cholecalciferol", "dose_mg": 500.0, "formulation_type": "tablet",
     "pack_size_units": 30, "price_inr": 22.0,
     "icmr_diseases": ["maternal_anc_supplements"]},

    # ── Skin / Fungal ────────────────────────────────────────────────────────
    {"name": "Clotrimazole 1% Cream 15g",
     "generic_name": "clotrimazole", "dose_mg": 10.0, "formulation_type": "topical",
     "pack_size_units": 1, "price_inr": 28.0,
     "icmr_diseases": []},

    {"name": "Permethrin 5% Cream 30g",
     "generic_name": "permethrin", "dose_mg": 50.0, "formulation_type": "topical",
     "pack_size_units": 1, "price_inr": 48.0,
     "icmr_diseases": []},

    {"name": "Whitfield's Ointment 25g (Benzoic Acid + Salicylic Acid)",
     "generic_name": "benzoic acid salicylic acid", "dose_mg": None, "formulation_type": "topical",
     "pack_size_units": 1, "price_inr": 18.0,
     "icmr_diseases": []},

    # ── Thyroid ─────────────────────────────────────────────────────────────
    {"name": "Levothyroxine Sodium 50mcg Tablet",
     "generic_name": "levothyroxine", "dose_mg": 50.0, "formulation_type": "tablet",
     "pack_size_units": 30, "price_inr": 28.0,
     "icmr_diseases": []},

    {"name": "Levothyroxine Sodium 100mcg Tablet",
     "generic_name": "levothyroxine", "dose_mg": 100.0, "formulation_type": "tablet",
     "pack_size_units": 30, "price_inr": 38.0,
     "icmr_diseases": []},

    # ── Pain / Muscle Relaxant ───────────────────────────────────────────────
    {"name": "Paracetamol + Tramadol 325mg/37.5mg Tablet",
     "generic_name": "paracetamol tramadol", "dose_mg": 325.0, "formulation_type": "tablet",
     "pack_size_units": 10, "price_inr": 42.0,
     "icmr_diseases": ["musculoskeletal_pain"]},

    {"name": "Chlorzoxazone 500mg + Ibuprofen 400mg Tablet",
     "generic_name": "chlorzoxazone ibuprofen", "dose_mg": 500.0, "formulation_type": "tablet",
     "pack_size_units": 10, "price_inr": 38.0,
     "icmr_diseases": ["musculoskeletal_pain"]},
]


def seed_symptomatic_drugs(cur):
    print(f"\n[3/4] Seeding {len(SYMPTOMATIC_DRUGS)} essential symptomatic drugs...")
    inserted = 0
    skipped  = 0
    for drug in SYMPTOMATIC_DRUGS:
        cur.execute("""
            INSERT INTO drugs (name, generic_name, dose_mg, formulation_type,
                               pack_size_units, price_inr, icmr_diseases, is_active)
            VALUES (%s, %s, %s, %s::formulation_type, %s, %s, %s, TRUE)
            ON CONFLICT DO NOTHING
            RETURNING id;
        """, (
            drug["name"], drug["generic_name"], drug.get("dose_mg"),
            drug["formulation_type"], drug["pack_size_units"], drug["price_inr"],
            drug["icmr_diseases"],
        ))
        row = cur.fetchone()
        if row:
            inserted += 1
        else:
            skipped += 1

    cur.execute("SELECT formulation_type, COUNT(*) FROM drugs GROUP BY 1 ORDER BY 2 DESC;")
    print(f"[OK] {inserted} new drugs inserted, {skipped} already existed")
    print("\n  Drug catalog by formulation:")
    for row in cur.fetchall():
        print(f"    {row[0]:20s}: {row[1]}")
    cur.execute("SELECT COUNT(*) FROM drugs;")
    print(f"  Total active drugs: {cur.fetchone()[0]}")


# ─── Step 4: Verify ──────────────────────────────────────────────────────────
def verify(cur):
    print("\n[4/4] Verification...")
    cur.execute("""
        SELECT ncd_type, COUNT(*) AS weeks,
               SUM(patients_est) AS total_patients,
               ROUND(AVG(patients_est)) AS avg_weekly_patients
        FROM ncd_demand_weekly
        GROUP BY 1
        ORDER BY 2 DESC;
    """)
    rows = cur.fetchall()
    print(f"\n  {'Condition':<35} {'Total Weeks':>12} {'Total Patients':>16} {'Avg/Week':>10}")
    print(f"  {'-'*78}")
    for row in rows:
        print(f"  {row[0]:<35} {row[1]:>12,} {row[2]:>16,} {row[3]:>10,}")

    cur.execute("SELECT COUNT(*) FROM ncd_demand_weekly;")
    print(f"\n  Total ncd_demand_weekly records: {cur.fetchone()[0]:,}")
    cur.execute("SELECT COUNT(DISTINCT ncd_type) FROM ncd_demand_weekly;")
    print(f"  Distinct condition types: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM drugs WHERE is_active;")
    print(f"  Total active drugs in catalog: {cur.fetchone()[0]}")


# ─── Main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Pharmasense — Symptomatic Demand Pipeline")
    p.add_argument("--db-password", "-p", required=True, help="Supabase postgres password")
    p.add_argument("--skip-demand", action="store_true", help="Only add drugs, skip demand generation")
    args = p.parse_args()

    print("\n" + "="*70)
    print("  Pharmasense — Symptomatic & Essential Condition Demand Pipeline")
    print("  Conditions: viral_fever_urti, acute_gastritis_dyspepsia,")
    print("              musculoskeletal_pain, asthma_copd_respiratory,")
    print("              helminth_infestation, uti_bacterial_infections,")
    print("              maternal_anc_supplements")
    print("  Districts: 641  |  Weeks: 2018–2024  |  Method: MBQ + NSSO/GBD")
    print("="*70)

    import time
    conn = get_conn(args.db_password)
    conn.autocommit = True
    cur  = conn.cursor()
    print("[OK] Connected to Supabase PostgreSQL")

    t0 = time.time()
    expand_check_constraint(cur)
    if not args.skip_demand:
        generate_symptomatic_demand(cur)
    seed_symptomatic_drugs(cur)
    verify(cur)
    conn.close()

    elapsed = time.time() - t0
    print(f"\n{'='*70}")
    print(f"  Symptomatic pipeline complete in {elapsed:.0f}s")
    print(f"{'='*70}")
