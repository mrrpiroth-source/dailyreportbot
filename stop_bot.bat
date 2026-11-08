@echo off
chcp 65001 >nul
title Stop KHQR Daily Report Telegram Bot
echo ========================================================
echo   Stopping all KHQR Telegram Bot processes...
echo ========================================================
taskkill /F /IM python.exe /T >nul 2>&1
echo.
echo [OK] All Bot processes stopped successfully.
echo ========================================================
pause

