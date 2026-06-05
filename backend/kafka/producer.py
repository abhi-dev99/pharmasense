import json
import structlog
from typing import List, Dict
from datetime import datetime
from backend.cache.client import RedisClient

log = structlog.get_logger()

class OutbreakProducer:
    """
    Outbreak event publisher.
    Threshold: risk_score >= 0.70 AND |score - prev_score| >= 0.10
    """
    def __init__(self):
        self.producer = None # Stub for AIOKafkaProducer
        
    async def maybe_publish(
        self,
        district_id: str,
        disease: str,
        new_score: float,
        hospitals: List[Dict]
    ) -> bool:
        redis = RedisClient.get()
        if not redis:
            log.warning("kafka.producer.no_redis", district=district_id)
            return False
            
        key = f"prev_risk:{district_id}:{disease}"
        prev_score = await redis.get(key)
        delta = abs(new_score - float(prev_score or 0))
        
        if new_score >= 0.70 and (prev_score is None or delta >= 0.10):
            await self._publish(district_id, disease, new_score, hospitals)
            await redis.set(key, str(new_score), ex=86400)
            return True
        return False

    async def _publish(self, district_id: str, disease: str, score: float, hospitals: List[Dict]):
        event = {
            "event_id": f"evt_{district_id}_{disease}_{int(datetime.utcnow().timestamp())}",
            "district_id": district_id,
            "disease": disease,
            "risk_score": score,
            "risk_level": "HIGH",
            "triggered_at": datetime.utcnow().isoformat(),
            "hospitals": hospitals
        }
        log.info("kafka.publish.outbreak_event", event_id=event['event_id'])
        # if self.producer: await self.producer.send_and_wait("outbreak_events", json.dumps(event).encode())

    async def publish_test_event(self, district_id: str, disease: str, score: float):
        await self._publish(district_id, disease, score, [{"id": "h1", "name": "Test Hosp"}])

producer = OutbreakProducer()
