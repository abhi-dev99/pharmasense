import asyncio
import os
import sys

# Ensure backend module is resolvable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.config import settings
from backend.db.client import get_db
from backend.cache.client import get_redis, RedisClient
import structlog

log = structlog.get_logger()

async def run_tests():
    log.info("Starting connection verification...")
    
    # Test Redis
    try:
        await RedisClient.connect()
        redis = get_redis()
        await redis.set("pharmasense_test", "1")
        val = await redis.get("pharmasense_test")
        assert val == "1"
        await redis.delete("pharmasense_test")
        log.info("[OK] Redis connection successful")
    except Exception as e:
        log.error("[FAIL] Redis connection failed", error=str(e))
        
    # Test Supabase DB (Projects A & B)
    try:
        db = get_db()
        db.connect()
        
        # Test Project A
        res_a = db.get_supabase_a().table("districts").select("id").limit(1).execute()
        log.info("[OK] Supabase Project A connected", count=len(res_a.data))
        
        # Test Project B
        res_b = db.get_supabase_b().table("ncd_demand_weekly").select("id").limit(1).execute()
        log.info("[OK] Supabase Project B connected")
        
        # Test psycopg2
        conn = db.get_pg_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        db.put_pg_connection(conn)
        log.info("[OK] Psycopg2 Pool connected to Project A")
        
    except Exception as e:
        log.error("[FAIL] Database connection failed", error=str(e))

    finally:
        await RedisClient.disconnect()
        try:
            get_db().disconnect()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(run_tests())
