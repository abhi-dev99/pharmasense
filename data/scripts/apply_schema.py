"""
Apply Supabase schema via direct PostgreSQL connection (psycopg2).
No need to open the SQL editor manually.

Usage:
  python data/scripts/apply_schema.py --db-password YOUR_DB_PASSWORD

Get DB password from:
  Supabase Dashboard -> Settings -> Database -> Connection string -> show password
  (It's the password you set when creating the project)
"""

import sys
import os
import argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

def apply_schema(db_password: str):
    try:
        import psycopg2
    except ImportError:
        print("psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)

    supabase_url = os.getenv("SUPABASE_URL", "")
    project_ref  = supabase_url.replace("https://", "").split(".")[0]
    db_host      = f"db.{project_ref}.supabase.co"
    db_port      = 5432
    db_name      = "postgres"
    db_user      = "postgres"

    print(f"\nConnecting to PostgreSQL at {db_host}:{db_port}...")

    try:
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            dbname=db_name,
            user=db_user,
            password=db_password,
            connect_timeout=15,
            sslmode="require",
        )
        conn.autocommit = True
        cur = conn.cursor()
        print("[OK]  Connected to Supabase PostgreSQL")
    except psycopg2.OperationalError as e:
        print(f"[ERR] Connection failed: {e}")
        print("\nCheck:")
        print("  1. DB password is correct (not the API key)")
        print("  2. Your IP is not blocked (Supabase -> Settings -> Database -> Network)")
        sys.exit(1)

    schema_path = ROOT / "data/seed/schema.sql"
    schema_sql  = schema_path.read_text(encoding="utf-8")

    print(f"\nApplying schema from {schema_path.name} ({len(schema_sql):,} bytes)...")

    # Split into statements — run each individually so we get clear error reporting
    # Supabase/PostgreSQL handles DO $$ blocks fine in a single execute
    try:
        cur.execute(schema_sql)
        print("[OK]  Schema applied successfully")
    except psycopg2.Error as e:
        print(f"[ERR] Schema application failed: {e}")
        print("\nCommon causes:")
        print("  - Tables already exist (safe to ignore if this is a re-run)")
        print("  - PostGIS extension not available (Supabase has it, should be fine)")
        conn.close()
        sys.exit(1)

    # Verify
    print("\nVerifying tables exist...")
    expected_tables = [
        "districts", "drugs", "hospitals", "epid_weekly",
        "weather_signals", "search_signals", "risk_scores",
        "demand_forecasts", "inventory", "inventory_transactions",
        "purchase_orders", "audit_log"
    ]
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)
    existing = {row[0] for row in cur.fetchall()}

    all_ok = True
    for t in expected_tables:
        if t in existing:
            print(f"  [OK]  {t}")
        else:
            print(f"  [ERR] {t} - MISSING")
            all_ok = False

    conn.close()

    if all_ok:
        print(f"\n[OK]  All {len(expected_tables)} tables created. Schema ready.")
    else:
        print(f"\n[WRN] Some tables missing. Check the error output above.")

    return all_ok


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply Pharmasense schema to Supabase")
    parser.add_argument(
        "--db-password", "-p",
        required=True,
        help="Supabase database password (Settings -> Database -> Connection string)"
    )
    args = parser.parse_args()
    success = apply_schema(args.db_password)
    sys.exit(0 if success else 1)
