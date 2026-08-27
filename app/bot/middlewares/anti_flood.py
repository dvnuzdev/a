import time
import logging
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

class AntiFloodMiddleware(BaseMiddleware):
    """
    High-Performance Anti-Flood / Throttling Middleware.
    Prevents bot spamming, command flooding, and DDoS attacks on Telegram updates.
    """

    def __init__(self, rate_limit_seconds: float = 0.8):
        self.rate_limit_seconds = rate_limit_seconds
        self.user_last_update: Dict[int, float] = {}

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
            now = time.time()
            last_time = self.user_last_update.get(user_id, 0.0)
            if now - last_time < self.rate_limit_seconds:
                logger.warning(f"Anti-Flood triggered for user {user_id}")
                if isinstance(event, CallbackQuery):
                    try:
                        await event.answer("⚠️ Iltimos, juda tez-tez tugma bosmang!", show_alert=True)
                    except Exception:
                        pass
                return  # Drop throttled update silently

            self.user_last_update[user_id] = now

            # Clean memory dict if it grows too large
            if len(self.user_last_update) > 10000:
                cutoff = now - 60.0
                self.user_last_update = {k: v for k, v in self.user_last_update.items() if v > cutoff}

        return await handler(event, data)
