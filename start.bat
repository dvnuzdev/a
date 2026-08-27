@echo off
chcp 65001 > nul
echo ===================================================
echo     OPENBUDGET TELEGRAM BOT - ISHGA TUSHIRISH
echo ===================================================
echo.
echo 1) Python orqali ishga tushirish (Polling)
echo 2) Docker Compose orqali ishga tushirish (Prod)
echo 3) Chiqish
echo.
set /p opt=Tanlang (1, 2, 3): 
if %opt%==1 (
    pip install -r requirements.txt
    python -m app.bot_runner
) else if %opt%==2 (
    docker-compose up --build -d
    docker-compose logs -f bot
)
pause
