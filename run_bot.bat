@echo off
title ClipVideo Telegram Bot 24/7 Auto-Restart
echo =============================================
echo    ClipVideo Telegram Bot Auto-Restart 24/7
echo =============================================

set PYTHON_EXE=.venv\Scripts\python.exe
set BOT_SCRIPT=tools\telegram_bot.py

if not exist %PYTHON_EXE% (
    echo Error: Virtual environment ^(.venv^) tidak ditemukan!
    echo Harap buat .venv dan install dependensi terlebih dahulu.
    pause
    exit /b 1
)

:loop
echo [%date% %time%] Menjalankan Bot Telegram...
%PYTHON_EXE% %BOT_SCRIPT%
echo [%date% %time%] Bot terhenti atau crash! Melakukan restart dalam 5 detik...
timeout /t 5
goto loop
