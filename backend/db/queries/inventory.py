from typing import List, Dict
from backend.db.client import get_db

def get_hospital_inventory(hospital_id: str) -> List[Dict]:
    supabase = get_db().get_supabase_a()
    response = supabase.table('inventory').select('*, drugs(*)').eq('hospital_id', hospital_id).execute()
    return response.data

def get_hospital_details(hospital_id: str) -> Dict:
    supabase = get_db().get_supabase_a()
    response = supabase.table('hospitals').select('*').eq('id', hospital_id).limit(1).execute()
    return response.data[0] if response.data else None
