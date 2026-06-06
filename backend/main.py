from contextlib import asynccontextmanager
from fastapi import FastAPI
import structlog
import asyncio

from backend.ml.loader import registry
from backend.db.client import get_db
from backend.cache.client import RedisClient
from backend.kafka.consumers.runner import kafka_runner
from backend.data.scheduler import start as start_scheduler, shutdown as shutdown_scheduler

from backend.api.risk import risk_router
from backend.api.forecast import forecast_router
from backend.api.brief import brief_router
from backend.api.simulate import simulate_router
from backend.api.orders import orders_router
from backend.api.admin import admin_router
from backend.api.signals import signals_router
from backend.api.hospitals import hospitals_router

log = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    log.info("pharmasense.startup.begin")
    
    # registry.load_all()           # ML models - Commented out for instant UI development boot
    
    # Initialize connections
    # We will wrap in try/except so local tests without Redis/Supabase don't hard crash the boot
    # try:
    #     await RedisClient.connect()
    # except Exception as e:
    #     log.warning("startup.redis.failed", error=str(e))
        
    try:
        db = get_db()
        db.connect()
        # db.verify() # Supabase verification sometimes slow, skipping to keep boot fast
    except Exception as e:
        log.warning("startup.db.failed", error=str(e))
        
    # Start background processes
    # kafka_runner.start()
    # start_scheduler()
    
    log.info("pharmasense.startup.complete", models=registry.health_map)
    
    yield  # app is running
    
    # SHUTDOWN
    log.info("pharmasense.shutdown.begin")
    try:
        await kafka_runner.stop()
        shutdown_scheduler()
        await RedisClient.disconnect()
        get_db().disconnect()
    except:
        pass
    log.info("pharmasense.shutdown.complete")

app = FastAPI(
    title="Pharmasense ML Service",
    version="1.0.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(risk_router,      prefix="/api/v1")
app.include_router(forecast_router,  prefix="/api/v1")
app.include_router(brief_router,     prefix="/api/v1")
app.include_router(signals_router,   prefix="/api/v1")
app.include_router(simulate_router,  prefix="/api/v1")
app.include_router(orders_router,    prefix="/api/v1")
app.include_router(admin_router,     prefix="/api/v1")
app.include_router(hospitals_router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "models": registry.health_map
    }
