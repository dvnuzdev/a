import logging
import html
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database.models import PayoutTicket, Vote, PayoutType, TicketStatus, User, VoteStatus
from app.bot.states import PayoutStates
from app.bot.keyboards.inline import get_admin_ticket_keyboard, get_user_ticket_keyboard
from app.bot.keyboards.reply import get_main_menu_keyboard
from app.services.payout_service import create_payout_ticket
from app.services.anti_fraud import is_valid_card_number, is_valid_uzbek_phone, clean_phone_number
from app.services.emoji_manager import emoji_manager
from app.config import settings

logger = logging.getLogger(__name__)
router = Router()

def check_is_admin(user_id: int) -> bool:
    return user_id in settings.admin_id_list

async def get_user_verified_vote_count(session: AsyncSession, telegram_id: int) -> int:
    """Returns number of completed/verified votes for user."""
    stmt = select(func.count(Vote.id)).where(Vote.telegram_id == telegram_id, Vote.status == VoteStatus.VERIFIED)
    return (await session.execute(stmt)).scalar_one_or_none() or 0

@router.callback_query(F.data.startswith("payout_type:"))
async def handle_payout_type_choice(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    user_id = callback.from_user.id

    u_stmt = select(User).where(User.telegram_id == user_id)
    u_res = await session.execute(u_stmt)
    user_obj = u_res.scalar_one_or_none()

    balance = user_obj.balance_uzs if user_obj else 0
    ref_earnings = user_obj.referral_earnings_uzs if user_obj else 0

    # Referral bonus withdrawal restriction check (Requires at least 5 verified votes)
    if not check_is_admin(user_id) and ref_earnings > 0:
        v_count = await get_user_verified_vote_count(session, user_id)
        min_required = settings.MIN_VOTES_FOR_WITHDRAWAL
        if v_count < min_required:
            vote_earnings = max(0, balance - ref_earnings)
            if vote_earnings <= 0:
                alert_text = (
                    f"⚠️ REFERAL BONUSINI YECHIB OLISH CHEKLOVI!\n\n"
                    f"Referal bonuslarini kartangizga yechib olish uchun kamida {min_required} ta ovoz bergan bo'lishingiz kerak!\n\n"
                    f"📊 Siz bergan ovozlar: {v_count} / {min_required} ta\n"
                    f"<i>(Oddiy bergan ovozlaringiz pulini esa darhol yechib olishingiz mumkin)</i>"
                )
                await callback.answer(alert_text, show_alert=True)
                return

    parts = callback.data.split(":")
    p_type = parts[1] # 'card' or 'phone'
    vote_id_raw = parts[2]
    vote_id = int(vote_id_raw) if vote_id_raw.isdigit() else None

    await state.update_data(payout_type=p_type, target_vote_id=vote_id)

    if p_type == "card":
        await state.set_state(PayoutStates.waiting_for_card)
        text = (
            f"{emoji_manager.get('balance')} <b>Uzcard yoki Humo karta raqamingizni kiriting:</b>\n\n"
            "Format: <code>8600123456789012</code> yoki <code>9860123456789012</code> (16 ta raqam)"
        )
    else:
        await state.set_state(PayoutStates.waiting_for_payout_phone)
        text = (
            f"{emoji_manager.get('other_phone')} <b>Pul o'tkazib beriladigan telefon raqamingizni kiriting:</b>\n\n"
            "Format: <code>+998901234567</code> (Paynet/Click/Payme orqali tushiriladi)"
        )

    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()

@router.message(PayoutStates.waiting_for_card, F.chat.type == "private")
async def process_card_number_input(message: Message, state: FSMContext):
    raw_card = message.text.strip() if message.text else ""
    card_clean = raw_card.replace(" ", "")

    if not is_valid_card_number(card_clean):
        await message.answer(
            f"{emoji_manager.get('warning')} <b>Karta raqami noto'g'ri kiritildi!</b>\n"
            "Iltimos, 16 ta raqamdan iborat Uzcard yoki Humo karta raqamingizni qayta kiriting:",
            parse_mode="HTML"
        )
        return

    await state.update_data(clean_card_number=card_clean)
    await state.set_state(PayoutStates.waiting_for_card_holder_name)

    await message.answer(
        f"{emoji_manager.get('user_admin')} <b>Karta egasining Ismi va Familiyasini kiriting:</b>\n\n"
        "<i>Adashib kartani xato yuborib qo'ymaslik hamda to'lov xavfsizligi uchun, iltimos, kartangiz ustidagi ism va familiyangizni yozing (masalan: ALISHER NAVOIY):</i>",
        parse_mode="HTML"
    )

@router.message(PayoutStates.waiting_for_card_holder_name, F.chat.type == "private")
async def process_card_holder_name_input(message: Message, state: FSMContext, session: AsyncSession, bot_identifier: str = "bot1"):
    holder_name = message.text.strip() if message.text else ""
    user_id = message.from_user.id
    is_adm = check_is_admin(user_id)

    if len(holder_name) < 3:
        await message.answer(f"{emoji_manager.get('warning')} Iltimos, karta egasining to'liq ism va familiyasini kiriting (masalan: ALISHER NAVOIY):", parse_mode="HTML")
        return

    data = await state.get_data()
    card_clean = data.get("clean_card_number")
    vote_id = data.get("target_vote_id")

    success, msg, ticket = await create_payout_ticket(
        session=session,
        telegram_id=user_id,
        vote_id=vote_id,
        payout_type=PayoutType.CARD,
        destination=card_clean,
        card_holder_name=holder_name,
        bot=message.bot,
        bot_identifier=bot_identifier
    )

    await state.clear()

    if not success or not ticket:
        await message.answer(f"{emoji_manager.get('danger')} {msg}", reply_markup=get_main_menu_keyboard(is_admin=is_adm), parse_mode="HTML")
        return

    safe_holder = html.escape(holder_name)
    user_ack = (
        f"{emoji_manager.get('success')} <b>ZAYAVKA MUVAFFAQIYATLI YARATILDI!</b>\n\n"
        f"{emoji_manager.get('tickets_icon')} Zayavka kodi: <code>{ticket.ticket_code}</code>\n"
        f"{emoji_manager.get('balance')} Karta raqam: <code>{card_clean}</code>\n"
        f"{emoji_manager.get('user_admin')} Karta egasi: <b>{safe_holder}</b>\n"
        f"{emoji_manager.get('warning')} Holat: <b>Ko'rib chiqilmoqda (Pending)</b>\n\n"
        f"Adminlar to'lovni amalga oshirgach, sizga ushbu bot orqali bildirishnoma yuboriladi.\n\n"
        f"{emoji_manager.get('finger_down')} <b>Yana ovoz berish uchun pastdagi menyudan foydalaning:</b>"
    )
    await message.answer(
        user_ack,
        reply_markup=get_main_menu_keyboard(is_admin=is_adm),
        parse_mode="HTML"
    )

@router.message(PayoutStates.waiting_for_payout_phone, F.chat.type == "private")
async def process_payout_phone_input(message: Message, state: FSMContext, session: AsyncSession, bot_identifier: str = "bot1"):
    raw_phone = message.text.strip() if message.text else ""
    normalized = clean_phone_number(raw_phone)
    user_id = message.from_user.id
    is_adm = check_is_admin(user_id)

    if not is_valid_uzbek_phone(normalized):
        await message.answer(
            f"{emoji_manager.get('warning')} <b>Telefon raqami noto'g'ri kiritildi!</b>\n"
            "Iltimos, <code>+998XXXXXXXXX</code> formatidagi raqamni kiriting:",
            parse_mode="HTML"
        )
        return

    data = await state.get_data()
    vote_id = data.get("target_vote_id")

    success, msg, ticket = await create_payout_ticket(
        session=session,
        telegram_id=user_id,
        vote_id=vote_id,
        payout_type=PayoutType.PHONE,
        destination=normalized,
        bot=message.bot,
        bot_identifier=bot_identifier
    )

    await state.clear()

    if not success or not ticket:
        await message.answer(f"{emoji_manager.get('danger')} {msg}", reply_markup=get_main_menu_keyboard(is_admin=is_adm), parse_mode="HTML")
        return

    user_ack = (
        f"{emoji_manager.get('success')} <b>ZAYAVKA MUVAFFAQIYATLI YARATILDI!</b>\n\n"
        f"{emoji_manager.get('tickets_icon')} Zayavka kodi: <code>{ticket.ticket_code}</code>\n"
        f"{emoji_manager.get('other_phone')} Telefon raqam: <code>{normalized}</code>\n"
        f"{emoji_manager.get('warning')} Holat: <b>Ko'rib chiqilmoqda (Pending)</b>\n\n"
        f"Adminlar Paynet/Click orqali pul o'tkazgach, sizga bildirishnoma keladi.\n\n"
        f"{emoji_manager.get('finger_down')} <b>Yana ovoz berish uchun pastdagi menyudan foydalaning:</b>"
    )
    await message.answer(
        user_ack,
        reply_markup=get_main_menu_keyboard(is_admin=is_adm),
        parse_mode="HTML"
    )

@router.message(F.text.contains("To'lov holati"), F.chat.type == "private")
async def check_user_payout_status(message: Message, session: AsyncSession):
    user_id = message.from_user.id

    u_stmt = select(User).where(User.telegram_id == user_id)
    u_res = await session.execute(u_stmt)
    user_obj = u_res.scalar_one_or_none()

    balance = user_obj.balance_uzs if user_obj else 0
    ref_earnings = user_obj.referral_earnings_uzs if user_obj else 0
    v_count = await get_user_verified_vote_count(session, user_id)

    stmt = select(PayoutTicket).where(PayoutTicket.telegram_id == user_id).order_by(PayoutTicket.created_at.desc()).limit(5)
    res = await session.execute(stmt)
    tickets = res.scalars().all()

    text = f"{emoji_manager.get('balance')} <b>SIZNING BALANSINGIZ VA ZAYAVKALARINGIZ:</b>\n\n"
    text += f"{emoji_manager.get('paid_icon')} <b>Joriy Balans: {balance:,} UZS</b>\n"
    text += f"🎁 Referal Bonusi: <b>{ref_earnings:,} UZS</b> (Yechish uchun kamida 5 ta ovoz berish kerak)\n"
    text += f"{emoji_manager.get('vote')} <b>Siz bergan ovozlar: {v_count} ta</b>\n\n"

    if not tickets:
        text += (
            f"{emoji_manager.get('help')} <b>Sizda hali hech qanday to'lov zayavkasi mavjud emas.</b>\n\n"
            f"Ovoz berib balansingizni to'ldirish uchun <b>{emoji_manager.get('vote')} Ovoz berish</b> tugmasini bosing!"
        )
    else:
        text += f"{emoji_manager.get('tickets_icon')} <b>Oxirgi zayavkalaringiz holati:</b>\n"
        for t in tickets:
            st_emoji = emoji_manager.get('warning') if t.status == TicketStatus.PENDING else (emoji_manager.get('success') if t.status == TicketStatus.PAID else emoji_manager.get('danger'))
            text += f"🔹 Kodu: <code>{t.ticket_code}</code> | {st_emoji} <code>{t.status.value}</code> | {t.amount_uzs:,} UZS\n"

    await message.answer(text, reply_markup=get_main_menu_keyboard(is_admin=check_is_admin(user_id)), parse_mode="HTML")
