from aiogram.fsm.state import State, StatesGroup

class VoteStates(StatesGroup):
    waiting_for_phone = State()
    waiting_for_captcha = State()
    waiting_for_otp = State()

class PayoutStates(StatesGroup):
    selecting_type = State()
    waiting_for_card = State()
    waiting_for_card_holder_name = State()
    waiting_for_payout_phone = State()
