@echo off
title Find Telegram Group IDs
cd /d "%~dp0"
echo ========================================================
echo   Scanning your Telegram Groups to find Chat IDs...
echo ========================================================
.venv\Scripts\python get_groups.py
pause
