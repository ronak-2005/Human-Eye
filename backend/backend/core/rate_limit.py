"""Rate limiting — called by auth.py only, not directly by routes."""
import redis.asyncio as aioredis
from fastapi import HTTPException, status
from core.config import settings

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def check_rate_limit(key_id: str):
    redis = await get_redis()
    redis_key = f"rl:{key_id}"
    current = await redis.incr(redis_key)
    if current == 1:
        await redis.expire(redis_key, 60)
    if current > settings.RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limit_exceeded",
                "message": f"Limit is {settings.RATE_LIMIT_PER_MINUTE} requests/minute",
                "code": "RATE_LIMIT",
            },
        )
