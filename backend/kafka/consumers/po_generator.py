import structlog
import asyncio
import json
from backend.db.client import get_db

log = structlog.get_logger()

async def po_generator_consumer():
    """
    Idempotent PO creation.
    Checks DB for existing PENDING POs before creating.
    """
    log.info("kafka.consumer.po_generator.started")
    # Stub consumer loop
    while True:
        try:
            # message = await consumer.getone()
            # data = json.loads(message.value)
            await asyncio.sleep(60) # Stub
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.error("kafka.consumer.po_generator.error", error=str(e))
            await asyncio.sleep(5)
            
    log.info("kafka.consumer.po_generator.stopped")
