"""
Main entry point for running the KHQR Daily Report Telegram Bot.
"""

import sys
import asyncio

# Safely ensure UTF-8 output on Windows terminals
if sys.platform == "win32":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

from bot import start_bot

if __name__ == "__main__":
    try:
        asyncio.run(start_bot())
    except (KeyboardInterrupt, SystemExit):
        print("\n👋 KHQR Bot ត្រូវបានបញ្ឈប់ (Stopped).")
    except Exception as e:
        print(f"\n❌ Error: {e}")
