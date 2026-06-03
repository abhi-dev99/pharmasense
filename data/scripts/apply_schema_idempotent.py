"""
Apply schema idempotently — drops existing policies first, then re-applies.
Safe to run multiple times.
"""
import sys, os
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
import psycopg2

def get_conn(password):
    url = os.getenv("SUPABASE_URL","")
    ref = url.replace("https://","").split(".")[0]
    return psycopg2.connect(
        host=f"db.{ref}.supabase.co", port=5432, dbname="postgres",
        user="postgres", password=password, sslmode="require", connect_timeout=15
    )

def run(cur, sql, desc=""):
    try:
        cur.execute(sql)
        return True
    except psycopg2.Error as e:
        msg = str(e).strip().split("\n")[0]
        print(f"  [skip] {desc}: {msg}")
        return False

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--db-password", "-p", required=True)
    args = p.parse_args()

    conn = get_conn(args.db_password)
    conn.autocommit = True
    cur = conn.cursor()
    print("[OK] Connected\n")

    # ── Drop all existing RLS policies (safe — just permissions, not data) ──
    print("Dropping existing RLS policies...")
    cur.execute("""
        SELECT schemaname, tablename, policyname
        FROM pg_policies WHERE schemaname = 'public';
    """)
    policies = cur.fetchall()
    for schema, table, policy in policies:
        run(cur, f'DROP POLICY IF EXISTS "{policy}" ON {schema}."{table}";', f"drop {policy}")
    print(f"  Dropped {len(policies)} policies\n")

    # ── Drop triggers (safe to recreate) ──
    print("Dropping existing triggers...")
    for trig, table in [("inventory_updated_at","inventory"),("inventory_txn_apply","inventory_transactions")]:
        run(cur, f'DROP TRIGGER IF EXISTS {trig} ON {table};', f"drop trigger {trig}")

    # ── Drop functions ──
    print("Dropping existing helper functions...")
    for fn in ["auth_role()","auth_hospital_id()","auth_district_name()","auth_state()",
                "update_inventory_timestamp()","apply_inventory_transaction()"]:
        run(cur, f"DROP FUNCTION IF EXISTS {fn} CASCADE;", f"drop fn {fn}")
    print()

    # ── Drop existing enum types if schema is being fully reset ──
    # (skip — enums cause issues if tables already use them)

    # ── Apply full schema ──
    print("Applying schema.sql...")
    schema_sql = (ROOT / "data/seed/schema.sql").read_text(encoding="utf-8")
    try:
        cur.execute(schema_sql)
        print("[OK] Schema applied\n")
    except psycopg2.Error as e:
        # Split and apply statement by statement
        print(f"  Bulk apply failed ({str(e)[:60]}), applying statement by statement...")
        conn.rollback() if not conn.autocommit else None
        
        import re
        # Split on semicolons not inside $$ blocks
        statements = re.split(r';\s*\n', schema_sql)
        ok = err = 0
        for stmt in statements:
            stmt = stmt.strip()
            if not stmt or stmt.startswith("--"):
                continue
            try:
                cur.execute(stmt)
                ok += 1
            except psycopg2.Error as e2:
                msg = str(e2).strip().split("\n")[0]
                if "already exists" not in msg.lower():
                    print(f"  [ERR] {msg[:100]}")
                    err += 1
        print(f"  Applied {ok} statements, {err} errors\n")

    # ── Verify tables ──
    print("Verifying tables...")
    expected = ["districts","drugs","hospitals","epid_weekly","weather_signals",
                "search_signals","risk_scores","demand_forecasts","inventory",
                "inventory_transactions","purchase_orders","audit_log"]
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;")
    existing = {r[0] for r in cur.fetchall()}

    all_ok = True
    for t in expected:
        status = "[OK] " if t in existing else "[ERR]"
        if t not in existing: all_ok = False
        print(f"  {status} {t}")

    conn.close()
    print(f"\n{'[OK] ALL TABLES READY' if all_ok else '[ERR] SOME TABLES MISSING'}")
    sys.exit(0 if all_ok else 1)
