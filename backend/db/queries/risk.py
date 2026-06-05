import json
from typing import List, Dict
from datetime import date
from backend.db.client import get_db

def get_latest_risk_scores(district_id: str) -> List[Dict]:
    supabase = get_db().get_supabase_a()
    response = supabase.table('risk_scores')\
        .select('*')\
        .eq('district_id', district_id)\
        .order('computed_at', desc=True)\
        .limit(10)\
        .execute()
    return response.data

def upsert_risk_scores(scores: List[Dict]):
    """
    High-throughput upsert for risk scores using psycopg2 connection pool.
    Useful for daily batch runs covering 641 districts x 4 diseases.
    """
    db = get_db()
    conn = db.get_pg_connection()
    try:
        with conn.cursor() as cur:
            # Prepare bulk insert logic
            # Uses PostgreSQL ON CONFLICT for upsert
            # Assuming uniqueness on (district_id, disease, target_date)
            query = """
                INSERT INTO risk_scores (
                    district_id, disease, target_date, risk_score, risk_level, 
                    predicted_cases, baseline_cases, model_used, weather_score, 
                    search_score, epid_baseline, is_anomaly
                ) VALUES (
                    %(district_id)s, %(disease)s, %(target_date)s, %(score)s, %(risk_level)s,
                    %(predicted_cases)s, %(baseline_cases)s, %(model_used)s, %(weather_score)s,
                    %(search_score)s, %(epid_baseline)s, %(is_anomaly)s
                ) ON CONFLICT (district_id, disease, target_date) 
                DO UPDATE SET
                    risk_score = EXCLUDED.risk_score,
                    risk_level = EXCLUDED.risk_level,
                    predicted_cases = EXCLUDED.predicted_cases,
                    baseline_cases = EXCLUDED.baseline_cases,
                    model_used = EXCLUDED.model_used,
                    weather_score = EXCLUDED.weather_score,
                    search_score = EXCLUDED.search_score,
                    epid_baseline = EXCLUDED.epid_baseline,
                    is_anomaly = EXCLUDED.is_anomaly,
                    computed_at = CURRENT_TIMESTAMP;
            """
            cur.executemany(query, scores)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        db.put_pg_connection(conn)
