"""
Historical Backfill and Sync Utility for KHQR Telegram Group.
Reads previous messages from the Telegram Group to recover all past KHQR payment transactions
that were sent before the bot was added or started.
"""

import sys
import io
import asyncio
import logging

if sys.platform == "win32":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

from telethon import TelegramClient
from typing import cast, Any, Awaitable
import config
from database import Database, CAMBODIA_TZ, get_cambodia_today_str
from parser import KHQRParser
from reporter import format_currency

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("SyncHistory")

db = Database(config.DB_PATH)

async def sync_previous_messages(client: TelegramClient, chat_id, limit: int = 200):
    """
    Fetches past messages from chat_id, parses any KHQR payment notifications,
    and saves them to SQLite database with their original historical timestamp.
    """
    print(f"\n🔄 កំពុងទាញយកសារចាស់ៗចំនួន {limit} សារចុងក្រោយពី Group...")
    print("=" * 65)

    total_scanned = 0
    found_payments = 0
    new_added = 0
    duplicates = 0

    usd_total = 0.0
    khr_total = 0.0

    try:
        async for msg in client.iter_messages(chat_id, limit=limit):
            if not msg.text:
                continue

            total_scanned += 1
            parsed = KHQRParser.parse_message(msg.text)
            if not parsed:
                continue

            found_payments += 1
            # Convert original Telegram message date to Cambodia Time
            txn_time = msg.date.astimezone(CAMBODIA_TZ).strftime("%Y-%m-%d %H:%M:%S")

            success, message, txn_id = db.save_transaction(
                amount=parsed["amount"],
                currency=parsed["currency"],
                payer_name=parsed["payer_name"],
                ref_code=parsed["ref_code"],
                bank_name=parsed["bank_name"],
                raw_text=msg.text,
                transaction_time=txn_time
            )

            if success:
                new_added += 1
                if parsed["currency"] == "USD":
                    usd_total += parsed["amount"]
                else:
                    khr_total += parsed["amount"]
                amt_str = format_currency(parsed["amount"], parsed["currency"])
                payer = parsed.get("payer_name") or "ភ្ញៀវ"
                ref = parsed.get("ref_code") or "N/A"
                print(f"  + [កត់ត្រាជោគជ័យ #{txn_id}]: {amt_str} | {payer} | Ref: {ref} ({txn_time})")
            else:
                duplicates += 1

        print("=" * 65)
        print("✅ ការទាញយកទិន្នន័យចាស់ៗត្រូវបានបញ្ចប់:")
        print(f"  • សារដែលបានពិនិត្យសរុប: {total_scanned} សារ")
        print(f"  • សារទូទាត់ KHQR ដែលរកឃើញ: {found_payments} លើក")
        print(f"  • ប្រតិបត្តិការថ្មីដែលបានកត់ត្រាចូល DB: {new_added} លើក")
        print(f"  • ប្រតិបត្តិការដែលបានកត់ត្រារួចហើយ (រំលង): {duplicates} លើក")
        print(f"  • សរុបទឹកប្រាក់ថ្មីដែលទើបទាញបាន: ${usd_total:,.2f} | {int(khr_total):,} ៛")
        print("=" * 65 + "\n")

        return {
            "total_scanned": total_scanned,
            "found_payments": found_payments,
            "new_added": new_added,
            "duplicates": duplicates,
            "usd_total": usd_total,
            "khr_total": khr_total
        }

    except Exception as e:
        print(f"❌ កំហុសក្នុងការទាញយកសារ: {e}")
        return None

async def main():
    if not config.API_ID or not config.API_HASH:
        print("❌ សូមបំពេញ TELEGRAM_API_ID និង TELEGRAM_API_HASH នៅក្នុង .env ជាមុនសិន!")
        return

    chat_id = config.MONITOR_CHAT_ID
    if not chat_id:
        print("❌ សូមបំពេញ MONITOR_CHAT_ID នៅក្នុង .env (អាចប្រើ get_groups.py ដើម្បីស្វែងរក Chat ID)")
        return

    session_name = "khqr_session"
    client = TelegramClient(session_name, config.API_ID, config.API_HASH)

    if config.BOT_TOKEN:
        await cast(Awaitable[Any], client.start(bot_token=config.BOT_TOKEN))
    elif config.PHONE_NUMBER:
        await cast(Awaitable[Any], client.start(phone=config.PHONE_NUMBER))
    else:
        await cast(Awaitable[Any], client.start())

    limit = config.SYNC_LIMIT or 200
    await sync_previous_messages(client, chat_id, limit=limit)

if __name__ == "__main__":
    asyncio.run(main())
