@echo off
chcp 65001 >nul
title KHQR Daily Report Telegram Bot
cd /d "%~dp0"
echo ========================================================
echo   KHQR Daily Report Telegram Bot is Starting...
echo ========================================================
echo.
.venv\Scripts\python.exe main.py
pause
