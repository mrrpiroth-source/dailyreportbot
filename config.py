"""
Configuration module for the KHQR Daily Report Telegram Bot.
Loads environment variables from .env file.
"""

import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Telegram API credentials (from https://my.telegram.org)
API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")

# Bot Token (from @BotFather) - Used for Bot mode or dual mode
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Phone Number - Used if running as Telegram User Client (to read other bot messages in groups)
PHONE_NUMBER = os.getenv("TELEGRAM_PHONE_NUMBER", "")

# Chat / Group ID to monitor (where Bank notifications arrive)
# Can be an integer ID (e.g. -1001234567890) or username (e.g. @my_group)
MONITOR_CHAT_ID = os.getenv("MONITOR_CHAT_ID", "")
try:
    if MONITOR_CHAT_ID and (MONITOR_CHAT_ID.startswith("-") or MONITOR_CHAT_ID.isdigit()):
        MONITOR_CHAT_ID = int(MONITOR_CHAT_ID)
except ValueError:
    pass

# Chat / Channel / Admin ID where daily reports should be sent
REPORT_CHAT_ID = os.getenv("REPORT_CHAT_ID", "")
try:
    if REPORT_CHAT_ID and (REPORT_CHAT_ID.startswith("-") or REPORT_CHAT_ID.isdigit()):
        REPORT_CHAT_ID = int(REPORT_CHAT_ID)
except ValueError:
    pass

# Daily Report Time (24h format, e.g. "22:00" for 10:00 PM Phnom Penh Time)
DAILY_REPORT_TIME = os.getenv("DAILY_REPORT_TIME", "22:00")

# Whether to send an instant confirmation alert when a payment is captured
ENABLE_INSTANT_ALERT = os.getenv("ENABLE_INSTANT_ALERT", "false").lower() in ("true", "1", "yes")

# Auto-sync previous messages when bot starts up (to capture past payments)
SYNC_ON_STARTUP = os.getenv("SYNC_ON_STARTUP", "true").lower() in ("true", "1", "yes")
SYNC_LIMIT = int(os.getenv("SYNC_LIMIT", "200"))

# Master Bot Owner (Avata) Telegram ID (Permanent Super Admin)
MASTER_BOT_OWNER_ID = 7299682335
ADMIN_USER_ID = MASTER_BOT_OWNER_ID

# Security: Admin User IDs (Owner / Managers who have full permission)
# E.g. "7299682335,87654321"
ADMIN_USER_IDS = [
    int(x.strip()) 
    for x in os.getenv("ADMIN_USER_IDS", str(MASTER_BOT_OWNER_ID)).split(",") 
    if x.strip().lstrip("-").isdigit()
]
# Ensure master Bot Owner (Avata 7299682335) is ALWAYS an admin regardless of environment variable settings
if MASTER_BOT_OWNER_ID not in ADMIN_USER_IDS:
    ADMIN_USER_IDS.append(MASTER_BOT_OWNER_ID)

# When True, only Admin and authorized staff can view reports & run commands
RESTRICT_REPORTS_TO_ADMIN = os.getenv("RESTRICT_REPORTS_TO_ADMIN", "true").lower() in ("true", "1", "yes")

# Database Path
DB_PATH = os.getenv("DB_PATH", "khqr_reports.db")

# Bot Application Version
BOT_VERSION = "2.5.3"

# Optional Render Deploy Hook for automatic deployment on push
RENDER_DEPLOY_HOOK = os.getenv("RENDER_DEPLOY_HOOK", "")

