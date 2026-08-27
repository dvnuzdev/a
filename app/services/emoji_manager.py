import logging
import json
import os
from typing import Dict, Optional
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

CUSTOM_EMOJIS_FILE = "custom_emojis.json"

DEFAULT_EMOJIS = {
    "welcome": "🌟",
    "building": "🏛️",
    "timer": "⏳",
    "calendar": "📅",
    "speaker": "📢",
    "finger_down": "👇",
    "vote": "🗳️",
    "other_phone": "📲",
    "channel": "📢",
    "link": "🔗",
    "top_ref": "🏆",
    "balance": "💳",
    "help": "ℹ️",
    "admin": "⚙️",
    "cancel": "❌",
    "num_1": "1️⃣",
    "num_2": "2️⃣",
    "num_3": "3️⃣",
    "user_admin": "👤",
    "user_owner": "👑",
    "bot_icon": "🤖",
    "system_icon": "🌐",
    "users_icon": "👥",
    "votes_icon": "🗳️",
    "tickets_icon": "⏳",
    "groups_icon": "💬",
    "pin_icon": "📌",
    "lock_icon": "🔒",
    "paid_icon": "✅",
    "success": "🟢",
    "danger": "🔴",
    "warning": "🟡"
}

EMOJI_LABELS = {
    "welcome": "🌟 Start Xush kelibsiz",
    "building": "🏛️ OpenBudget Bino",
    "timer": "⏳ Taymer / Soat",
    "calendar": "📅 Kalendar / Sana",
    "speaker": "📢 Bildirishnoma Spiker",
    "finger_down": "👇 Pastga ko'rsatgich",
    "vote": "🗳️ Ovoz berish Tugmasi",
    "other_phone": "📲 Boshqa raqam Tugmasi",
    "channel": "📢 To'lovlar kanali Tugmasi",
    "link": "🔗 Mening havolam Tugmasi",
    "top_ref": "🏆 Top Referrallar Tugmasi",
    "balance": "💳 To'lov holati Tugmasi",
    "help": "ℹ️ Yordam / Qoidalar Tugmasi",
    "admin": "⚙️ Admin Panel Tugmasi",
    "cancel": "❌ Bekor qilish Tugmasi",
    "num_1": "1️⃣ Qoida 1 Emojisi",
    "num_2": "2️⃣ Qoida 2 Emojisi",
    "num_3": "3️⃣ Qoida 3 Emojisi",
    "user_admin": "👤 Admin Foydalanuvchi Icon",
    "user_owner": "👑 Ega Foydalanuvchi Icon",
    "users_icon": "👥 Foydalanuvchilar statistikasi",
    "votes_icon": "🗳️ Ovozlar statistikasi",
    "tickets_icon": "⏳ Zayavkalar statistikasi",
    "groups_icon": "💬 Faol guruhlar statistikasi",
    "bot_icon": "🤖 Bot statistikasi ikonasi",
    "system_icon": "🌐 Tizim statistikasi ikonasi",
    "pin_icon": "📌 Loyiha ID ikonasi",
    "lock_icon": "🔒 Band summa ikonasi",
    "paid_icon": "✅ To'langan summa ikonasi",
    "success": "🟢 Muvaffaqiyatli status",
    "danger": "🔴 Rad etilgan status",
    "warning": "🟡 Kutilayotgan status"
}

class EmojiManager:
    """Manages Telegram Premium Custom Emojis (<tg-emoji emoji-id="...">) with disk & Redis persistence."""

    def __init__(self):
        self._cache: Dict[str, str] = {}
        self._load_from_file()

    def _load_from_file(self):
        """Loads custom emojis from local JSON file to guarantee survival across redeploys."""
        if os.path.exists(CUSTOM_EMOJIS_FILE):
            try:
                with open(CUSTOM_EMOJIS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._cache.update(data)
                        logger.info(f"Loaded {len(data)} custom emojis from {CUSTOM_EMOJIS_FILE}")
            except Exception as e:
                logger.warning(f"Failed to load custom_emojis.json: {e}")

    def _save_to_file(self):
        """Persists current custom emoji cache to local JSON file."""
        try:
            with open(CUSTOM_EMOJIS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save custom_emojis.json: {e}")

    async def load_emojis(self, redis: Optional[Redis] = None):
        """Preload custom emoji IDs from Redis if available, merging with file cache."""
        self._load_from_file()
        if not redis:
            return
        try:
            stored = await redis.hgetall("bot_custom_emojis")
            if stored:
                redis_data = {k.decode('utf-8'): v.decode('utf-8') for k, v in stored.items()}
                self._cache.update(redis_data)
                self._save_to_file()
        except Exception as e:
            logger.warning(f"Could not load custom emojis from Redis: {e}")

    async def set_custom_emoji(self, key: str, emoji_id: str, redis: Optional[Redis] = None):
        """Set custom_emoji_id for a specific key, persisting to memory, disk, and Redis."""
        self._cache[key] = emoji_id
        self._save_to_file()

        if redis:
            try:
                await redis.hset("bot_custom_emojis", key, emoji_id)
            except Exception as e:
                logger.error(f"Failed to persist custom emoji in Redis: {e}")

    def get(self, key: str) -> str:
        """Returns HTML formatted <tg-emoji> if custom_emoji_id exists, else fallback standard emoji."""
        fallback = DEFAULT_EMOJIS.get(key, "🔹")
        emoji_id = self._cache.get(key)
        if emoji_id:
            return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'
        return fallback

    def get_emoji_id(self, key: str) -> Optional[str]:
        """Returns custom_emoji_id string if configured, else None."""
        return self._cache.get(key)

    def get_plain(self, key: str) -> str:
        """Returns standard emoji string for keyboard buttons."""
        return DEFAULT_EMOJIS.get(key, "🔹")

emoji_manager = EmojiManager()
