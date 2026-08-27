import logging
import html
import base64
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from redis.asyncio import Redis

from app.database.models import Vote, VoteStatus, User, PayoutTicket, TicketStatus, PayoutType
from app.bot.states import VoteStates, PayoutStates
from app.bot.keyboards.reply import get_phone_request_keyboard, get_main_menu_keyboard, get_cancel_keyboard
from app.bot.keyboards.inline import get_payout_choice_keyboard
from app.services.anti_fraud import clean_phone_number, is_valid_uzbek_phone
from app.services.emoji_manager import emoji_manager
from app.services.openbudget_api import openbudget_api
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
async def start_self_vote_process(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(VoteStates.waiting_for_phone)

    text = (
        f"{emoji_manager.get('vote')} <b>OPENBUDGET TIZIMIDA OVOZ BERISH</b>\n\n"
        f"1️⃣ Telefon raqamingizni pastdagi <b>📱 Telefon raqamni yuborish</b> tugmasi orqali yuboring yoki yozib yuboring.\n"
        f"2️⃣ Bot sizga rasmdagi Captcha kodini yuboradi.\n"
        f"3️⃣ SMS kodni kiritasiz va pulingiz darhol beriladi!\n\n"
        f"{emoji_manager.get('paid_icon')} <b>1 ta ovoz uchun mukofot: {settings.DEFAULT_REWARD_PER_VOTE:,} UZS</b>"
    )
    
    await message.answer(
        text,
        reply_markup=get_phone_request_keyboard(),
        parse_mode="HTML"
    )

@router.message(F.text.contains("Boshqa raqamdan ovoz"), F.chat.type == "private")
async def start_other_phone_vote(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(VoteStates.waiting_for_phone)

    text = (
        f"{emoji_manager.get('other_phone')} <b>Boshqa telefon raqami orqali ovoz berish:</b>\n\n"
        f"Ovoz beriladigan telefon raqamini quyidagi formatda yozib yuboring:\n"
        f"Masalan: <code>+998901234567</code> yoki <code>901234567</code>"
    )
    await message.answer(
        text,
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

    wait_msg = await message.answer("⏳ OpenBudget serveriga ulanilmoqda...", reply_markup=get_cancel_keyboard())

    # Fetch captcha from OpenBudget
    ok, msg, captcha_data = await openbudget_api.get_captcha()
    if not ok or not captcha_data.get("image"):
        await wait_msg.edit_text(
            f"🔴 <b>OpenBudget serveriga ulanishda xatolik yuz berdi:</b>\n{msg}\n\nIltimos birozdan so'ng qayta urinib ko'ring.",
            reply_markup=get_main_menu_keyboard(is_admin=is_adm),
            parse_mode="HTML"
        )
        await state.clear()
        return

    captcha_key = captcha_data.get("captchaKey")
    image_b64 = captcha_data.get("image")

    try:
        try:
            await wait_msg.delete()
        except Exception:
            pass

        image_bytes = base64.b64decode(image_b64)
        photo = BufferedInputFile(image_bytes, filename="captcha.jpg")

        await message.answer_photo(
            photo=photo,
            caption=(
                f"📱 <b>Raqam: +{normalized_phone}</b>\n\n"
                f"🖼 <b>Yuqoridagi rasmdagi tasdiqlash (Captcha) kodini kiriting:</b>"
            ),
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )

        await state.update_data(
            phone=normalized_phone,
            captcha_key=captcha_key,
            bot_identifier=bot_identifier
        )
        await state.set_state(VoteStates.waiting_for_captcha)

    except Exception as e:
        logger.error(f"Error rendering captcha photo: {e}")
        await message.answer(
            "🔴 Rasmni yuklab bo'lmadi. Qayta urinib ko'ring.",
            reply_markup=get_main_menu_keyboard(is_admin=is_adm)
        )
        await state.clear()

@router.message(VoteStates.waiting_for_captcha, F.text)
async def process_captcha_text(message: Message, state: FSMContext, session: AsyncSession):
    raw_text = message.text.strip() if message.text else ""
    if "bekor qilish" in raw_text.lower():
        await cancel_handler(message, state)
        return

    data = await state.get_data()
    phone = data.get("phone")
    captcha_key = data.get("captcha_key")
    bot_identifier = data.get("bot_identifier", "bot1")

    if not phone or not captcha_key:
        await state.clear()
        await message.answer("⚠️ Jarayon eskirgan. Qaytadan /start bosing.", reply_markup=get_main_menu_keyboard())
        return

    wait_msg = await message.answer("⏳ SMS kod so'ralmoqda...", reply_markup=get_cancel_keyboard())

    # Send OTP request to OpenBudget API
    ok, resp_msg, extra_data = await openbudget_api.send_otp(
        phone_number=phone,
        captcha_key=captcha_key,
        captcha_result=raw_text
    )

    if not ok:
        await wait_msg.delete()
        # If captcha was invalid or server error, fetch a new captcha immediately
        if "captcha" in resp_msg.lower() or "noto'g'ri" in resp_msg.lower():
            cap_ok, _, new_captcha = await openbudget_api.get_captcha()
            if cap_ok and new_captcha.get("image"):
                image_bytes = base64.b64decode(new_captcha.get("image"))
                photo = BufferedInputFile(image_bytes, filename="captcha.jpg")
                await message.answer_photo(
                    photo=photo,
                    caption=(
                        f"❌ <b>Captcha kodi noto'g'ri kiritildi!</b>\n\n"
                        f"🖼 <b>Yangi rasmdagi tasdiqlash kodini kiriting:</b>"
                    ),
                    reply_markup=get_cancel_keyboard(),
                    parse_mode="HTML"
                )
                await state.update_data(captcha_key=new_captcha.get("captchaKey"))
                return

        await message.answer(
            f"❌ <b>Xatolik:</b> {resp_msg}",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="HTML"
        )
        await state.clear()
        return

    # OTP successfully sent
    token = extra_data.get("token") or extra_data.get("otpKey") or "token_ok"
    await state.update_data(token=token, phone=phone)
    await state.set_state(VoteStates.waiting_for_otp)

    await wait_msg.delete()
    await message.answer(
        f"📩 <b>+{phone} raqamingizga 6 xonali SMS tasdiqlash kodi yuborildi!</b>\n\n"
        f"Iltimos, kelgan SMS kodni kiriting:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )

@router.message(VoteStates.waiting_for_otp, F.text)
async def process_otp_text(message: Message, state: FSMContext, session: AsyncSession):
    otp_code = message.text.strip() if message.text else ""
    if "bekor qilish" in otp_code.lower():
        await cancel_handler(message, state)
        return

    data = await state.get_data()
    phone = data.get("phone")
    token = data.get("token")
    bot_identifier = data.get("bot_identifier", "bot1")
    user_id = message.from_user.id
    is_adm = check_is_admin(user_id)

    if not phone:
        await state.clear()
        await message.answer("⚠️ Jarayon eskirgan. Qaytadan /start bosing.", reply_markup=get_main_menu_keyboard())
        return

    clean_otp = "".join(filter(str.isdigit, otp_code))
    if len(clean_otp) < 4 or len(clean_otp) > 8:
        await message.answer(
            "⚠️ <b>SMS kodi noto'g'ri formatda!</b>\nIltimos, telefoningizga kelgan 6 xonali raqamli kodni kiriting:",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
        return

    wait_msg = await message.answer("⏳ Ovoz tekshirilmoqda va tasdiqlanmoqda...", reply_markup=get_cancel_keyboard())

    # Verify OTP with OpenBudget API
    ok, verify_msg, tx_id = await openbudget_api.verify_otp(
        phone_number=phone,
        otp_code=clean_otp,
        token=token
    )

    await wait_msg.delete()

    if not ok:
        await message.answer(
            f"❌ <b>Xatolik:</b> {verify_msg}\n\nIltimos, SMS kodni qaytadan to'g'ri kiriting:",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
        return

    # OTP verified successfully! Create or update Vote record
    vote_stmt = select(Vote).where(Vote.voted_phone_number == phone)
    v_res = await session.execute(vote_stmt)
    vote_rec = v_res.scalar_one_or_none()

    if not vote_rec:
        vote_rec = Vote(
            telegram_id=user_id,
            voted_phone_number=phone,
            openbudget_project_id=settings.OPENBUDGET_PROJECT_ID,
            bot_identifier=bot_identifier,
            status=VoteStatus.VERIFIED
        )
        session.add(vote_rec)
    else:
        vote_rec.status = VoteStatus.VERIFIED

    await session.commit()
    await session.refresh(vote_rec)

    # Award referral bonus to inviter if user was referred
    user_stmt = select(User).where(User.telegram_id == user_id)
    u_res = await session.execute(user_stmt)
    cur_user = u_res.scalar_one_or_none()

    if cur_user and cur_user.referred_by and settings.REFERRAL_BONUS_PER_VOTE > 0:
        inviter_stmt = select(User).where(User.telegram_id == cur_user.referred_by)
        inv_res = await session.execute(inviter_stmt)
        inviter = inv_res.scalar_one_or_none()
        if inviter:
            inviter.balance += settings.REFERRAL_BONUS_PER_VOTE
            await session.commit()
            try:
                await message.bot.send_message(
                    chat_id=inviter.telegram_id,
                    text=(
                        f"🎉 <b>Siz taklif qilgan do'stingiz ovoz berdi!</b>\n\n"
                        f"💰 Sizga <b>+{settings.REFERRAL_BONUS_PER_VOTE:,} UZS</b> referral bonusi berildi!"
                    ),
                    parse_mode="HTML"
                )
            except Exception:
                pass

    await state.clear()

    success_text = (
        f"🎉 <b>Tabriklaymiz! Ovozingiz OpenBudget tizimida muvaffaqiyatli qabul qilindi!</b>\n\n"
        f"📱 <b>Raqam:</b> +{phone}\n"
        f"🆔 <b>Tranzaksiya:</b> <code>{tx_id}</code>\n"
        f"💰 <b>Mukofot: {settings.DEFAULT_REWARD_PER_VOTE:,} UZS</b>\n\n"
        f"{emoji_manager.get('finger_down')} <b>To'lovni qaysi usulda olishni xohlaysiz?</b>"
    )

    await message.answer(
        success_text,
        reply_markup=get_payout_choice_keyboard(vote_id=vote_rec.id),
        parse_mode="HTML"
    )

