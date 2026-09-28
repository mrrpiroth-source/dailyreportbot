@echo off
chcp 65001 >nul
title GitHub Push Tool - Daily Report Bot
color 0A
echo ======================================================================
echo    KHQR DAILY REPORT BOT - GITHUB PUSH & INSTANT AUTO DEPLOY
echo ======================================================================
echo.
echo  Target: https://github.com/mrrpiroth-source/dailyreportbot
echo.
echo  [1/3] Staging all files...
git add -A

echo  [2/3] Checking for changes to commit...
git diff-index --quiet HEAD --
if %errorlevel% neq 0 (
    echo  Creating auto-commit...
    git commit -m "Auto-Update: Release v2.5.0 - Security hardening, instant health checks & 1-click controls"
) else (
    echo  No uncommitted changes, proceeding to push...
)

echo  [3/3] Pushing to GitHub (origin/main)...
git push -u origin main

echo.
echo ======================================================================
if %errorlevel% equ 0 (
    echo  [SUCCESS] Code pushed to GitHub successfully!
    echo.
    echo  Checking for Render Deploy Hook...
    powershell -Command "if (Test-Path .env) { $line = Get-Content .env | Select-String 'RENDER_DEPLOY_HOOK='; if ($line) { $hook = $line.ToString().Replace('RENDER_DEPLOY_HOOK=','').Trim(); if ($hook -and $hook.StartsWith('http')) { Write-Host '  >> Triggering Render Deploy Hook for instant deployment...' -ForegroundColor Cyan; try { Invoke-RestMethod -Uri $hook -Method Post; Write-Host '  >> [OK] Render is now automatically building & deploying the latest version!' -ForegroundColor Green } catch { Write-Host '  >> Could not trigger hook: ' $_ -ForegroundColor Yellow } } else { Write-Host '  >> Tip: Add RENDER_DEPLOY_HOOK to .env for instant 1-click cloud auto-deploy!' -ForegroundColor Yellow } } }"
    echo.
    echo  ------------------------------------------------------------------
    echo  [IMPORTANT] To make Render ALWAYS update automatically on push:
    echo   1. Go to https://dashboard.render.com
    echo   2. Open your Service -> Settings
    echo   3. Set "Auto-Deploy" to "Yes"
    echo   4. If not Auto-Deploy: Click "Manual Deploy" -> "Deploy latest commit"
    echo  ------------------------------------------------------------------
) else (
    echo  [NOTICE] If asked to Sign In, please click "Sign in with your browser"
    echo  and log in with account: mrrpiroth-source
)
echo ======================================================================
echo.
pause

