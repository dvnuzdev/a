from datetime import datetime, timezone, timedelta
from typing import Tuple
from app.services.emoji_manager import emoji_manager

# Uzbekistan Timezone GMT+5
UZB_TZ = timezone(timedelta(hours=5))
TARGET_DEADLINE = datetime(2026, 8, 22, 0, 0, 0, tzinfo=UZB_TZ)

def get_countdown_info() -> Tuple[str, str, bool]:
    """
    Calculates remaining time until August 22, 00:00 GMT+5.
    Returns: (countdown_str: str, formatted_html_msg: str, is_started: bool)
    """
    now = datetime.now(UZB_TZ)
    diff = TARGET_DEADLINE - now

    e_timer = emoji_manager.get("timer")
    e_cal = emoji_manager.get("calendar")
    e_wel = emoji_manager.get("welcome")
    e_vote = emoji_manager.get("vote")
    e_link = emoji_manager.get("link")
    e_finger = emoji_manager.get("finger_down")

    if diff.total_seconds() <= 0:
        return "0 kun, 00 soat, 00 daqiqa", f"🚀 <b>OPENBUDGET MAVSUMI RASMAN BOSHLANDI!</b>\n\nBotga o'tib ovoz bering va pul mukofotini oling!", True

    days = diff.days
    hours, remainder = divmod(diff.seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    countdown_str = f"{days} kun, {hours:02d} soat, {minutes:02d} daqiqa"

    formatted_html = (
        f"{e_wel} <b>OPENBUDGET RASMIY BOTI</b>\n\n"
        f"<blockquote>{e_timer} <b>Ovoz berish boshlanishiga:</b> <code>{countdown_str}</code> qoldi!\n\n"
        f"{e_vote} OpenBudget rasmiy botida o'z raqamingiz hamda yaqinlaringiz raqamidan ovoz bering va pul mukofotini oling!\n\n"
        f"{e_link} <b>Referal Tizimi:</b> Shaxsiy taklif havolangiz orqali do'stlaringizni taklif qiling va ular bergan har bir ovoz uchun doimiy qo'shimcha daromad ishlang!</blockquote>\n\n"
        f"{e_finger} <b>Botga o'tib hoziroq boshlash uchun pastdagi tugmani bosing:</b>"
    )

    return countdown_str, formatted_html, False

def get_countdown_text() -> Tuple[str, bool]:
    """HTML format helper for group broadcasts."""
    c_str, html_msg, is_started = get_countdown_info()
    return html_msg, is_started
