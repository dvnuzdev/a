import re
from typing import Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database.models import PayoutTicket, User

def luhn_checksum_is_valid(card_number: str) -> bool:
    """Validate 16-digit Uzcard / Humo / Visa / Mastercard numbers using Luhn Algorithm."""
    digits = [int(c) for c in card_number if c.isdigit()]
    if len(digits) != 16:
        return False
    
    checksum = 0
    reverse_digits = digits[::-1]
    for i, digit in enumerate(reverse_digits):
        if i % 2 == 1:
            doubled = digit * 2
            checksum += doubled if doubled < 10 else doubled - 9
        else:
            checksum += digit
    return checksum % 10 == 0

def clean_phone_number(phone: str) -> str:
    """Normalize phone number to standard +998XXXXXXXXX format."""
    cleaned = re.sub(r"[^\d+]", "", phone)
    if cleaned.startswith("998") and len(cleaned) == 12:
        cleaned = "+" + cleaned
    elif len(cleaned) == 9 and not cleaned.startswith("+"):
        cleaned = "+998" + cleaned
    return cleaned

def is_valid_uzbek_phone(phone: str) -> bool:
    """Check if phone number is a valid Uzbekistan mobile number (+998XXXXXXXXX)."""
    normalized = clean_phone_number(phone)
    pattern = r"^\+998[0-9]{9}$"
    return bool(re.match(pattern, normalized))

def is_valid_card_number(card: str) -> bool:
    """Check if card is a 16-digit Uzcard (8600), Humo (9860), or standard bank card."""
    clean_card = re.sub(r"\s+", "", card)
    if not clean_card.isdigit() or len(clean_card) != 16:
        return False
    # Uzcard prefix: 8600, Humo prefix: 9860
    return luhn_checksum_is_valid(clean_card)

async def evaluate_fraud_risk(
    session: AsyncSession,
    telegram_id: int,
    destination: str
) -> Tuple[bool, str]:
    """
    Evaluate anti-fraud risk score:
    - Check if destination (Card/Phone) has been used by ANOTHER Telegram account.
    - Check if user risk score is elevated.
    Returns: (is_high_risk: bool, risk_reason: str)
    """
    clean_dest = re.sub(r"\s+", "", destination)

    # 1. Check duplicate destination across different Telegram accounts
    stmt = select(func.count(PayoutTicket.id)).where(
        PayoutTicket.destination == clean_dest,
        PayoutTicket.telegram_id != telegram_id
    )
    result = await session.execute(stmt)
    duplicate_count = result.scalar_one_or_none() or 0

    if duplicate_count > 0:
        return True, f"Ushbu karta/raqam ({clean_dest}) ilgari boshqa Telegram akkaunt ({duplicate_count} ta) tomonidan ishlatilgan!"

    # 2. Check User Risk Score
    user_stmt = select(User).where(User.telegram_id == telegram_id)
    user_res = await session.execute(user_stmt)
    user = user_res.scalar_one_or_none()

    if user and user.risk_score >= 50:
        return True, f"Foydalanuvchining shubhali faollik reytingi yuqori (Risk score: {user.risk_score})"

    return False, ""
