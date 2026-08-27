import logging
import asyncio
import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from app.config import settings
from app.database.session import init_db, AsyncSessionLocal
from app.bot.handlers import start, vote, payout, admin, group
from app.bot.handlers.group import broadcast_daily_countdown
from app.bot.middlewares.throttling import ThrottlingMiddleware

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Initialize Redis or fallback to MemoryStorage if auth fails
redis_client = None
storage = None

try:
    redis_client = Redis.from_url(settings.REDIS_URL, socket_connect_timeout=3)
    storage = RedisStorage(redis=redis_client)
except Exception as e:
    logger.warning(f"Redis initialization failed: {e}. Falling back to MemoryStorage.")
    storage = MemoryStorage()

bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher(storage=storage)

class DbSessionMiddleware:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    async def __call__(self, handler, event, data):
        async with self.session_factory() as session:
            data["session"] = session
            if redis_client:
                data["redis"] = redis_client
            return await handler(event, data)

dp.update.middleware(DbSessionMiddleware(AsyncSessionLocal))

dp.include_router(start.router)
dp.include_router(vote.router)
dp.include_router(payout.router)
dp.include_router(admin.router)
dp.include_router(group.router)

async def daily_countdown_scheduler():
    while True:
        try:
            logger.info("Running daily countdown broadcast to groups...")
            await broadcast_daily_countdown(bot, AsyncSessionLocal)
        except Exception as e:
            logger.error(f"Error in daily_countdown_scheduler: {e}")
        await asyncio.sleep(86400)

async def start_polling_loop():
    try:
        logger.info(">>> AIOGRAM 3 LONG POLLING STARTED SUCCESSFULLY <<<")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, handle_signals=False)
    except Exception as ex:
        logger.critical(f"FATAL POLLING LOOP ERROR: {ex}", exc_info=True)

use_polling = os.getenv("USE_POLLING", "false").lower() in ["true", "1", "yes"]

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Database tables...")
    await init_db()

    if redis_client:
        try:
            await redis_client.ping()
            logger.info("Redis authentication & connection ping successful!")
        except Exception as err:
            logger.warning(f"Redis ping failed ({err}). Switching FSM storage to MemoryStorage.")
            dp.fsm.storage = MemoryStorage()

    countdown_task = asyncio.create_task(daily_countdown_scheduler())

    if use_polling:
        logger.info("Starting bot in LONG POLLING mode...")
        polling_task = asyncio.create_task(start_polling_loop())
    else:
        webhook_url = f"{settings.WEBHOOK_DOMAIN}{settings.WEBHOOK_PATH}"
        logger.info(f"Setting Telegram Webhook to {webhook_url}")
        try:
            await bot.set_webhook(
                url=webhook_url,
                secret_token=settings.SECRET_TOKEN,
                drop_pending_updates=True
            )
        except Exception as e:
            logger.warning(f"Could not set webhook ({e}). Switching to Long Polling mode...")
            polling_task = asyncio.create_task(start_polling_loop())

    yield

    if 'polling_task' in locals() and not polling_task.done():
        polling_task.cancel()
    countdown_task.cancel()

    logger.info("Closing Telegram bot session...")
    try:
        await bot.delete_webhook()
        await bot.session.close()
        if redis_client:
            await redis_client.close()
    except Exception:
        pass

app = FastAPI(
    title="OpenBudget High-Load Telegram Bot Service",
    version="1.0.0",
    lifespan=lifespan
)

@app.post(settings.WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != settings.SECRET_TOKEN:
        logger.warning("Unauthorized webhook request with invalid secret token!")
        raise HTTPException(status_code=401, detail="Invalid secret token")

    update_data = await request.json()
    from aiogram.types import Update
    telegram_update = Update(**update_data)
    
    await dp.feed_update(bot=bot, update=telegram_update)
    return {"status": "ok"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "openbudget-bot", "environment": settings.ENV}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
