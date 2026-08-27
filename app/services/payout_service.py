import random
import string
import logging
import html
from typing import Tuple, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from aiogram import Bot
from app.config import settings
from app.database.models import (
    PayoutTicket, Vote, User, SystemBudget, TicketStatus, PayoutType, VoteStatus, AuditLog
)
from app.services.anti_fraud import evaluate_fraud_risk, clean_phone_number
from app.services.emoji_manager import emoji_manager

logger = logging.getLogger(__name__)

def generate_ticket_code() -> str:
    """Generate a unique ticket code e.g. OB-872910."""
    digits = ''.join(random.choices(string.digits, k=6))
    return f"OB-{digits}"

def mask_destination(dest: str) -> str:
    """Mask card or phone number for privacy before public broadcast."""
    if len(dest) == 16 and dest.isdigit():
        return f"{dest[:4]} **** **** {dest[-4:]}"
    elif dest.startswith("+998") and len(dest) == 13:
        return f"{dest[:6]} *** *{dest[-2:]}"
    return f"{dest[:3]}***{dest[-2:]}"

async def get_or_create_budget(session: AsyncSession) -> SystemBudget:
    """Fetch or initialize system budget tracker object."""
    stmt = select(SystemBudget).where(SystemBudget.id == 1)
    res = await session.execute(stmt)
    budget = res.scalar_one_or_none()
    if not budget:
        budget = SystemBudget(
            id=1,
            total_budget_uzs=settings.MAX_TOTAL_BUDGET,
            total_reserved_uzs=0,
            total_paid_uzs=0
        )
        session.add(budget)
        await session.flush()
    return budget

async def create_payout_ticket(
    session: AsyncSession,
    telegram_id: int,
    vote_id: Optional[int],
    payout_type: PayoutType,
    destination: str,
    card_holder_name: Optional[str] = None,
    amount_uzs: int = None,
    bot: Optional[Bot] = None,
    bot_identifier: str = "bot1"
) -> Tuple[bool, str, Optional[PayoutTicket]]:
    """
    Atomically creates a new PayoutTicket (Zayavka) and sends instant admin notification card.
    Supports card holder name verification and balance deductions.
    """
    reward_amount = amount_uzs or settings.DEFAULT_REWARD_PER_VOTE
    clean_dest = destination.replace(" ", "")

    user_stmt = select(User).where(User.telegram_id == telegram_id)
    u_res = await session.execute(user_stmt)
    user_obj = u_res.scalar_one_or_none()

    if not user_obj:
        return False, "Foydalanuvchi ma'lumoti topilmadi.", None

    # 1. Verify Vote Exists if vote_id provided
    if vote_id:
        vote_stmt = select(Vote).where(Vote.id == vote_id, Vote.telegram_id == telegram_id)
        vote_res = await session.execute(vote_stmt)
        vote = vote_res.scalar_one_or_none()

        if not vote:
            return False, "Tasdiqlangan ovoz ma'lumoti topilmadi.", None

        ticket_stmt = select(PayoutTicket).where(PayoutTicket.vote_id == vote_id)
        t_res = await session.execute(ticket_stmt)
        existing_ticket = t_res.scalar_one_or_none()
        if existing_ticket:
            return False, f"Ushbu ovoz bo'yicha tayyor zayavka mavjud (#{existing_ticket.ticket_code}).", existing_ticket

    # 2. Anti-Fraud Evaluation
    is_high_risk, risk_reason = await evaluate_fraud_risk(session, telegram_id, clean_dest)
    ticket_initial_status = TicketStatus.HIGH_RISK if is_high_risk else TicketStatus.PENDING

    # 3. Create Ticket
    code = generate_ticket_code()
    clean_holder = card_holder_name.strip() if card_holder_name else None

    new_ticket = PayoutTicket(
        ticket_code=code,
        telegram_id=telegram_id,
        vote_id=vote_id,
        bot_identifier=bot_identifier,
        payout_type=payout_type,
        destination=clean_dest,
        card_holder_name=clean_holder,
        amount_uzs=reward_amount,
        status=ticket_initial_status,
        risk_reason=risk_reason if is_high_risk else None,
        created_at=datetime.utcnow()
    )
    session.add(new_ticket)

    # 4. Update Reserved System Budget
    budget = await get_or_create_budget(session)
    budget.total_reserved_uzs += reward_amount

    # 5. Audit Log
    audit = AuditLog(
        event_type="TICKET_CREATED",
        telegram_id=telegram_id,
        details=f"Ticket {code} created for {clean_dest} (Holder: {clean_holder}, Amount: {reward_amount} UZS). HighRisk={is_high_risk}, Bot={bot_identifier}"
    )
    session.add(audit)

    await session.commit()
    logger.info(f"Successfully created ticket {code} for user {telegram_id} on {bot_identifier}")

    # 6. Instant Admin Notification Card Dispatch
    if bot:
        try:
            raw_name = user_obj.full_name if user_obj.full_name else "Foydalanuvchi"
            safe_name = html.escape(raw_name)
            user_mention = f'<a href="tg://user?id={telegram_id}">{safe_name}</a>'
            user_uname = f"@{user_obj.username}" if user_obj.username else "Mavjud emas"

            p_type_str = payout_type.value if hasattr(payout_type, 'value') else payout_type

            holder_info = f"\n{emoji_manager.get('user_admin')} <b>Karta Egasi:</b> <b>{html.escape(clean_holder)}</b>" if clean_holder else ""

            admin_card_text = (
                f"{emoji_manager.get('warning')} <b>YANGI ZAYAVKA KELDI (#{code})</b> [{bot_identifier.upper()}]\n\n"
                f"{emoji_manager.get('user_admin')} <b>Foydalanuvchi:</b> {user_mention} ({user_uname} | ID: <code>{telegram_id}</code>)\n"
                f"{emoji_manager.get('balance')} <b>To'lov Rekviziti:</b> <code>{clean_dest}</code> ({p_type_str}){holder_info}\n"
                f"{emoji_manager.get('paid_icon')} <b>Summa:</b> {reward_amount:,} UZS\n"
                f"{emoji_manager.get('tickets_icon')} <b>Holati:</b> <code>Kutilmoqda</code>"
            )
            from app.bot.keyboards.inline import get_admin_ticket_keyboard
            keyboard = get_admin_ticket_keyboard(new_ticket.id)

            group_ids_to_try = [
                settings.ADMIN_CHANNEL_ID,
                int(f"-100{abs(settings.ADMIN_CHANNEL_ID)}"),
                -5273763144,
                -1005273763144
            ]
            for target_group in group_ids_to_try:
                try:
                    await bot.send_message(
                        chat_id=target_group,
                        text=admin_card_text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                    logger.info(f"Ticket card #{code} sent to admin group {target_group}")
                    break
                except Exception as group_ex:
                    logger.warning(f"Could not send ticket card to group {target_group}: {group_ex}")

            for admin_id in settings.admin_id_list:
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=admin_card_text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                except Exception as adm_ex:
                    logger.debug(f"Direct admin notification to {admin_id} failed: {adm_ex}")

        except Exception as ex:
            logger.error(f"Failed to dispatch ticket card to admins: {ex}", exc_info=True)

    msg = "Zayavka qabul qilindi va adminlar ko'rib chiqishiga yuborildi."
    if is_high_risk:
        msg = "Zayavka qabul qilindi. Diqqat: Karta/raqam xavfsizlik filtri tomonidan shubhali deb topildi va qo'shimcha tekshiruvga yuborildi."

    return True, msg, new_ticket

async def process_ticket_action(
    session: AsyncSession,
    ticket_id: int,
    action: str, # 'pay', 'PAID', 'reject', 'REJECTED'
    admin_telegram_id: int,
    reason: str = "",
    bot: Optional[Bot] = None
) -> Tuple[bool, str]:
    """Admin updates ticket status (PAID / REJECTED) and notifies user & channel."""
    stmt = select(PayoutTicket).where(PayoutTicket.id == ticket_id)
    res = await session.execute(stmt)
    ticket = res.scalar_one_or_none()

    if not ticket:
        return False, "Zayavka topilmadi."

    budget = await get_or_create_budget(session)
    act_upper = action.upper()

    if act_upper in ["PAY", "PAID"]:
        if ticket.status == TicketStatus.PAID:
            return False, "Zayavka allaqachon to'langan!"
        
        budget.total_reserved_uzs = max(0, budget.total_reserved_uzs - ticket.amount_uzs)
        budget.total_paid_uzs += ticket.amount_uzs
        
        ticket.status = TicketStatus.PAID
        ticket.processed_by_admin_id = admin_telegram_id
        ticket.updated_at = datetime.utcnow()

        # 1. Mark or Create Verified Vote for Statistics
        if ticket.vote_id:
            v_stmt = select(Vote).where(Vote.id == ticket.vote_id)
            v_res = await session.execute(v_stmt)
            vote_obj = v_res.scalar_one_or_none()
            if vote_obj:
                vote_obj.status = VoteStatus.VERIFIED
                vote_obj.verified_at = datetime.utcnow()
        else:
            voted_phone = ticket.destination.split("->")[0].strip() if "->" in ticket.destination else ticket.destination
            
            v_stmt = select(Vote).where(Vote.voted_phone_number == voted_phone)
            v_res = await session.execute(v_stmt)
            existing_vote = v_res.scalar_one_or_none()

            if existing_vote:
                existing_vote.status = VoteStatus.VERIFIED
                existing_vote.verified_at = datetime.utcnow()
                ticket.vote_id = existing_vote.id
            else:
                new_vote = Vote(
                    telegram_id=ticket.telegram_id,
                    voted_phone_number=voted_phone,
                    openbudget_project_id=settings.OPENBUDGET_PROJECT_ID,
                    status=VoteStatus.VERIFIED,
                    verified_at=datetime.utcnow(),
                    bot_identifier=ticket.bot_identifier or "bot1"
                )
                session.add(new_vote)
                await session.flush()
                ticket.vote_id = new_vote.id

        # 2. Referral Bonus Payout & Referral Count Increment to inviter
        user_stmt = select(User).where(User.telegram_id == ticket.telegram_id)
        u_res = await session.execute(user_stmt)
        user_obj = u_res.scalar_one_or_none()

        if user_obj and user_obj.referrer_id:
            ref_stmt = select(User).where(User.telegram_id == user_obj.referrer_id)
            r_res = await session.execute(ref_stmt)
            referrer_obj = r_res.scalar_one_or_none()

            if referrer_obj:
                uv_stmt = select(func.count(Vote.id)).where(
                    Vote.telegram_id == user_obj.telegram_id,
                    Vote.status == VoteStatus.VERIFIED
                )
                user_verified_count = (await session.execute(uv_stmt)).scalar_one_or_none() or 0

                if user_verified_count == 1:
                    referrer_obj.referral_count += 1
                    if settings.REFERRAL_BONUS_PER_VOTE > 0:
                        referrer_obj.referral_earnings_uzs += settings.REFERRAL_BONUS_PER_VOTE
                        referrer_obj.balance_uzs += settings.REFERRAL_BONUS_PER_VOTE

                    if bot:
                        try:
                            ref_msg = (
                                f"{emoji_manager.get('welcome')} <b>REFERAL BONUSI KELDI!</b>\n\n"
                                f"Siz taklif qilgan do'stingizning ovozi tasdiqlandi va to'landi!\n"
                                f"{emoji_manager.get('balance')} Balansingizga: <b>+{settings.REFERRAL_BONUS_PER_VOTE:,} UZS</b> qo'shildi!\n"
                                f"{emoji_manager.get('lock_icon')} Jami balansingiz: <b>{referrer_obj.balance_uzs:,} UZS</b>"
                            )
                            await bot.send_message(chat_id=referrer_obj.telegram_id, text=ref_msg, parse_mode="HTML")
                        except Exception as ref_ex:
                            logger.error(f"Failed to notify referrer {referrer_obj.telegram_id}: {ref_ex}")

        if bot:
            try:
                user_msg = (
                    f"{emoji_manager.get('success')} <b>TO'LOV MUVAFFAQIYATLI BAJARILDI!</b>\n\n"
                    f"{emoji_manager.get('tickets_icon')} Zayavka kodi: <code>#{ticket.ticket_code}</code>\n"
                    f"{emoji_manager.get('paid_icon')} Summa: <b>{ticket.amount_uzs:,} UZS</b>\n"
                    f"{emoji_manager.get('balance')} Rekvizit: <code>{ticket.destination}</code>\n\n"
                    f"Pul kartangizga o'tkazildi! Rahmat!"
                )
                await bot.send_message(chat_id=ticket.telegram_id, text=user_msg, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Failed to notify user {ticket.telegram_id} of payment: {e}")

            try:
                dest_masked = mask_destination(ticket.destination)
                channel_text = (
                    f"{emoji_manager.get('success')} <b>YANGI TO'LOV MUVAFFAQIYATLI O'TKAZILDI!</b>\n\n"
                    f"{emoji_manager.get('tickets_icon')} <b>Zayavka kodi:</b> <code>#{ticket.ticket_code}</code>\n"
                    f"{emoji_manager.get('balance')} <b>Qabul qiluvchi:</b> <code>{dest_masked}</code>\n"
                    f"{emoji_manager.get('paid_icon')} <b>Summa:</b> {ticket.amount_uzs:,} UZS\n"
                    f"{emoji_manager.get('success')} <b>Holati:</b> Muvaffaqiyatli to'lab berildi!\n\n"
                    f"🤖 Botimiz orqali siz ham ovoz bering va pulingizni oling!"
                )
                from app.bot.keyboards.inline import get_payout_proof_channel_keyboard
                channel_ids_to_try = [
                    settings.PAYOUT_PROOF_CHANNEL_ID,
                    -1004487937644
                ]
                for ch_id in channel_ids_to_try:
                    try:
                        await bot.send_message(
                            chat_id=ch_id,
                            text=channel_text,
                            reply_markup=get_payout_proof_channel_keyboard(),
                            parse_mode="HTML"
                        )
                        logger.info(f"Payment proof posted to channel {ch_id}")
                        break
                    except Exception as ch_ex:
                        logger.warning(f"Could not post payment proof to channel {ch_id}: {ch_ex}")

            except Exception as e:
                logger.error(f"Failed to post text payment proof to channel: {e}")

    elif act_upper in ["REJECT", "REJECTED"]:
        if ticket.status == TicketStatus.REJECTED:
            return False, "Zayavka allaqachon rad etilgan!"

        budget.total_reserved_uzs = max(0, budget.total_reserved_uzs - ticket.amount_uzs)

        ticket.status = TicketStatus.REJECTED
        ticket.processed_by_admin_id = admin_telegram_id
        ticket.risk_reason = reason or "Admin tomonidan rad etildi."
        ticket.updated_at = datetime.utcnow()

        if bot:
            try:
                safe_reason = html.escape(reason or "Admin tomonidan rad etildi.")
                reject_msg = (
                    f"{emoji_manager.get('danger')} <b>ZAYAVKA RAD ETILDI</b>\n\n"
                    f"{emoji_manager.get('tickets_icon')} Zayavka kodi: <code>#{ticket.ticket_code}</code>\n"
                    f"{emoji_manager.get('danger')} <b>Rad etilish sababi:</b> {safe_reason}\n\n"
                    f"Agarda e'tirozingiz bo'lsa, admin bilan bog'lanishingiz mumkin."
                )
                await bot.send_message(chat_id=ticket.telegram_id, text=reject_msg, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Failed to notify user {ticket.telegram_id} of rejection: {e}")

    audit = AuditLog(
        event_type=f"TICKET_{act_upper}",
        telegram_id=ticket.telegram_id,
        details=f"Admin {admin_telegram_id} set ticket {ticket.ticket_code} to {act_upper}. Reason: {reason}"
    )
    session.add(audit)
    await session.commit()
    return True, f"Zayavka holati {act_upper} ga o'zgartirildi."
