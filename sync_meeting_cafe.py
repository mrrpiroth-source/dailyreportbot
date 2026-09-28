import sys
import asyncio
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from telethon import TelegramClient
import config
from database import Database, CAMBODIA_TZ
from parser import KHQRParser
from reporter import format_currency

async def sync():
    db = Database(config.DB_PATH)
    client = TelegramClient('user_session', config.API_ID, config.API_HASH)
    await client.connect()
    
    chat_id = -1004325343684
    print(f"Scanning messages from 'Meeting cafe ☕️' (ID: {chat_id})...")
    
    total_scanned = 0
    payments_found = 0
    new_saved = 0
    duplicates = 0
    
    all_dates = set()

    async for msg in client.iter_messages(chat_id, limit=500):
        if not msg.text:
            continue
        
        total_scanned += 1
        parsed = KHQRParser.parse_message(msg.text)
        if not parsed:
            continue
            
        payments_found += 1
        txn_time = msg.date.astimezone(CAMBODIA_TZ).strftime("%Y-%m-%d %H:%M:%S")
        date_str = txn_time.split()[0]
        all_dates.add(date_str)
        
        success, message, txn_id = db.save_transaction(
            amount=parsed["amount"],
            currency=parsed["currency"],
            payer_name=parsed["payer_name"],
            ref_code=parsed["ref_code"],
            bank_name=parsed["bank_name"],
            raw_text=msg.text,
            transaction_time=txn_time
        )
        
        amt_str = format_currency(parsed["amount"], parsed["currency"])
        payer = parsed.get("payer_name") or "ភ្ញៀវ"
        ref = parsed.get("ref_code") or "N/A"
        
        if success:
            new_saved += 1
            print(f"  [+] #{txn_id}: {amt_str} | {payer} | Ref: {ref} ({txn_time})")
        else:
            duplicates += 1
            print(f"  [=] DUPLICATE: {amt_str} | {payer} | Ref: {ref} ({txn_time})")

    print("\n" + "="*60)
    print(f"Total scanned: {total_scanned} messages")
    print(f"Payments found: {payments_found}")
    print(f"New saved: {new_saved}")
    print(f"Duplicates: {duplicates}")
    print("="*60)
    
    print("\nSummaries by Date:")
    for d in sorted(all_dates):
        s = db.get_summary_by_date(d)
        print(f"Date: {d} -> Total USD: ${s['total_usd']:,.2f} ({s['count_usd']} txns) | Total KHR: {int(s['total_khr']):,} ៛ ({s['count_khr']} txns) | Total: {s['total_count']} txns")
        
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(sync())
