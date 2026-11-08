@echo off
chcp 65001 >nul
title Telegram Login - KHQR Bot
cd /d "%~dp0"
echo ========================================================
echo   KHQR Bot Telegram User Login Tool
echo ========================================================
echo.
.venv\Scripts\python.exe login.py
echo.
echo ========================================================
pause

