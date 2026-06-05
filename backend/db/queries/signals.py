from typing import List, Dict
from datetime import date, timedelta
from backend.db.client import get_db

def get_weather_signals(district_id: str, days_back: int = 7) -> List[Dict]:
    supabase = get_db().get_supabase_a()
    start_date = (date.today() - timedelta(days=days_back)).isoformat()
    response = supabase.table('weather_signals')\
        .select('*')\
        .eq('district_id', district_id)\
        .gte('date', start_date)\
        .order('date', desc=True)\
        .execute()
    return response.data

def get_search_signals(state: str, days_back: int = 28) -> List[Dict]:
    supabase = get_db().get_supabase_a()
    start_date = (date.today() - timedelta(days=days_back)).isoformat()
    response = supabase.table('search_signals')\
        .select('*')\
        .eq('state', state)\
        .gte('date', start_date)\
        .order('date', desc=True)\
        .execute()
    return response.data
