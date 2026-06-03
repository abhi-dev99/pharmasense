"""
Phase 0 — Script 4: Seed Hospitals + Supabase Auth Users
Seeds demo hospitals from National Health Facility Registry data (public domain),
creates demo user accounts in Supabase Auth with role metadata.

Usage: python data/scripts/04_seed_hospitals.py
Pre-req: Scripts 01-03 complete (districts + drugs tables populated)
"""

import sys
import os
import json
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import pandas as pd
from tqdm import tqdm
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# ─── Demo hospitals (curated from NHFR public data, ~10 districts) ────────────
# Format: name, district_name (must match districts.name), state, lat, lon, tier, beds
# Using real hospitals from NHFR (National Health Facility Registry)
DEMO_HOSPITALS = [
    # Tamil Nadu — high dengue risk
    {"name": "Rajiv Gandhi Government General Hospital", "district_name": "Chennai", "state": "Tamil Nadu",
     "lat": 13.0827, "lon": 80.2707, "tier": "State", "bed_count": 2600},
    {"name": "Government Stanley Medical College Hospital", "district_name": "Chennai", "state": "Tamil Nadu",
     "lat": 13.1061, "lon": 80.2850, "tier": "State", "bed_count": 1500},
    {"name": "Government District Headquarters Hospital Coimbatore", "district_name": "Coimbatore", "state": "Tamil Nadu",
     "lat": 11.0168, "lon": 76.9558, "tier": "District", "bed_count": 750},
    {"name": "Erode Government District Hospital", "district_name": "Erode", "state": "Tamil Nadu",
     "lat": 11.3410, "lon": 77.7172, "tier": "District", "bed_count": 500},

    # Maharashtra — high malaria + dengue
    {"name": "KEM Hospital Mumbai", "district_name": "Mumbai", "state": "Maharashtra",
     "lat": 19.0007, "lon": 72.8337, "tier": "State", "bed_count": 1800},
    {"name": "Pune District Hospital Sassoon", "district_name": "Pune", "state": "Maharashtra",
     "lat": 18.5158, "lon": 73.8569, "tier": "State", "bed_count": 1400},
    {"name": "Nasik Civil Hospital", "district_name": "Nashik", "state": "Maharashtra",
     "lat": 19.9975, "lon": 73.7898, "tier": "District", "bed_count": 600},

    # Uttar Pradesh — high cholera + ADD risk
    {"name": "Balrampur Hospital Lucknow", "district_name": "Lucknow", "state": "Uttar Pradesh",
     "lat": 26.8467, "lon": 80.9462, "tier": "State", "bed_count": 1200},
    {"name": "Government District Combined Hospital Varanasi", "district_name": "Varanasi", "state": "Uttar Pradesh",
     "lat": 25.3176, "lon": 82.9739, "tier": "District", "bed_count": 500},
    {"name": "Government Medical College Gorakhpur", "district_name": "Gorakhpur", "state": "Uttar Pradesh",
     "lat": 26.7606, "lon": 83.3732, "tier": "District", "bed_count": 700},

    # Kerala — dengue + malaria
    {"name": "Government Medical College Thiruvananthapuram", "district_name": "Thiruvananthapuram", "state": "Kerala",
     "lat": 8.5241, "lon": 76.9366, "tier": "State", "bed_count": 1000},
    {"name": "Kozhikode Government Medical College", "district_name": "Kozhikode", "state": "Kerala",
     "lat": 11.2588, "lon": 75.7804, "tier": "State", "bed_count": 1200},

    # West Bengal — cholera + dengue
    {"name": "NRS Medical College and Hospital Kolkata", "district_name": "Kolkata", "state": "West Bengal",
     "lat": 22.5726, "lon": 88.3639, "tier": "State", "bed_count": 1500},
    {"name": "Burdwan Medical College Hospital", "district_name": "Bardhaman", "state": "West Bengal",
     "lat": 23.2324, "lon": 87.8615, "tier": "State", "bed_count": 800},

    # Rajasthan — malaria
    {"name": "SMS Hospital Jaipur", "district_name": "Jaipur", "state": "Rajasthan",
     "lat": 26.9124, "lon": 75.7873, "tier": "State", "bed_count": 2000},
    {"name": "Udaipur Government Hospital", "district_name": "Udaipur", "state": "Rajasthan",
     "lat": 24.5854, "lon": 73.7125, "tier": "District", "bed_count": 600},
]

# ─── Demo user accounts (Supabase Auth) ───────────────────────────────────────
# Passwords: all set to "Pharmasense2026!" for demo
DEMO_USERS = [
    {
        "email": "minister@pharmasense.demo",
        "password": "Pharmasense2026!",
        "role": "state_minister",
        "name": "State Health Minister (TN)",
        "metadata": {"app_role": "state_minister", "state": "Tamil Nadu"}
    },
    {
        "email": "dho.chennai@pharmasense.demo",
        "password": "Pharmasense2026!",
        "role": "district_officer",
        "name": "District Health Officer - Chennai",
        "metadata": {"app_role": "district_officer", "district_name": "Chennai", "state": "Tamil Nadu"}
    },
    {
        "email": "dho.pune@pharmasense.demo",
        "password": "Pharmasense2026!",
        "role": "district_officer",
        "name": "District Health Officer - Pune",
        "metadata": {"app_role": "district_officer", "district_name": "Pune", "state": "Maharashtra"}
    },
    {
        "email": "pharma.kem@pharmasense.demo",
        "password": "Pharmasense2026!",
        "role": "pharmacist",
        "name": "KEM Hospital Pharmacist",
        "metadata": {"app_role": "pharmacist", "hospital_name": "KEM Hospital Mumbai"}
    },
    {
        "email": "pharma.rajiv@pharmasense.demo",
        "password": "Pharmasense2026!",
        "role": "pharmacist",
        "name": "Rajiv Gandhi Hospital Pharmacist",
        "metadata": {"app_role": "pharmacist", "hospital_name": "Rajiv Gandhi Government General Hospital"}
    },
    {
        "email": "pharma.sms@pharmasense.demo",
        "password": "Pharmasense2026!",
        "role": "pharmacist",
        "name": "SMS Hospital Pharmacist",
        "metadata": {"app_role": "pharmacist", "hospital_name": "SMS Hospital Jaipur"}
    },
]

# ─── Fetch district IDs from Supabase ─────────────────────────────────────────
def get_district_id_map(client) -> dict[str, str]:
    """Returns {district_name_lower: district_id}"""
    result = client.table("districts").select("id,name,state").execute()
    lookup = {}
    for d in result.data:
        key = d["name"].strip().lower()
        lookup[key] = d["id"]
    return lookup

# ─── Seed hospitals ───────────────────────────────────────────────────────────
def seed_hospitals(client, district_id_map: dict) -> dict[str, str]:
    """Returns {hospital_name: hospital_id}"""
    print(f"\n🏥 Seeding {len(DEMO_HOSPITALS)} demo hospitals...")
    hospital_id_map = {}

    for h in tqdm(DEMO_HOSPITALS, desc="Inserting hospitals"):
        district_key = h["district_name"].lower().strip()
        district_id  = district_id_map.get(district_key)

        if not district_id:
            # Fuzzy fallback
            from rapidfuzz import process, fuzz
            match = process.extractOne(district_key, list(district_id_map.keys()), scorer=fuzz.token_sort_ratio)
            if match and match[1] >= 75:
                district_id = district_id_map[match[0]]
                print(f"   ⚠️  Fuzzy matched '{district_key}' → '{match[0]}' (score={match[1]})")
            else:
                print(f"   ❌ No district found for '{h['district_name']}' — skipping hospital")
                continue

        record = {
            "name":        h["name"],
            "district_id": district_id,
            "lat":         h["lat"],
            "lon":         h["lon"],
            "tier":        h["tier"],
            "bed_count":   h["bed_count"],
        }

        try:
            result = client.table("hospitals").insert(record).execute()
            if result.data:
                hosp_id = result.data[0]["id"]
                hospital_id_map[h["name"]] = hosp_id
        except Exception as e:
            # Hospital may already exist — try selecting it
            try:
                sel = client.table("hospitals").select("id").eq("name", h["name"]).execute()
                if sel.data:
                    hospital_id_map[h["name"]] = sel.data[0]["id"]
            except Exception:
                print(f"   ❌ Failed to insert/find {h['name']}: {e}")

    print(f"   ✅ {len(hospital_id_map)} hospitals seeded")
    return hospital_id_map

# ─── Seed opening inventory ───────────────────────────────────────────────────
def seed_inventory(client, hospital_id_map: dict):
    """Creates zero-stock inventory records for each hospital × ICMR drug"""
    print(f"\n💊 Seeding opening inventory...")

    # Get all ICMR drugs
    drugs_result = client.table("drugs").select("id,generic_name,formulation_type").execute()
    drugs = drugs_result.data
    print(f"   {len(drugs)} drugs × {len(hospital_id_map)} hospitals = {len(drugs) * len(hospital_id_map)} records")

    # Get all hospitals
    hosp_result = client.table("hospitals").select("id,name").execute()
    hospitals = hosp_result.data

    records = []
    for hosp in hospitals:
        for drug in drugs:
            # Seed with realistic opening stock based on hospital tier
            tier_result = client.table("hospitals").select("tier").eq("id", hosp["id"]).execute()
            tier = tier_result.data[0]["tier"] if tier_result.data else "District"
            base_stock = {"State": 1000, "District": 500, "CHC": 200, "PHC": 50}.get(tier, 200)

            records.append({
                "hospital_id":  hosp["id"],
                "drug_id":      drug["id"],
                "stock_units":  base_stock,
                "reorder_point": base_stock // 5,
            })

    BATCH_SIZE = 200
    success = 0
    for i in tqdm(range(0, len(records), BATCH_SIZE), desc="Seeding inventory"):
        batch = records[i:i + BATCH_SIZE]
        try:
            client.table("inventory").upsert(batch, on_conflict="hospital_id,drug_id").execute()
            success += len(batch)
        except Exception as e:
            print(f"\n   ❌ Batch {i//BATCH_SIZE} failed: {str(e)[:100]}")

    print(f"   ✅ {success} inventory records seeded")

# ─── Create Supabase Auth users ───────────────────────────────────────────────
def create_demo_users(client, hospital_id_map: dict) -> dict[str, str]:
    """Creates demo users in Supabase Auth with role metadata"""
    print(f"\n👤 Creating {len(DEMO_USERS)} demo Supabase Auth users...")

    # Update pharmacist metadata with actual hospital IDs
    for user in DEMO_USERS:
        if user["role"] == "pharmacist":
            hosp_name = user["metadata"].get("hospital_name")
            if hosp_name and hosp_name in hospital_id_map:
                user["metadata"]["hospital_id"] = hospital_id_map[hosp_name]

    created_users = {}
    for user_def in DEMO_USERS:
        try:
            result = client.auth.admin.create_user({
                "email":            user_def["email"],
                "password":         user_def["password"],
                "email_confirm":    True,
                "user_metadata":    user_def["metadata"],
            })
            if hasattr(result, "user") and result.user:
                uid = result.user.id
                created_users[user_def["email"]] = uid
                print(f"   ✅ Created: {user_def['email']} (role={user_def['role']})")
        except Exception as e:
            err = str(e)
            if "already registered" in err.lower() or "already exists" in err.lower():
                print(f"   ⚠️  {user_def['email']} already exists — skipping")
            else:
                print(f"   ❌ Failed to create {user_def['email']}: {err[:80]}")

    return created_users

# ─── Save seed data locally ───────────────────────────────────────────────────
def save_seed_reference(hospital_id_map: dict, user_map: dict):
    out = ROOT / "data/seed/demo_accounts.json"
    out.parent.mkdir(parents=True, exist_ok=True)

    reference = {
        "_note": "Demo account credentials for Pharmasense hackathon demo",
        "_warning": "NEVER commit real credentials. This file is gitignored.",
        "default_password": "Pharmasense2026!",
        "hospitals": hospital_id_map,
        "users": [
            {
                "email":    u["email"],
                "role":     u["role"],
                "name":     u["name"],
                "password": u["password"],
            }
            for u in DEMO_USERS
        ]
    }

    with open(out, "w") as f:
        json.dump(reference, f, indent=2)
    print(f"\n💾 Demo account reference saved to {out}")

# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*60)
    print("  Script 04 — Seed Hospitals + Auth Users")
    print("="*60)

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
        sys.exit(1)

    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    district_id_map = get_district_id_map(client)
    print(f"✅ Loaded {len(district_id_map)} districts from Supabase")

    hospital_id_map = seed_hospitals(client, district_id_map)
    seed_inventory(client, hospital_id_map)

    user_map = create_demo_users(client, hospital_id_map)
    save_seed_reference(hospital_id_map, user_map)

    print("\n✅ Script 04 complete.")
    print("\nDemo accounts (all password: Pharmasense2026!):")
    for u in DEMO_USERS:
        print(f"  {u['role']:20s} → {u['email']}")
