@echo off
chcp 65001 >nul
title GitHub Push Tool - Daily Report Bot
color 0A
echo ======================================================================
echo    KHQR DAILY REPORT BOT - GITHUB PUSH
echo ======================================================================
echo.
echo  Target: https://github.com/mrrpiroth-source/dailyreportbot
echo.
echo  Starting git push...
echo.

git push -u origin main

echo.
echo ======================================================================
if %errorlevel% equ 0 (
    echo  [SUCCESS] Code pushed to GitHub successfully!
    echo  You can now go to Render.com and click "Manual Deploy"!
) else (
    echo  [NOTICE] If asked to Sign In, please click "Sign in with your browser"
    echo  and log in with account: mrrpiroth-source
)
echo ======================================================================
echo.
pause
