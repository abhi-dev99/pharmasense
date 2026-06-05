import redis.asyncio as redis
import structlog
from backend.config import settings

log = structlog.get_logger()

class RedisClient:
    _pool: redis.ConnectionPool = None
    _client: redis.Redis = None

    @classmethod
    async def connect(cls):
        """Initialize async Redis connection pool"""
        if cls._pool is None:
            log.info("redis.connecting", url=settings.redis_url)
            cls._pool = redis.ConnectionPool.from_url(
                settings.redis_url,
                max_connections=settings.redis_max_connections,
                decode_responses=True
            )
            cls._client = redis.Redis(connection_pool=cls._pool)
            
            # Test connection
            try:
                await cls._client.ping()
                log.info("redis.connected")
            except Exception as e:
                log.error("redis.connection_failed", error=str(e))
                raise

    @classmethod
    async def disconnect(cls):
        """Close connection pool gracefully"""
        if cls._client:
            await cls._client.aclose()
            log.info("redis.disconnected")

    @classmethod
    def get_client(cls) -> redis.Redis:
        if cls._client is None:
            raise RuntimeError("Redis client not initialized. Call connect() first.")
        return cls._client

# Expose a global getter for convenience
def get_redis() -> redis.Redis:
    return RedisClient.get_client()
