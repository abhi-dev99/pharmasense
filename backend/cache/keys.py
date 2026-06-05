from datetime import date

class CacheKeys:
    """Centralized schema for Redis keys"""
    
    @staticmethod
    def risk_score(district_id: str, disease: str, target_date: date) -> str:
        """Cache for ML risk predictions (TTL 24h)"""
        return f"risk:{district_id}:{disease}:{target_date.isoformat()}"
        
    @staticmethod
    def hospital_brief(hospital_id: str, target_date: date) -> str:
        """Cache for Gemini LLM hospital briefs (TTL 24h)"""
        return f"brief:{hospital_id}:{target_date.isoformat()}"
        
    @staticmethod
    def rate_limit(user_id: str, endpoint: str, window_epoch: int) -> str:
        """Sliding window counter for rate limits (TTL 70s)"""
        return f"rl:{user_id}:{endpoint}:{window_epoch}"
        
    @staticmethod
    def jwt_blacklist(jti: str) -> str:
        """Stateless token revocation blacklist (TTL matches JWT expiry)"""
        return f"jwt_revoked:{jti}"
