import time
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

class ThrottlingMiddleware(BaseMiddleware):
    """Middleware for rate limiting users (anti-spam / anti-DDoS)."""

    def __init__(self, redis_client: Redis, limit: float = 1.0):
        self.redis = redis_client
        self.limit = limit
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if user_id:
            key = f"rate_limit:{user_id}"
            try:
                is_throttled = await self.redis.get(key)
                if is_throttled:
                    if isinstance(event, Message):
                        await event.answer("⚠️ Iltimos, juda tez-tez tugmalarni bosmang. Biroz kuting.")
                    elif isinstance(event, CallbackQuery):
                        await event.answer("⚠️ Juda tez-tez bosyapsiz. Biroz kuting.", show_alert=True)
                    return
                
                await self.redis.set(key, "1", px=int(self.limit * 1000))
            except Exception as e:
                logger.error(f"Redis throttling error: {e}")

        return await handler(event, data)
