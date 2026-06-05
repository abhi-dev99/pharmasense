from typing import List, Dict
from backend.db.client import get_db

def create_purchase_order(hospital_id: str, payload: Dict) -> Dict:
    """
    Creates a purchase order in the db if one for the same outbreak event doesn't already exist.
    """
    supabase = get_db().get_supabase_a()
    response = supabase.table('purchase_orders').insert({
        'hospital_id': hospital_id,
        'status': 'PENDING',
        'details': payload
    }).execute()
    return response.data[0] if response.data else None

def get_pending_orders(hospital_id: str) -> List[Dict]:
    supabase = get_db().get_supabase_a()
    response = supabase.table('purchase_orders')\
        .select('*')\
        .eq('hospital_id', hospital_id)\
        .eq('status', 'PENDING')\
        .execute()
    return response.data
