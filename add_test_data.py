"""
Utility script to simulate receiving KHQR payments.
Adds realistic test transactions to the database so you can preview reports immediately.
"""

import sys
import io
import datetime
from zoneinfo import ZoneInfo

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from database import Database, get_cambodia_now, get_cambodia_today_str
from reporter import format_daily_summary

def seed_sample_data():
    db = Database("khqr_reports.db")
    now = get_cambodia_now()
    today_str = get_cambodia_today_str()

    sample_txns = [
        {
            "amount": 12.50,
            "currency": "USD",
            "payer_name": "CHAN VANDETH",
            "ref_code": "ABA-TEST-001",
            "bank_name": "ABA Bank",
            "time": now.strftime("%Y-%m-%d 09:15:20")
        },
        {
            "amount": 20000.0,
            "currency": "KHR",
            "payer_name": "HENG SOKHA",
            "ref_code": "ABA-TEST-002",
            "bank_name": "ABA Bank",
            "time": now.strftime("%Y-%m-%d 10:45:00")
        },
        {
            "amount": 5.00,
            "currency": "USD",
            "payer_name": "KEO SREYMOM",
            "ref_code": "ABA-TEST-003",
            "bank_name": "ABA Bank",
            "time": now.strftime("%Y-%m-%d 12:30:15")
        },
        {
            "amount": 80000.0,
            "currency": "KHR",
            "payer_name": "SOK VISAL",
            "ref_code": "BK-TEST-004",
            "bank_name": "Bakong KHQR",
            "time": now.strftime("%Y-%m-%d 14:10:05")
        },
        {
            "amount": 45.00,
            "currency": "USD",
            "payer_name": "LONG DAVIN",
            "ref_code": "ABA-TEST-005",
            "bank_name": "ABA Bank",
            "time": now.strftime("%Y-%m-%d 16:50:30")
        },
    ]

    print("🌱 កំពុងបញ្ចូលទិន្នន័យសាកល្បង (Seeding test KHQR transactions)...")
    for item in sample_txns:
        success, msg, txn_id = db.save_transaction(
            amount=item["amount"],
            currency=item["currency"],
            payer_name=item["payer_name"],
            ref_code=item["ref_code"],
            bank_name=item["bank_name"],
            raw_text=f"Sample Payment: {item['currency']} {item['amount']} from {item['payer_name']}",
            transaction_time=item["time"]
        )
        if success:
            print(f"  + បញ្ចូលជោគជ័យ: {item['currency']} {item['amount']:,} ({item['payer_name']})")
        else:
            print(f"  - {msg}")

    print("\n" + "="*50)
    print("📊 លទ្ធផលរបាយការណ៍បូកសរុបថ្ងៃនេះ (Preview):")
    print("="*50)
    summary = db.get_summary_by_date(today_str)
    print(format_daily_summary(summary, title_prefix="ថ្ងៃនេះ (Today)"))

if __name__ == "__main__":
    seed_sample_data()
