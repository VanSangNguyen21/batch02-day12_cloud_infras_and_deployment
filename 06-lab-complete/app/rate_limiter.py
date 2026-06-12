import time
import uuid
import logging
from collections import defaultdict, deque
from fastapi import HTTPException
from app.config import settings

logger = logging.getLogger(__name__)

# Redis initialization for rate limiter
USE_REDIS = False
_redis = None

if settings.redis_url:
    try:
        import redis
        _redis = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_timeout=2.0,
            socket_connect_timeout=2.0
        )
        _redis.ping()
        USE_REDIS = True
        logger.info("Rate limiter connected to Redis.")
    except Exception as e:
        logger.error(f"Rate Limiter Redis connection failed: {e}. Using in-memory fallback.")

_rate_windows: dict[str, deque] = defaultdict(deque)

def check_rate_limit(user_id: str):
    """
    Check if the user has exceeded the rate limit (10 req/min).
    Using Redis-based sliding window if available, otherwise falling back to in-memory sliding window.
    """
    limit = settings.rate_limit_per_minute
    
    if not USE_REDIS:
        now = time.time()
        window = _rate_windows[user_id]
        while window and window[0] < now - 60:
            window.popleft()
        if len(window) >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {limit} req/min. Please try again later.",
                headers={"Retry-After": "60"},
            )
        window.append(now)
        return

    # Redis-based sliding window using ZSET
    now = time.time()
    key = f"rate_limit:{user_id}"
    try:
        pipe = _redis.pipeline()
        # Remove elements older than 60s
        pipe.zremrangebyscore(key, 0, now - 60)
        # Get count
        pipe.zcard(key)
        # Add current element with unique identifier
        req_id = f"{now}-{uuid.uuid4().hex[:6]}"
        pipe.zadd(key, {req_id: now})
        # Set expire
        pipe.expire(key, 60)
        # Execute
        _, current_requests, _, _ = pipe.execute()
        
        if current_requests > limit:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {limit} req/min. Please try again later.",
                headers={"Retry-After": "60"},
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Redis rate limiter error: {e}. Falling back to in-memory.")
        # Fallback to in-memory logic
        now = time.time()
        window = _rate_windows[user_id]
        while window and window[0] < now - 60:
            window.popleft()
        if len(window) >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {limit} req/min. Please try again later.",
                headers={"Retry-After": "60"},
            )
        window.append(now)
