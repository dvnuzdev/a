import logging
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import settings
from app.database.models import Base

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def init_db():
    """Verify and initialize database tables with exponential retry logic and auto-migration."""
    max_retries = 10
    for attempt in range(1, max_retries + 1):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                # Auto-migrate newly added columns if they don't exist in pre-existing tables
                await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS manual_votes_offset INTEGER DEFAULT 0;"))
                await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_earnings_uzs BIGINT DEFAULT 0;"))
            logger.info("Database tables & schema auto-migrations verified/applied successfully.")
            return
        except Exception as e:
            logger.warning(f"Database connection attempt {attempt}/{max_retries} failed: {e}. Retrying in 2s...")
            if attempt == max_retries:
                logger.error("Database connection failed permanently after max retries.")
                raise e
            await asyncio.sleep(2)

async def get_db():
    """Dependency for getting DB session in FastAPI handlers."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
