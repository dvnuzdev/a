from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from app.services.emoji_manager import emoji_manager

def get_main_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Returns main menu reply keyboard with custom emoji icons or clean plain fallbacks."""
    def make_btn(text: str, key: str, style: str = None) -> KeyboardButton:
        kwargs = {}
        if style:
            kwargs["style"] = style
        emoji_id = emoji_manager.get_emoji_id(key)
        if emoji_id:
            kwargs["icon_custom_emoji_id"] = emoji_id
            kwargs["text"] = text
        else:
            plain_emoji = emoji_manager.get_plain(key)
            kwargs["text"] = f"{plain_emoji} {text}"
        return KeyboardButton(**kwargs)

    buttons = [
        [
            make_btn("Ovoz berish", "vote", style="success"),
            make_btn("Boshqa raqamdan ovoz", "other_phone", style="primary")
        ],
        [
            make_btn("Statistika", "votes_icon", style="success"),
            make_btn("To'lov holati", "balance", style="primary")
        ],
        [
            make_btn("To'lovlar kanali", "channel", style="success"),
            make_btn("Mening havolam", "link", style="primary")
        ],
        [
            make_btn("Top Referrallar", "top_ref", style="success"),
            make_btn("Yordam / Qoidalar", "help", style="primary")
        ]
    ]

    if is_admin:
        buttons.append([make_btn("Admin Panel", "admin", style="primary")])

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        persistent=True
    )

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Returns red cancel reply keyboard for FSM states."""
    kwargs = {"style": "danger"}
    emoji_id = emoji_manager.get_emoji_id("cancel")
    if emoji_id:
        kwargs["icon_custom_emoji_id"] = emoji_id
        kwargs["text"] = "Bekor qilish"
    else:
        plain_cancel = emoji_manager.get_plain("cancel")
        kwargs["text"] = f"{plain_cancel} Bekor qilish"

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(**kwargs)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_phone_request_keyboard() -> ReplyKeyboardMarkup:
    """Returns contact share reply keyboard with styled red cancel button."""
    kwargs_cancel = {"style": "danger"}
    emoji_id_cancel = emoji_manager.get_emoji_id("cancel")
    if emoji_id_cancel:
        kwargs_cancel["icon_custom_emoji_id"] = emoji_id_cancel
        kwargs_cancel["text"] = "Bekor qilish"
    else:
        plain_cancel = emoji_manager.get_plain("cancel")
        kwargs_cancel["text"] = f"{plain_cancel} Bekor qilish"

    kwargs_contact = {"request_contact": True, "style": "success"}
    emoji_id_phone = emoji_manager.get_emoji_id("other_phone")
    if emoji_id_phone:
        kwargs_contact["icon_custom_emoji_id"] = emoji_id_phone
        kwargs_contact["text"] = "Telefon raqamni yuborish"
    else:
        plain_phone = emoji_manager.get_plain("other_phone")
        kwargs_contact["text"] = f"{plain_phone} Telefon raqamni yuborish"

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(**kwargs_contact)
            ],
            [
                KeyboardButton(**kwargs_cancel)
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
