import structlog
import asyncio
import json
from aiokafka import AIOKafkaConsumer
from twilio.rest import Client
from backend.config import settings

log = structlog.get_logger()

async def whatsapp_notifier_consumer():
    """
    Reads outbreak_events independently.
    Sends Twilio WA message alerts.
    """
    log.info("kafka.consumer.whatsapp_notifier.started")
    
    # Initialize Twilio Client
    twilio_client = None
    if settings.twilio_account_sid and settings.twilio_auth_token:
        twilio_client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    else:
        log.warning("kafka.consumer.whatsapp_notifier.twilio_missing", msg="Twilio credentials missing. Notifier running in silent mode.")

    # Initialize AIOKafkaConsumer
    consumer = AIOKafkaConsumer(
        settings.kafka_outbreak_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_consumer_group_wa,
        auto_offset_reset='earliest'
    )
    
    try:
        await consumer.start()
    except Exception as e:
        log.error("kafka.consumer.whatsapp_notifier.connection_failed", error=str(e))
        return

    try:
        async for msg in consumer:
            try:
                event = json.loads(msg.value.decode('utf-8'))
                district_id = event.get('district_id')
                disease = event.get('disease')
                risk_level = event.get('risk_level')
                
                log.info("kafka.consumer.whatsapp_notifier.event_received", district_id=district_id, disease=disease)
                
                if twilio_client and settings.twilio_whatsapp_from:
                    # Target number: In production, this would be fetched from the DB based on district_id.
                    # For demo/hackathon purposes, we use the environment variable (or hardcoded testing number).
                    target_number = "+16562202799"
                    to_number = f"whatsapp:{target_number}"
                    
                    message_body = (
                        f"🚨 *PharmaSense Outbreak Alert* 🚨\n\n"
                        f"District: *{district_id}*\n"
                        f"Disease: *{disease.upper()}*\n"
                        f"Risk Level: *{risk_level}*\n\n"
                        f"Our ML Models have flagged this region for an imminent outbreak. "
                        f"A draft Purchase Order has automatically been generated in the system. "
                        f"Please review immediately."
                    )
                    
                    # Run Twilio sync API call inside a thread to avoid blocking asyncio event loop
                    await asyncio.to_thread(
                        twilio_client.messages.create,
                        body=message_body,
                        from_=settings.twilio_whatsapp_from,
                        to=to_number
                    )
                    log.info("kafka.consumer.whatsapp_notifier.twilio_sent", to=to_number)
            except Exception as e:
                log.error("kafka.consumer.whatsapp_notifier.processing_error", error=str(e))
    except asyncio.CancelledError:
        log.info("kafka.consumer.whatsapp_notifier.cancelled")
    finally:
        await consumer.stop()
        log.info("kafka.consumer.whatsapp_notifier.stopped")
