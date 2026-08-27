import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ChatMemberStatus
from app.config import settings

logger = logging.getLogger(__name__)

def get_subscription_keyboard(channel_username: str) -> InlineKeyboardMarkup:
    """
    Returns inline keyboard matching the user screenshot:
    - Row 1 (Blue URL Button): 📢 Obuna bo'lish
    - Row 2 (Green Action Button): ✔️ Tekshirish
    """
    clean_channel = channel_username.replace("@", "")
    url = f"https://t.me/{clean_channel}"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Obuna bo'lish",
                    url=url
                )
            ],
            [
                InlineKeyboardButton(
                    text="✔️ Tekshirish",
                    callback_data="check_subscription"
                )
            ]
        ]
    )
    return keyboard

async def is_user_subscribed(bot, user_id: int, channel_id_or_username: str) -> bool:
    """Checks if user is member, administrator, or creator of mandatory channel."""
    try:
        member = await bot.get_chat_member(chat_id=channel_id_or_username, user_id=user_id)
        return member.status in [
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR
        ]
    except Exception as e:
        logger.error(f"Error checking channel subscription for user {user_id} in {channel_id_or_username}: {e}")
        # Default to True if channel check fails to prevent blocking users due to bot admin permission issues
        return True

class SubscriptionMiddleware(BaseMiddleware):
    """Middleware enforcing mandatory channel subscription before bot usage."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Skip check for admins or if no required channel is set
        user_id = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if not user_id:
            return await handler(event, data)

        if user_id in settings.admin_id_list:
            return await handler(event, data)

        bot = data["bot"]
        required_channel = getattr(settings, "REQUIRED_CHANNEL", "@openbudget_channel")

        # Allow 'check_subscription' callback query to bypass middleware to allow re-evaluation
        if isinstance(event, CallbackQuery) and event.data == "check_subscription":
            return await handler(event, data)

        subscribed = await is_user_subscribed(bot, user_id, required_channel)

        if not subscribed:
            sub_text = "❌ **Botdan to'liq foydalanish uchun quyidagi kanallarga obuna bo'ling:**"
            kb = get_subscription_keyboard(required_channel)

            if isinstance(event, Message):
                await event.answer(sub_text, reply_markup=kb, parse_mode="Markdown")
            elif isinstance(event, CallbackQuery):
                await event.answer("⚠️ Botdan foydalanish uchun kanallarga obuna bo'ling!", show_alert=True)
                await event.message.answer(sub_text, reply_markup=kb, parse_mode="Markdown")
            return

        return await handler(event, data)
