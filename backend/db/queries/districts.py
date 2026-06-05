from typing import List, Dict
from backend.db.client import get_db

def get_all_districts() -> List[Dict]:
    supabase = get_db().get_supabase_a()
    response = supabase.table('districts').select('*').execute()
    return response.data

def get_district_by_id(district_id: str) -> Dict:
    supabase = get_db().get_supabase_a()
    response = supabase.table('districts').select('*').eq('id', district_id).limit(1).execute()
    return response.data[0] if response.data else None
