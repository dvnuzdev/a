import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from app.config import settings
from app.database.session import init_db, AsyncSessionLocal
from app.services.emoji_manager import emoji_manager
from app.bot.middlewares.anti_flood import AntiFloodMiddleware
from app.bot.handlers import start, vote, payout, admin, group

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Initializing Database tables...")
    await init_db()

    # Redis or MemoryStorage fallback
    storage = MemoryStorage()
    redis_client = None
    try:
        redis_client = Redis.from_url(settings.REDIS_URL, socket_connect_timeout=3)
        await redis_client.ping()
        storage = RedisStorage(redis=redis_client)
        logger.info("Redis authentication & connection successful!")
        await emoji_manager.load_emojis(redis_client)
    except Exception as e:
        logger.warning(f"Redis fallback to MemoryStorage: {e}")

    clean_token = (os.getenv("BOT_TOKEN") or settings.BOT_TOKEN).strip().strip('"').strip("'")
    logger.info(f"Connecting bot with token prefix: {clean_token[:10]}... (len: {len(clean_token)})")

    bot = Bot(token=clean_token)
    dp = Dispatcher(storage=storage)

    try:
        bot_info = await bot.get_me()
    except Exception as err:
        logger.error(f"❌ TELEGRAM BOT TOKEN XATOSI: {err}")
        logger.error("Iltimos, Railway Variables bo'limidagi BOT_TOKEN to'g'riligini tekshiring!")
        raise err

    bot_identifier = "bot2" if (bot_info.id == 8913170688 or "8913170688" in clean_token) else "bot1"
    logger.info(f"Bot identified as: {bot_identifier.upper()} (@{bot_info.username})")

    # Anti-Flood Middleware Registration
    anti_flood = AntiFloodMiddleware(rate_limit_seconds=0.8)
    dp.message.middleware(anti_flood)
    dp.callback_query.middleware(anti_flood)

    class DbSessionMiddleware:
        def __init__(self, session_factory, redis_conn=None, bot_id="bot1"):
            self.session_factory = session_factory
            self.redis_conn = redis_conn
            self.bot_id = bot_id

        async def __call__(self, handler, event, data):
            if self.redis_conn:
                await emoji_manager.load_emojis(self.redis_conn)
            async with self.session_factory() as session:
                data["session"] = session
                data["redis"] = self.redis_conn
                data["bot_identifier"] = self.bot_id
                return await handler(event, data)

    dp.update.middleware(DbSessionMiddleware(AsyncSessionLocal, redis_conn=redis_client, bot_id=bot_identifier))

    dp.include_router(start.router)
    dp.include_router(vote.router)
    dp.include_router(payout.router)
    dp.include_router(admin.router)
    dp.include_router(group.router)

    logger.info("Deleting any active webhook without dropping pending updates...")
    await bot.delete_webhook(drop_pending_updates=False)

    logger.info(f">>> BOT LAUNCHED IN STANDALONE POLLING MODE: @{bot_info.username} (ID: {bot_info.id}) [{bot_identifier.upper()}] <<<")

    allowed_updates = dp.resolve_used_update_types()
    await dp.start_polling(bot, allowed_updates=allowed_updates)

if __name__ == "__main__":
    asyncio.run(main())
