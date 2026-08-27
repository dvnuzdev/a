# 🗳 OpenBudget Telegram Bot (Rasmiy API v2 Integratsiyasi bilan)

Ushbu papkada botning barcha eng so\'nggi, toza va to\'liq ishchi fayllari jamlangan.

---

## 📂 Papka Tarkibi

- pp/ - Asosiy bot dastur kodi (Aiogram 3, SQLAlchemy, OpenBudget API v2 servisi, Anti-fraud, Load Balancer).
- pp/services/openbudget_api.py - MEmu rasmiy ilovasidan olingan eng so\'nggi API v2 integratsiyasi (captcha-2, /dfghgtrgffg/check, /iutyjmjyfgnmg/verify, /resend-sms).
- .env - Bot tokeni, Admin ID, OpenBudget loyiha ID va boshqa sozlamalar.
- 
equirements.txt - Python kutubxonalari ro\'yxati.
- Dockerfile & docker-compose.yml - Serverda (VPS) bitta buyruq bilan PostgreSQL, Redis va Nginx bilan ko\'tarish uchun.
- start.bat - Windows kompyuterda botni ishga tushirish uchun 1-bosqichli fayl.

---

## ⚙️ Sozlash (.env fayli)

.env faylini ochib, quyidagi asosiy parametrlarni o\'zingizga moslang:

1. BOT_TOKEN - @BotFather dan olingan bot tokeni.
2. ADMIN_TELEGRAM_IDS - Admin(lar)ning Telegram ID raqamlari (vergul bilan).
3. OPENBUDGET_PROJECT_ID - Siz ovoz yig\'ayotgan OpenBudget loyihangiz ID raqami.
4. DEFAULT_REWARD_PER_VOTE - 1 ta ovoz uchun foydalanuvchiga to\'lanadigan summa (masalan: 25000).
5. PAYOUT_PROOF_CHANNEL_ID / PAYOUT_PROOF_CHANNEL_URL - To\'lovlar cheki yuboriladigan kanal.

---

## 🚀 Ishga tushirish

### 1-usul: Windows kompyuterda
start.bat faylini 2 marta bosing va 1 ni tanlang.

Yoki CMD / PowerShell orqali:
`ash
pip install -r requirements.txt
python -m app.bot_runner
`

### 2-usul: Serverda (Docker orqali)
`ash
docker-compose up --build -d
`
