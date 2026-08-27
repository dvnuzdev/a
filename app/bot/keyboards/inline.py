from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.config import settings
from app.services.emoji_manager import emoji_manager, EMOJI_LABELS

PAYOUT_CHANNEL_DIRECT_URL = "https://t.me/+FFC_JlR5pR8xOWNi"

def make_inline_btn(text: str, key: str = None, style: str = None, **kwargs) -> InlineKeyboardButton:
    """Helper to create InlineKeyboardButton with native Telegram API 8.3 style and icon_custom_emoji_id."""
    params = {"text": text, **kwargs}
    if style:
        params["style"] = style
    if key:
        emoji_id = emoji_manager.get_emoji_id(key)
        if emoji_id:
            params["icon_custom_emoji_id"] = emoji_id
    return InlineKeyboardButton(**params)

def get_help_contacts_keyboard() -> InlineKeyboardMarkup:
    """Returns inline keyboard with direct links to Admin, Owner, and Official Payment Channel."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                make_inline_btn(
                    text="Admin",
                    key="user_admin",
                    style="primary",
                    url="https://t.me/cmbk_222"
                ),
                make_inline_btn(
                    text="Ega",
                    key="user_owner",
                    style="success",
                    url="https://t.me/the_797"
                )
            ],
            [
                make_inline_btn(
                    text="Rasmiy To'lovlar Kanalimiz",
                    key="channel",
                    style="primary",
                    url=PAYOUT_CHANNEL_DIRECT_URL
                )
            ]
        ]
    )

def get_openbudget_voting_keyboard(project_id: str = None) -> InlineKeyboardMarkup:
    """Returns inline keyboard linking directly to the OpenBudget initiative page."""
    target_id = project_id or settings.OPENBUDGET_PROJECT_ID
    url = f"https://openbudget.uz/boards/initiatives/initiative/{target_id}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                make_inline_btn(
                    text="🌐 OpenBudget'da Ovoz Berish",
                    key="vote",
                    style="primary",
                    url=url
                )
            ]
        ]
    )

def get_payout_choice_keyboard(vote_id: int = None) -> InlineKeyboardMarkup:
    """Returns payout destination selection inline keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                make_inline_btn(
                    text="Plastik Karta (Uzcard / Humo)",
                    key="balance",
                    style="primary",
                    callback_data=f"payout_type:card:{vote_id or 0}"
                )
            ],
            [
                make_inline_btn(
                    text="Telefon Raqam (Paynet / Click)",
                    key="other_phone",
                    style="success",
                    callback_data=f"payout_type:phone:{vote_id or 0}"
                )
            ]
        ]
    )

def get_payout_proof_channel_keyboard() -> InlineKeyboardMarkup:
    """Returns inline keyboard linking directly to the Payment Proof Channel."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                make_inline_btn(
                    text="Rasmiy To'lovlar Kanalimiz",
                    key="channel",
                    style="success",
                    url=PAYOUT_CHANNEL_DIRECT_URL
                )
            ]
        ]
    )

def get_user_ticket_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    """Returns user ticket view inline keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                make_inline_btn(
                    text="To'lovlar Kanaliga O'tish",
                    key="channel",
                    style="success",
                    url=PAYOUT_CHANNEL_DIRECT_URL
                )
            ],
            [
                make_inline_btn(
                    text="To'lov chekini so'rash",
                    key="tickets_icon",
                    style="primary",
                    callback_data=f"request_receipt:{ticket_id}"
                )
            ]
        ]
    )

def get_admin_ticket_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    """Returns administrative action inline keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                make_inline_btn(
                    text="To'landi",
                    key="success",
                    style="success",
                    callback_data=f"admin_pay:{ticket_id}"
                ),
                make_inline_btn(
                    text="Rad etish",
                    key="danger",
                    style="danger",
                    callback_data=f"admin_reject:{ticket_id}"
                )
            ],
            [
                make_inline_btn(
                    text="Chek Rasmi Yuborish",
                    key="tickets_icon",
                    style="primary",
                    callback_data=f"admin_upload_receipt:{ticket_id}"
                ),
                make_inline_btn(
                    text="Qayta tekshirish",
                    key="system_icon",
                    style="success",
                    callback_data=f"admin_recheck:{ticket_id}"
                )
            ]
        ]
    )

def get_admin_reject_reasons_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    """Returns preset rejection reason selection keyboard for admins."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                make_inline_btn(
                    text="Karta / Raqam Noto'g'ri",
                    key="danger",
                    style="danger",
                    callback_data=f"reject_preset:{ticket_id}:card_invalid"
                )
            ],
            [
                make_inline_btn(
                    text="Ovoz Tasdiqlanmagan",
                    key="warning",
                    style="danger",
                    callback_data=f"reject_preset:{ticket_id}:unverified"
                )
            ],
            [
                make_inline_btn(
                    text="Takroriy Zayavka",
                    key="danger",
                    style="danger",
                    callback_data=f"reject_preset:{ticket_id}:duplicate"
                )
            ],
            [
                make_inline_btn(
                    text="Sababini matn qilib yozish",
                    style="primary",
                    callback_data=f"reject_preset:{ticket_id}:custom"
                )
            ]
        ]
    )

def get_admin_dashboard_keyboard() -> InlineKeyboardMarkup:
    """Returns full interactive Admin Panel inline menu with native styles and custom emoji icons."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                make_inline_btn(
                    text="Kutilayotgan Zayavkalar",
                    key="warning",
                    style="primary",
                    callback_data="admin_menu:pending"
                ),
                make_inline_btn(
                    text="Ovozlar Statistikasi",
                    key="votes_icon",
                    style="primary",
                    callback_data="admin_menu:users_stats"
                )
            ],
            [
                make_inline_btn(
                    text="Userlarga Xabar",
                    key="speaker",
                    style="success",
                    callback_data="admin_menu:user_broadcast"
                ),
                make_inline_btn(
                    text="Guruhlarga Reklama",
                    key="speaker",
                    style="success",
                    callback_data="admin_menu:broadcast"
                )
            ],
            [
                make_inline_btn(
                    text="Ovoz Narxi (UZS)",
                    key="paid_icon",
                    style="success",
                    callback_data="admin_menu:change_vote_price"
                ),
                make_inline_btn(
                    text="Referal Bonusi",
                    key="balance",
                    style="success",
                    callback_data="admin_menu:change_ref_bonus"
                )
            ],
            [
                make_inline_btn(
                    text="Ovoz Qo'shish/Ayirish",
                    key="votes_icon",
                    style="primary",
                    callback_data="admin_menu:adjust_votes"
                ),
                make_inline_btn(
                    text="OpenBudget ID",
                    key="pin_icon",
                    style="primary",
                    callback_data="admin_menu:change_project_id"
                )
            ],
            [
                make_inline_btn(
                    text="Premium Emojilar",
                    key="welcome",
                    style="primary",
                    callback_data="admin_menu:emojis"
                ),
                make_inline_btn(
                    text="Top Referrallar",
                    key="top_ref",
                    style="primary",
                    callback_data="admin_menu:top_ref"
                )
            ],
            [
                make_inline_btn(
                    text="Faol Guruhlar",
                    key="groups_icon",
                    style="primary",
                    callback_data="admin_menu:groups"
                ),
                make_inline_btn(
                    text="Yangilash",
                    key="system_icon",
                    style="primary",
                    callback_data="admin_menu:refresh"
                )
            ]
        ]
    )

def get_admin_emojis_keyboard() -> InlineKeyboardMarkup:
    """Returns selection list of buttons for customizing Premium Custom Emojis."""
    buttons = []
    keys = list(EMOJI_LABELS.keys())
    for i in range(0, len(keys), 2):
        row = []
        k1 = keys[i]
        row.append(make_inline_btn(text=EMOJI_LABELS[k1], key=k1, style="primary", callback_data=f"edit_emoji:{k1}"))
        if i + 1 < len(keys):
            k2 = keys[i+1]
            row.append(make_inline_btn(text=EMOJI_LABELS[k2], key=k2, style="success", callback_data=f"edit_emoji:{k2}"))
        buttons.append(row)

    buttons.append([make_inline_btn(text="⬅️ Admin Panelga Qaytish", style="danger", callback_data="admin_menu:refresh")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
