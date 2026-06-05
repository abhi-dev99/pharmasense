import json
import functools
from typing import Callable, Any
import structlog
from fastapi import Request, Response
from backend.cache.client import get_redis

log = structlog.get_logger()

def cache_response(ttl_seconds: int = 86400, key_builder: Callable = None):
    """
    Decorator to cache FastAPI endpoint responses.
    
    Args:
        ttl_seconds: Time to live in seconds (default 24h)
        key_builder: Function that takes (request, *args, **kwargs) and returns a string key.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(request: Request, *args, **kwargs) -> Any:
            if not key_builder:
                log.warning("cache.no_key_builder", endpoint=request.url.path)
                return await func(request, *args, **kwargs)
                
            cache_key = key_builder(request, *args, **kwargs)
            redis = get_redis()
            
            # Try cache first
            try:
                cached_data = await redis.get(cache_key)
                if cached_data:
                    log.debug("cache.hit", key=cache_key)
                    
                    # Assume JSON serializable dict for now
                    data = json.loads(cached_data)
                    # Add a cache_hit flag if it's a dict
                    if isinstance(data, dict):
                        data['cache_hit'] = True
                    return data
            except Exception as e:
                log.warning("cache.read_error", key=cache_key, error=str(e))
                
            # Cache miss, call actual function
            log.debug("cache.miss", key=cache_key)
            result = await func(request, *args, **kwargs)
            
            # Save to cache
            try:
                # If result is a Pydantic model, use model_dump
                if hasattr(result, "model_dump"):
                    dict_data = result.model_dump(mode='json')
                else:
                    dict_data = result
                    
                await redis.setex(cache_key, ttl_seconds, json.dumps(dict_data))
                log.debug("cache.set", key=cache_key, ttl=ttl_seconds)
            except Exception as e:
                log.warning("cache.write_error", key=cache_key, error=str(e))
                
            return result
        return wrapper
    return decorator
