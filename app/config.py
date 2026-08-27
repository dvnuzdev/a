import os
from typing import List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    BOT_TOKEN: str = "8709713103:AAFDufoeDTuo3R4VBQ3KgecniXM70x_kB38"
    WEBHOOK_DOMAIN: str = "https://152.70.17.29"
    WEBHOOK_PATH: str = "/webhook/main"
    SECRET_TOKEN: str = "openbudget-secret-webhook-token-2026"

    ADMIN_TELEGRAM_IDS: str = "6734269605,5916705324,8581373433"
    ADMIN_CHANNEL_ID: int = -5273763144
    PAYOUT_PROOF_CHANNEL_ID: int = -1004487937644
    PAYOUT_PROOF_CHANNEL_URL: str = "https://t.me/+FFC_JlR5pR8xOWNi"
    REQUIRED_CHANNEL: str = "@openbudget_channel"

    # High-Load Balancer Settings (250 users limit per bot)
    MAX_CONCURRENT_USERS_PER_BOT: int = 250
    SECONDARY_BOT_LINK: str = "https://t.me/opendvn2_bot?start=redirect"

    OPENBUDGET_PROJECT_ID: str = "board_123456"
    DEFAULT_REWARD_PER_VOTE: int = 25000
    REFERRAL_BONUS_PER_VOTE: int = 5000
    MANUAL_VOTE_OFFSET: int = 0
    MIN_VOTES_FOR_WITHDRAWAL: int = 5
    MAX_TOTAL_BUDGET: int = 125000000

    # PostgreSQL Fallback Parameters
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "railway"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    RAW_DATABASE_URL: str = ""

    # Redis Parameters
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    RAW_REDIS_URL: str = ""

    ENV: str = "production"
    LOG_LEVEL: str = "INFO"

    @property
    def admin_id_list(self) -> List[int]:
        raw = os.getenv("ADMIN_TELEGRAM_IDS") or self.ADMIN_TELEGRAM_IDS
        return [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]

    @property
    def DATABASE_URL(self) -> str:
        url = (
            os.getenv("DATABASE_URL") or 
            os.getenv("POSTGRES_URL") or 
            os.getenv("DATABASE_PRIVATE_URL") or 
            os.getenv("DATABASE_PUBLIC_URL") or
            os.getenv("POSTGRESQL_URL")
        )

        if not url:
            user = os.getenv("POSTGRESUSER") or os.getenv("POSTGRES_USER") or self.POSTGRES_USER
            password = os.getenv("POSTGRESPASSWORD") or os.getenv("POSTGRES_PASSWORD") or self.POSTGRES_PASSWORD
            host = os.getenv("POSTGRESHOST") or os.getenv("POSTGRES_HOST") or self.POSTGRES_HOST
            port = os.getenv("POSTGRESPORT") or os.getenv("POSTGRES_PORT") or str(self.POSTGRES_PORT)
            db = os.getenv("POSTGRESDATABASE") or os.getenv("POSTGRES_DB") or self.POSTGRES_DB
            url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"

        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

        return url

    @property
    def REDIS_URL(self) -> str:
        url = (
            os.getenv("REDIS_URL") or 
            os.getenv("REDIS_PRIVATE_URL") or 
            os.getenv("REDIS_PUBLIC_URL") or 
            self.RAW_REDIS_URL
        )
        if not url:
            password = os.getenv("REDISPASSWORD") or os.getenv("REDIS_PASSWORD")
            host = os.getenv("REDISHOST") or os.getenv("REDIS_HOST") or self.REDIS_HOST
            port = os.getenv("REDISPORT") or os.getenv("REDIS_PORT") or str(self.REDIS_PORT)
            if password:
                url = f"redis://default:{password}@{host}:{port}/0"
            else:
                url = f"redis://{host}:{port}/0"
        return url

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
