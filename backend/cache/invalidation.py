import structlog
from datetime import date
from typing import List
from backend.cache.client import get_redis
from backend.cache.keys import CacheKeys

log = structlog.get_logger()

async def invalidate_district_risk(district_id: str, target_date: date, diseases: List[str] = None):
    """
    Invalidates risk scores for a specific district.
    Used when a sudden weather anomaly or signal spike occurs.
    """
    redis = get_redis()
    
    if not diseases:
        diseases = ['dengue', 'malaria', 'cholera', 'acute_diarrhoeal_disease']
        
    keys_to_delete = [
        CacheKeys.risk_score(district_id, disease, target_date)
        for disease in diseases
    ]
    
    deleted = await redis.delete(*keys_to_delete)
    log.info("cache.invalidated.risk_score", district_id=district_id, deleted_count=deleted)


async def invalidate_hospital_brief(hospital_id: str, target_date: date):
    """
    Invalidates LLM hospital brief.
    Used when significant inventory changes occur to force a new LLM generation.
    """
    redis = get_redis()
    key = CacheKeys.hospital_brief(hospital_id, target_date)
    
    deleted = await redis.delete(key)
    log.info("cache.invalidated.hospital_brief", hospital_id=hospital_id, deleted_count=deleted)
