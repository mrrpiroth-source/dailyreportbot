"""
Main entry point for running the KHQR Daily Report Telegram Bot.
"""

import sys
import time
import asyncio

# Safely ensure UTF-8 output on Windows terminals
if sys.platform == "win32":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

from bot import start_bot

if __name__ == "__main__":
    retry_delay = 3
    while True:
        try:
            asyncio.run(start_bot())
            # If start_bot finishes normally without error, exit gracefully
            break
        except (KeyboardInterrupt, SystemExit):
            print("\n👋 KHQR Bot ត្រូវបានបញ្ឈប់ (Stopped).")
            break
        except Exception as e:
            print(f"\n⚠️ KHQR Bot ជួបបញ្ហារអាក់រអួល ឬដាច់ Connection: {e}")
            print(f"🔄 កំពុងតភ្ជាប់ និង Restart ឡើងវិញដោយស្វ័យប្រវត្តក្នុងរយៈពេល {retry_delay} វិនាទី (Auto-Recovery)...")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay + 2, 30)

