"""
Interactive Live Demo for KHQR Telegram Daily Report Bot.
Demonstrates the full lifecycle:
1. Intercepting KHQR messages (ABA Merchant & Bakong)
2. Parsing Amount ($ & ៛), Payer, and Ref Code
3. Anti-duplicate prevention
4. Real-time transaction alerts
5. End-of-day scheduled Daily Summary (22:00)
6. Monthly Sales Report
"""

import sys
import io
import time
import os

# Ensure UTF-8 output on Windows terminals
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from database import Database, get_cambodia_now, get_cambodia_today_str
from parser import KHQRParser
from reporter import (
    format_transaction_alert,
    format_daily_summary,
    format_monthly_summary,
    format_range_summary
)

def run_demo():
    print("=" * 65)
    print("🌟 ដំណើរការ DEMO: KHQR TELEGRAM DAILY REPORT BOT 🌟")
    print("=" * 65)
    print("ប្រព័ន្ធកំពុងដំណើរការ និងត្រៀមស្តាប់សារពី Telegram Group...\n")

    # Use a fresh demo database
    demo_db_path = "demo_khqr.db"
    if os.path.exists(demo_db_path):
        os.remove(demo_db_path)
    db = Database(demo_db_path)

    # 1. Simulate incoming payments
    incoming_stream = [
        {
            "sender": "ABA Merchant Bot",
            "text": """Payment Received!
Amount: $ 18.50
From: CHAN VANDETH
Date: 28-Sep-2026 14:20:10
Approval Code: 112233
Ref / Trans ID: ABA-998811
Terminal: POS-01""",
            "desc": "ភ្ញៀវទី ១ ស្កេន KHQR បង់ប្រាក់ដុល្លារ ($18.50)"
        },
        {
            "sender": "ABA Merchant Bot",
            "text": """Payment Received!
Amount: KHR 80,000
From: HENG SOKHA
Date: 28-Sep-2026 14:35:22
Approval Code: 445566
Ref / Trans ID: ABA-998812
Terminal: POS-01""",
            "desc": "ភ្ញៀវទី ២ ស្កេន KHQR បង់ប្រាក់រៀល (80,000 ៛)"
        },
        {
            "sender": "Customer Chat",
            "text": "សួស្តីបង តើហាងបើកដល់ម៉ោងប៉ុន្មានដែរ?",
            "desc": "សារសន្ទនាធម្មតា (មិនមែនជាការបង់ប្រាក់)"
        },
        {
            "sender": "ABA Merchant Bot (Duplicate)",
            "text": """Payment Received!
Amount: $ 18.50
From: CHAN VANDETH
Date: 28-Sep-2026 14:20:10
Approval Code: 112233
Ref / Trans ID: ABA-998811""",
            "desc": "សារដដែលផ្ញើចូលម្តងទៀត (បន្លំ ឬ Resend)"
        },
        {
            "sender": "Bakong KHQR Bot",
            "text": """KHQR Payment Successful
Amount: $ 35.00
From: SOK SAMNANG
Txn ID: BK-774411
Date: 2026-09-28 15:10:05""",
            "desc": "ភ្ញៀវទី ៣ ស្កេន Bakong KHQR ($35.00)"
        },
        {
            "sender": "ABA Merchant Bot",
            "text": """ទទួលបានការទូទាត់ប្រាក់!
ចំនួនទឹកប្រាក់: 120,000 ៛
ពី: កែវ ស្រីមុំ
លេខកូដអនុម័ត: 778899
លេខយោង: ABA-998815""",
            "desc": "ភ្ញៀវទី ៤ ស្កេន KHQR ជាភាសាខ្មែរ (120,000 ៛)"
        }
    ]

    for idx, item in enumerate(incoming_stream, 1):
        print(f"\n📨 [សារទី {idx}] ផ្ញើដោយ: {item['sender']}")
        print(f"👉 សកម្មភាព: {item['desc']}")
        print("┌" + "─" * 50)
        for line in item["text"].strip().split("\n"):
            print(f"│ {line}")
        print("└" + "─" * 50)

        # Parse message
        parsed = KHQRParser.parse_message(item["text"])
        if not parsed:
            print("⚪ [BOT ACTION]: មិនមែនជាសារទូទាត់ប្រាក់ -> រំលងចោល (Ignored).")
            continue

        # Save to Database
        now_str = get_cambodia_now().strftime("%Y-%m-%d %H:%M:%S")
        success, msg, txn_id = db.save_transaction(
            amount=parsed["amount"],
            currency=parsed["currency"],
            payer_name=parsed["payer_name"],
            ref_code=parsed["ref_code"],
            bank_name=parsed["bank_name"],
            raw_text=item["text"],
            transaction_time=now_str
        )

        if success:
            print(f"🟢 [BOT ACTION]: ចាប់បានការទូទាត់ជោគជ័យ!")
            print(f"   • រូបិយប័ណ្ណ: {parsed['currency']}")
            print(f"   • ទឹកប្រាក់: {parsed['amount']:,}")
            print(f"   • អតិថិជន: {parsed['payer_name']}")
            print(f"   • លេខកូដយោង (Ref): {parsed['ref_code']}")
            print(f"   • ធនាគារ: {parsed['bank_name']}")
            print(f"   💾 បានកត់ត្រាចូល SQLite Database: Transaction #{txn_id}")
        else:
            print(f"🔴 [BOT ACTION - ANTI-DUPLICATE]: {msg}")
            print("   🛡️ ប្រព័ន្ធបានការពារកុំឱ្យបូកប្រាក់ជាន់គ្នាទ្វេដង!")

    # 2. Simulate User typing commands
    print("\n" + "=" * 65)
    print("📱 SIMULATION: អ្នកប្រើប្រាស់វាយ Command សុំមើលរបាយការណ៍")
    print("=" * 65)

    print("\n👤 [User]: វាយពាក្យបញ្ជា /today")
    today_summary = db.get_summary_by_date()
    print("🤖 [KHQR Bot ឆ្លើយតប]:\n")
    print(format_daily_summary(today_summary, title_prefix="ថ្ងៃនេះ (Today)"))

    print("\n" + "=" * 65)
    print("⏰ SIMULATION: ដល់ម៉ោង 22:00 យប់ (Scheduled Auto Report)")
    print("=" * 65)
    print("🤖 [ប្រព័ន្ធផ្ញើរបាយការណ៍ស្វ័យប្រវត្តចូល Telegram Group]:\n")
    print(format_daily_summary(today_summary, title_prefix="ប្រចាំថ្ងៃ (Daily Summary)"))

    print("\n" + "=" * 65)
    print("📈 SIMULATION: អ្នកប្រើប្រាស់វាយពាក្យបញ្ជា /month (របាយការណ៍ប្រចាំខែ)")
    print("=" * 65)
    print("👤 [User]: វាយពាក្យបញ្ជា /month")
    monthly_summary = db.get_summary_by_month()
    print("🤖 [KHQR Bot ឆ្លើយតប]:\n")
    print(format_monthly_summary(monthly_summary))

    print("\n" + "=" * 65)
    print("🎉 ចប់ការ DEMO ដោយជោគជ័យ! ប្រព័ន្ធត្រៀមរួចរាល់ ១០០% សម្រាប់ការប្រើប្រាស់ជាក់ស្តែង។")
    print("=" * 65 + "\n")

    # Clean up demo database
    if os.path.exists(demo_db_path):
        os.remove(demo_db_path)

if __name__ == "__main__":
    run_demo()
