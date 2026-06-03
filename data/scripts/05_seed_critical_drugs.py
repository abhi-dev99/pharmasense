"""
Seed 12 critical ICMR injectable/sachet/vial drugs that were missed
by the automated medicines pipeline (formulation parsing gap).

These are standard GoI/WHO essential medicines with public procurement prices.
Run once — idempotent (ON CONFLICT DO NOTHING).

Usage: python data/scripts/05_seed_critical_drugs.py --db-password pharmasons99lite
"""
import sys, os, argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
import psycopg2, psycopg2.extras

# ─── Hardcoded ICMR critical drugs ────────────────────────────────────────────
# Source: ICMR STWs, WHO Essential Medicines List, GoI HLL Lifecare catalog
# price_inr = approximate GoI procurement price per unit pack
CRITICAL_DRUGS = [
    # ── IV Fluids (missed: formulation_type = iv_bag) ──────────────────────────
    {
        "name": "Ringer's Lactate Infusion 500ml",
        "generic_name": "ringer lactate",
        "dose_mg": None,
        "formulation_type": "iv_bag",
        "pack_size_units": 1,
        "price_inr": 35.00,
        "icmr_diseases": ["dengue", "cholera", "acute_diarrhoeal_disease", "malaria"],
        "notes": "Primary crystalloid for dengue fluid resuscitation and cholera rehydration",
    },
    {
        "name": "Normal Saline 0.9% Infusion 500ml",
        "generic_name": "sodium chloride",
        "dose_mg": None,
        "formulation_type": "iv_bag",
        "pack_size_units": 1,
        "price_inr": 28.00,
        "icmr_diseases": ["dengue", "cholera", "malaria"],
        "notes": "Alternate IV fluid when Ringer's not available",
    },
    {
        "name": "Dextrose 5% Infusion 500ml",
        "generic_name": "dextrose",
        "dose_mg": 50.0,
        "formulation_type": "iv_bag",
        "pack_size_units": 1,
        "price_inr": 32.00,
        "icmr_diseases": ["malaria"],
        "notes": "For hypoglycaemia in severe malaria",
    },
    # ── Injections (missed: formulation_type = injection/vial) ─────────────────
    {
        "name": "Artesunate Injection 60mg",
        "generic_name": "artesunate",
        "dose_mg": 60.0,
        "formulation_type": "vial",
        "pack_size_units": 1,
        "price_inr": 185.00,
        "icmr_diseases": ["malaria"],
        "notes": "WHO first-line for severe malaria; 2.4mg/kg IV at 0h/12h/24h",
    },
    {
        "name": "Dextrose 50% Injection 25ml",
        "generic_name": "dextrose",
        "dose_mg": 500.0,
        "formulation_type": "vial",
        "pack_size_units": 1,
        "price_inr": 22.00,
        "icmr_diseases": ["malaria"],
        "notes": "Hypoglycaemia rescue in severe malaria — 50mL of 50% IV",
    },
    # ── ORS Sachet (missed: formulation_type = sachet) ─────────────────────────
    {
        "name": "ORS Powder Sachet 27.9g (WHO Formula)",
        "generic_name": "oral rehydration salts",
        "dose_mg": None,
        "formulation_type": "sachet",
        "pack_size_units": 1,
        "price_inr": 5.50,
        "icmr_diseases": ["cholera", "acute_diarrhoeal_disease", "dengue"],
        "notes": "WHO low-osmolarity ORS; makes 1L; cornerstone of ADD/cholera treatment",
    },
    # ── IV Cannula (device, tracked as 'other') ────────────────────────────────
    {
        "name": "IV Cannula 18G",
        "generic_name": "iv cannula",
        "dose_mg": None,
        "formulation_type": "other",
        "pack_size_units": 1,
        "price_inr": 12.00,
        "icmr_diseases": ["dengue", "malaria", "cholera"],
        "notes": "Required for IV fluid administration in severe cases",
    },
    # ── Anti-malarials as injections ───────────────────────────────────────────
    {
        "name": "Artemether Injection 80mg/ml (1ml ampoule)",
        "generic_name": "artemether",
        "dose_mg": 80.0,
        "formulation_type": "vial",
        "pack_size_units": 1,
        "price_inr": 95.00,
        "icmr_diseases": ["malaria"],
        "notes": "IM alternative when IV artesunate not available for severe malaria",
    },
    # ── Paracetamol IV (severe cases in hospital) ──────────────────────────────
    {
        "name": "Paracetamol Infusion 1g/100ml",
        "generic_name": "paracetamol",
        "dose_mg": 1000.0,
        "formulation_type": "iv_bag",
        "pack_size_units": 1,
        "price_inr": 110.00,
        "icmr_diseases": ["dengue", "malaria"],
        "notes": "IV paracetamol for inpatient fever management when oral route unavailable",
    },
    # ── Azithromycin injection (severe cholera, IV access) ─────────────────────
    {
        "name": "Azithromycin Injection 500mg",
        "generic_name": "azithromycin",
        "dose_mg": 500.0,
        "formulation_type": "injection",
        "pack_size_units": 1,
        "price_inr": 145.00,
        "icmr_diseases": ["cholera"],
        "notes": "IV azithromycin for severe cholera when oral route unavailable",
    },
    # ── Metronidazole IV ───────────────────────────────────────────────────────
    {
        "name": "Metronidazole Infusion 500mg/100ml",
        "generic_name": "metronidazole",
        "dose_mg": 500.0,
        "formulation_type": "iv_bag",
        "pack_size_units": 1,
        "price_inr": 48.00,
        "icmr_diseases": ["acute_diarrhoeal_disease"],
        "notes": "IV metronidazole for severe amoebic dysentery/colitis",
    },
    # ── Ceftriaxone injection (severe ADD/bacteraemia) ─────────────────────────
    {
        "name": "Ceftriaxone Injection 1g",
        "generic_name": "ceftriaxone",
        "dose_mg": 1000.0,
        "formulation_type": "injection",
        "pack_size_units": 1,
        "price_inr": 65.00,
        "icmr_diseases": ["acute_diarrhoeal_disease", "cholera"],
        "notes": "Broad-spectrum for severe ADD with bacteraemia or typhoid complications",
    },
]

def get_conn(password):
    url = os.getenv("SUPABASE_URL","")
    ref = url.replace("https://","").split(".")[0]
    return psycopg2.connect(
        host=f"db.{ref}.supabase.co", port=5432, dbname="postgres",
        user="postgres", password=password, sslmode="require", connect_timeout=15
    )

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--db-password", "-p", required=True)
    args = p.parse_args()

    conn = get_conn(args.db_password)
    conn.autocommit = True
    cur = conn.cursor()
    print(f"\nSeeding {len(CRITICAL_DRUGS)} critical injectable/sachet drugs...\n")

    inserted = 0
    for drug in CRITICAL_DRUGS:
        try:
            cur.execute("""
                INSERT INTO drugs (name, generic_name, dose_mg, formulation_type,
                                   pack_size_units, price_inr, icmr_diseases, is_active)
                VALUES (%s, %s, %s, %s::formulation_type, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING id;
            """, (
                drug["name"], drug["generic_name"], drug.get("dose_mg"),
                drug["formulation_type"], drug["pack_size_units"], drug["price_inr"],
                drug["icmr_diseases"], True,
            ))
            row = cur.fetchone()
            status = "[OK]  inserted" if row else "[--]  already exists"
            print(f"  {status}: {drug['name']}")
            if row: inserted += 1
        except Exception as e:
            print(f"  [ERR] {drug['name']}: {e}")

    cur.execute("SELECT formulation_type, COUNT(*) FROM drugs GROUP BY 1 ORDER BY 2 DESC;")
    print(f"\nDrugs by formulation:")
    for row in cur.fetchall():
        print(f"  {row[0]:15s}: {row[1]}")

    cur.execute("SELECT COUNT(*) FROM drugs;")
    total = cur.fetchone()[0]
    print(f"\n[OK] Total drugs in DB: {total} ({inserted} new from this run)")
    conn.close()
