"""Redis-backed sliding window rate limiter (60s window per API key)."""
import hashlib
import logging
import time
import uuid

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

logger = logging.getLogger("agent.rate_limiter")
WINDOW_SECONDS = 60


def _key_id(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]


def check_rate_limit(key: str) -> None:
    """Enforce RATE_LIMIT_PER_MINUTE requests per 60s window stored in Redis."""
    if r is None:
        logger.warning("rate_limiter_skipped_no_redis")
        return

    limit = max(1, settings.rate_limit_per_minute)
    redis_key = f"rate_limit:{_key_id(key)}"
    now = time.time()
    window_start = now - WINDOW_SECONDS

    try:
        pipe = r.pipeline()
        pipe.zremrangebyscore(redis_key, 0, window_start)
        pipe.zcard(redis_key)
        _, current_count = pipe.execute()

        if current_count >= limit:
            oldest = r.zrange(redis_key, 0, 0, withscores=True)
            retry_after = (
                max(1, int(oldest[0][1] + WINDOW_SECONDS - now) + 1)
                if oldest
                else WINDOW_SECONDS
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "limit": limit,
                    "window_seconds": WINDOW_SECONDS,
                    "retry_after_seconds": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        member = f"{now}:{uuid.uuid4().hex[:8]}"
        pipe = r.pipeline()
        pipe.zadd(redis_key, {member: now})
        pipe.expire(redis_key, WINDOW_SECONDS)
        pipe.execute()
    except HTTPException:
        raise
    except (redis.RedisError, OSError) as exc:
        logger.warning(f"rate_limiter_redis_error: {exc}")
