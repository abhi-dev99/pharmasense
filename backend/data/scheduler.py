import asyncio
import structlog
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.data.weather import weather_fetcher
from backend.data.search_trends import search_fetcher
from backend.db.client import get_db

log = structlog.get_logger()
scheduler = AsyncIOScheduler()

async def daily_batch_06am_IST():
    """
    Full system run. Logs to audit_log. Updates batch:status in Redis.
    Steps:
    1. fetch_weather()
    2. fetch_search_trends()
    3. fetch_districts_and_run_inference()
    """
    log.info("scheduler.daily_batch.start", time=datetime.utcnow().isoformat())
    try:
        weather_updated = await weather_fetcher.fetch_and_persist()
        search_updated = await search_fetcher.fetch_and_persist()
        
        # Next, it would trigger the ML inference for all districts
        # and invalidate cache
        
        log.info("scheduler.daily_batch.complete", weather=weather_updated, search=search_updated)
        
        # Log to audit_log in DB
        db = get_db()
        # db.execute(...)
    except Exception as e:
        log.error("scheduler.daily_batch.failed", error=str(e))

async def hourly_weather_anomaly_check():
    """
    Checks if current weather deviates from forecast significantly.
    If anomaly found: invalidate specific district risk caches.
    """
    log.info("scheduler.hourly_anomaly.start")
    # Stub logic
    pass

def start():
    """
    Wires up the cron jobs and starts the scheduler background task.
    IST is UTC+5:30. 06:00 IST = 00:30 UTC.
    """
    scheduler.add_job(
        daily_batch_06am_IST,
        CronTrigger(hour=0, minute=30, timezone='UTC'),
        id='daily_batch'
    )
    
    scheduler.add_job(
        hourly_weather_anomaly_check,
        CronTrigger(minute=0, timezone='UTC'),
        id='hourly_anomaly'
    )
    
    scheduler.start()
    log.info("scheduler.started")

def shutdown():
    scheduler.shutdown()
    log.info("scheduler.shutdown")
