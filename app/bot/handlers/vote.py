import logging
import html
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from redis.asyncio import Redis

from app.database.models import Vote, VoteStatus, User, PayoutTicket, TicketStatus, PayoutType
from app.bot.states import VoteStates, PayoutStates
from app.bot.keyboards.reply import get_phone_request_keyboard, get_main_menu_keyboard, get_cancel_keyboard
from app.bot.keyboards.inline import get_payout_choice_keyboard, get_openbudget_voting_keyboard
from app.services.anti_fraud import clean_phone_number, is_valid_uzbek_phone
from app.services.emoji_manager import emoji_manager
from app.config import settings

logger = logging.getLogger(__name__)
router = Router()

def check_is_admin(user_id: int) -> bool:
    return user_id in settings.admin_id_list

@router.message(F.text.contains("Bekor qilish"))
async def cancel_handler(message: Message, state: FSMContext):
    is_adm = check_is_admin(message.from_user.id)
    await state.clear()
    cancel_text = f"{emoji_manager.get('cancel')} <b>Jarayon bekor qilindi.</b>\n\n{emoji_manager.get('finger_down')} Menyudan bo'limni tanlang:"
    await message.answer(cancel_text, reply_markup=get_main_menu_keyboard(is_admin=is_adm), parse_mode="HTML")

@router.message(F.text.contains("Ovoz berish"), F.chat.type == "private")
async def start_self_vote_process(message: Message, state: FSMContext, session: AsyncSession, redis: Redis):
    await state.clear()
    await state.set_state(VoteStates.waiting_for_phone)

    target_id = settings.OPENBUDGET_PROJECT_ID
    project_url = f"https://openbudget.uz/boards/initiatives/initiative/{target_id}"

    text = (
        f"{emoji_manager.get('vote')} <b>OPENBUDGET'DA OVOZ BERISH VA PUL OLISH:</b>\n\n"
        f"1️⃣ <b>1-Qadam:</b> Quyidagi havola orqali OpenBudget rasmiy saytiga kiring va loyihamizga ovoz bering:\n"
        f"🔗 <a href='{project_url}'><b>OpenBudget Rasmiy Havolasi</b></a>\n\n"
        f"2️⃣ <b>2-Qadam:</b> Ovoz berib bo'lgach, ovoz bergan telefon raqamingizni pastdagi <b>📱 Telefon raqamni yuborish</b> tugmasi orqali yuboring yoki yozib yuboring:\n\n"
        f"<i>(Ovoz tekshirilishi bilan pulingiz darhol kartangizga o'tkazib beriladi)</i>"
    )
    
    # Send instructions with inline button
    await message.answer(
        text,
        reply_markup=get_openbudget_voting_keyboard(target_id),
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    # Also send the reply keyboard to easily share contact or cancel
    await message.answer(
        f"{emoji_manager.get('finger_down')} Ovoz bergan raqamingizni yuboring:",
        reply_markup=get_phone_request_keyboard(),
        parse_mode="HTML"
    )

@router.message(F.text.contains("Boshqa raqamdan ovoz"), F.chat.type == "private")
async def start_other_phone_vote(message: Message, state: FSMContext, redis: Redis):
    await state.clear()
    await state.set_state(VoteStates.waiting_for_phone)

    target_id = settings.OPENBUDGET_PROJECT_ID
    project_url = f"https://openbudget.uz/boards/initiatives/initiative/{target_id}"

    text = (
        f"{emoji_manager.get('other_phone')} <b>Boshqa telefon raqami orqali ovoz berish:</b>\n\n"
        f"1️⃣ <a href='{project_url}'><b>OpenBudget Rasmiy Havolasi</b></a> orqali boshqa raqamingizdan ovoz bering.\n\n"
        f"2️⃣ Ovoz bergan telefon raqamingizni quyidagi formatda yozib yuboring:\n"
        f"Masalan: <code>+998901234567</code> yoki <code>901234567</code>"
    )
    await message.answer(
        text,
        reply_markup=get_openbudget_voting_keyboard(target_id),
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    await message.answer(
        f"{emoji_manager.get('finger_down')} Ovoz berilgan raqamni yozing:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )

@router.message(VoteStates.waiting_for_phone, F.contact)
async def process_phone_contact(message: Message, state: FSMContext, session: AsyncSession):
    contact = message.contact
    raw_phone = contact.phone_number
    await handle_phone_submission(message, state, session, raw_phone)

@router.message(VoteStates.waiting_for_phone, F.text)
async def process_phone_text(message: Message, state: FSMContext, session: AsyncSession, redis: Redis):
    raw_text = message.text.strip() if message.text else ""
    raw_lower = raw_text.lower()

    if "statistika" in raw_lower:
        await state.clear()
        from app.bot.handlers.start import show_public_general_stats
        await show_public_general_stats(message, session)
        return

    if "to'lov holati" in raw_lower:
        await state.clear()
        from app.bot.handlers.payout import check_user_payout_status
        await check_user_payout_status(message, session)
        return

    if "to'lovlar kanali" in raw_lower or "kanal" in raw_lower:
        await state.clear()
        from app.bot.handlers.start import show_payout_channel
        await show_payout_channel(message)
        return

    if "mening havolam" in raw_lower or "havola" in raw_lower:
        await state.clear()
        from app.bot.handlers.start import show_referral_link
        await show_referral_link(message, session)
        return

    if "top referrallar" in raw_lower:
        await state.clear()
        from app.bot.handlers.start import show_top_referrals
        await show_top_referrals(message, session)
        return

    if "yordam" in raw_lower:
        await state.clear()
        from app.bot.handlers.start import show_help_rules
        await show_help_rules(message)
        return

    if "admin panel" in raw_lower or "admin" in raw_lower:
        await state.clear()
        from app.bot.handlers.admin import open_admin_panel
        await open_admin_panel(message, session, redis)
        return

    if "bekor qilish" in raw_lower:
        await cancel_handler(message, state)
        return

    await handle_phone_submission(message, state, session, raw_text)

async def handle_phone_submission(message: Message, state: FSMContext, session: AsyncSession, raw_phone: str, bot_identifier: str = "bot1"):
    normalized_phone = clean_phone_number(raw_phone)
    user_id = message.from_user.id
    is_adm = check_is_admin(user_id)

    if not is_valid_uzbek_phone(normalized_phone):
        await message.answer(
            f"{emoji_manager.get('warning')} <b>Telefon raqam noto'g'ri!</b>\n\n"
            f"Iltimos, O'zbekiston mobil raqamini kiriting (masalan: <code>+998901234567</code>):",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
        return

    # Check if this phone already has a VERIFIED vote
    stmt = select(Vote).where(Vote.voted_phone_number == normalized_phone, Vote.status == VoteStatus.VERIFIED)
    res = await session.execute(stmt)
    existing_vote = res.scalar_one_or_none()

    if existing_vote:
        await message.answer(
            f"{emoji_manager.get('danger')} <b>Ushbu raqam (+{normalized_phone}) orqali allaqachon ovoz berilgan va tasdiqlangan!</b>\n\n"
            f"Bitta raqamdan faqat 1 marta ovoz berish mumkin.",
            reply_markup=get_main_menu_keyboard(is_admin=is_adm),
            parse_mode="HTML"
        )
        await state.clear()
        return

    # Create or update pending vote record
    vote_stmt = select(Vote).where(Vote.voted_phone_number == normalized_phone)
    v_res = await session.execute(vote_stmt)
    vote_rec = v_res.scalar_one_or_none()

    if not vote_rec:
        vote_rec = Vote(
            telegram_id=user_id,
            voted_phone_number=normalized_phone,
            openbudget_project_id=settings.OPENBUDGET_PROJECT_ID,
            bot_identifier=bot_identifier,
            status=VoteStatus.PENDING_OTP
        )
        session.add(vote_rec)
        await session.commit()
        await session.refresh(vote_rec)

    await state.clear()

    # Transition directly to payout destination choice
    success_text = (
        f"{emoji_manager.get('success')} <b>Raqamingiz qabul qilindi: +{normalized_phone}</b>\n\n"
        f"{emoji_manager.get('paid_icon')} <b>Mukofot miqdori: {settings.DEFAULT_REWARD_PER_VOTE:,} UZS</b>\n\n"
        f"{emoji_manager.get('finger_down')} <b>To'lovni qaysi usulda olishni xohlaysiz?</b>"
    )

    await message.answer(
        success_text,
        reply_markup=get_payout_choice_keyboard(vote_id=vote_rec.id),
        parse_mode="HTML"
    )
