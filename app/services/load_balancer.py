import time
import logging
from typing import Tuple
from redis.asyncio import Redis
from app.config import settings

logger = logging.getLogger(__name__)

async def evaluate_bot_load_and_redirect(redis: Redis, user_id: int) -> Tuple[bool, int]:
    """
    Evaluates active concurrent users in Redis over a 10-minute sliding window.
    Returns: (is_overloaded: bool, active_user_count: int)
    """
    now = time.time()
    window_start = now - 600 # 10 minutes ago
    redis_key = "bot_active_users_window"

    try:
        # 1. Remove expired active sessions older than 10 minutes
        await redis.zremrangebyscore(redis_key, 0, window_start)

        # 2. Count current active users in window
        active_count = await redis.zcard(redis_key) or 0

        # 3. Check if current user is already in active set
        user_score = await redis.zscore(redis_key, str(user_id))

        max_limit = getattr(settings, "MAX_CONCURRENT_USERS_PER_BOT", 100)

        # If user is new and load >= limit, trigger overload redirect
        if not user_score and active_count >= max_limit:
            logger.warning(f"Bot active load threshold reached ({active_count}/{max_limit}). Redirecting user {user_id}")
            return True, active_count

        # Register/refresh user active timestamp
        await redis.zadd(redis_key, {str(user_id): now})
        await redis.expire(redis_key, 1200)

        return False, active_count + 1

    except Exception as e:
        logger.error(f"Error evaluating bot load in Redis: {e}")
        return False, 0
