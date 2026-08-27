import logging
from aiogram import Router, F
from aiogram.types import Message, ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.models import Group
from app.services.countdown import get_countdown_text
from app.services.emoji_manager import emoji_manager
from app.config import settings

logger = logging.getLogger(__name__)
router = Router()

def get_group_promo_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    """Returns promotional inline keyboard in Premium format with custom emoji icon and success style."""
    vote_emoji_id = emoji_manager.get_emoji_id("vote")
    kwargs = {
        "url": f"https://t.me/{bot_username}?start=group_promo",
        "style": "success"
    }
    if vote_emoji_id:
        kwargs["icon_custom_emoji_id"] = vote_emoji_id
        kwargs["text"] = "Botga O'tish hamda Ovoz Berish"
    else:
        plain_vote = emoji_manager.get_plain("vote")
        kwargs["text"] = f"{plain_vote} Botga O'tish hamda Ovoz Berish"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(**kwargs)
            ]
        ]
    )

@router.my_chat_member()
async def on_bot_group_state_change(event: ChatMemberUpdated, session: AsyncSession):
    """Triggered when bot is added to or removed from a group."""
    chat = event.chat
    if chat.type not in ["group", "supergroup"]:
        return

    new_status = event.new_chat_member.status
    stmt = select(Group).where(Group.chat_id == chat.id)
    res = await session.execute(stmt)
    db_group = res.scalar_one_or_none()

    if new_status in ["member", "administrator"]:
        if not db_group:
            db_group = Group(chat_id=chat.id, title=chat.title, is_active=True)
            session.add(db_group)
        else:
            db_group.is_active = True
        await session.commit()
        logger.info(f"Bot added to group: {chat.title} ({chat.id})")

        try:
            bot_info = await event.bot.get_me()
            countdown_text, _ = get_countdown_text()
            e_wel = emoji_manager.get("welcome")
            await event.bot.send_message(
                chat_id=chat.id,
                text=f"{e_wel} <b>Rahmat! Bot guruhga qo'shildi!</b>\n\n{countdown_text}",
                reply_markup=get_group_promo_keyboard(bot_info.username),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to send welcome promo to group {chat.id}: {e}")

    elif new_status in ["kicked", "left"]:
        if db_group:
            db_group.is_active = False
            await session.commit()

@router.message(Command("vaqt"), F.chat.type.in_(["group", "supergroup"]))
@router.message(Command("reklama"), F.chat.type.in_(["group", "supergroup"]))
@router.message(Command("ovoz"), F.chat.type.in_(["group", "supergroup"]))
async def group_countdown_cmd(message: Message):
    """Group command displaying live countdown and referral earning promo."""
    bot_info = await message.bot.get_me()
    countdown_text, _ = get_countdown_text()
    await message.answer(
        countdown_text,
        reply_markup=get_group_promo_keyboard(bot_info.username),
        parse_mode="HTML"
    )

async def broadcast_daily_countdown(bot, session_factory):
    """Background task sending daily countdown to all active groups."""
    async with session_factory() as session:
        stmt = select(Group).where(Group.is_active == True)
        res = await session.execute(stmt)
        groups = res.scalars().all()

        if not groups:
            return

        bot_info = await bot.get_me()
        countdown_text, is_started = get_countdown_text()
        keyboard = get_group_promo_keyboard(bot_info.username)
        e_spk = emoji_manager.get("speaker")

        for g in groups:
            try:
                await bot.send_message(
                    chat_id=g.chat_id,
                    text=f"{e_spk} <b>KUNLIK OGOHLANTIRISH:</b>\n\n{countdown_text}",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Failed daily countdown broadcast to group {g.chat_id}: {e}")
