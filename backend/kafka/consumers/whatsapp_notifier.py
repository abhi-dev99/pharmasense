import structlog
import asyncio
from backend.config import settings

log = structlog.get_logger()

async def whatsapp_notifier_consumer():
    """
    Reads outbreak_events independently.
    Waits slightly to ensure PO exists, then fetches details and sends Twilio WA message.
    """
    log.info("kafka.consumer.whatsapp_notifier.started")
    # Stub consumer loop
    while True:
        try:
            # message = await consumer.getone()
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.error("kafka.consumer.whatsapp_notifier.error", error=str(e))
            await asyncio.sleep(5)
            
    log.info("kafka.consumer.whatsapp_notifier.stopped")
