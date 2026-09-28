@echo off
title KHQR Daily Report Telegram Bot
cd /d "%~dp0"
echo ========================================================
echo   KHQR Daily Report Telegram Bot is Starting...
echo ========================================================
.venv\Scripts\python main.py
pause
