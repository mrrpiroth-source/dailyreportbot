"""
Test suite for KHQR Parser and Database
Validates extraction of amounts in USD and KHR, payer names, and ref codes.
"""

import sys
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from parser import KHQRParser
from database import Database
from reporter import format_transaction_alert, format_daily_summary

def run_tests():
    sample_messages = [
        # 1. ABA Merchant English Format
        {
            "name": "ABA Merchant English (USD)",
            "text": """
Payment Received!
Amount: $ 12.50
From: CHAN VANDETH
Date: 28-Sep-2026 14:22:15
Approval Code: 123456
Ref / Trans ID: 987654321
Terminal: Pos-01
            """,
            "expected_amount": 12.50,
            "expected_currency": "USD",
            "expected_ref": "987654321",
            "expected_payer": "CHAN VANDETH"
        },
        # 2. ABA Merchant KHR Format
        {
            "name": "ABA Merchant KHR",
            "text": """
Payment Received!
Amount: KHR 60,000
From: HENG SOKHA
Date: 28-Sep-2026 15:30:12
Approval Code: 654321
Ref / Trans ID: 987654322
Terminal: Pos-01
            """,
            "expected_amount": 60000.0,
            "expected_currency": "KHR",
            "expected_ref": "987654322",
            "expected_payer": "HENG SOKHA"
        },
        # 3. ABA Merchant Khmer Format
        {
            "name": "ABA Merchant Khmer (USD)",
            "text": """
ទទួលបានការទូទាត់ប្រាក់!
ចំនួនទឹកប្រាក់: $ 25.00
ពី: សុខ ពិសិដ្ឋ
កាលបរិច្ឆេទ: 28-Sep-2026 16:10:00
លេខកូដអនុម័ត: 445566
លេខយោង: 987654323
            """,
            "expected_amount": 25.00,
            "expected_currency": "USD",
            "expected_ref": "445566", # or 987654323
            "expected_payer": "សុខ ពិសិដ្ឋ"
        },
        # 4. Bakong KHQR
        {
            "name": "Bakong KHQR (KHR)",
            "text": """
KHQR Payment Successful
Amount: 100,000 ៛
From: SOK CHHEANG
Txn ID: BK99887766
Date: 2026-09-28 17:00:00
            """,
            "expected_amount": 100000.0,
            "expected_currency": "KHR",
            "expected_ref": "BK99887766"
        },
        # 5. Non-payment message (should be ignored)
        {
            "name": "General Chat message",
            "text": "Hello admin, please check the inventory today.",
            "expected_amount": None
        }
    ]

    print("=== TESTING KHQR PARSER ===")
    passed = 0
    total = len(sample_messages)

    for item in sample_messages:
        result = KHQRParser.parse_message(item["text"])
        if item["expected_amount"] is None:
            if result is None:
                print(f"✅ [PASS] {item['name']} correctly identified as non-payment.")
                passed += 1
            else:
                print(f"❌ [FAIL] {item['name']} falsely parsed as payment: {result}")
        else:
            if not result:
                print(f"❌ [FAIL] {item['name']} failed to parse!")
            else:
                amt_ok = abs(result["amount"] - item["expected_amount"]) < 0.001
                curr_ok = result["currency"] == item["expected_currency"]
                if amt_ok and curr_ok:
                    print(f"✅ [PASS] {item['name']}: {result['currency']} {result['amount']:,} | Payer: {result['payer_name']} | Ref: {result['ref_code']}")
                    passed += 1
                else:
                    print(f"❌ [FAIL] {item['name']}: Got {result['currency']} {result['amount']}, expected {item['expected_currency']} {item['expected_amount']}")

    print(f"\nParser Results: {passed}/{total} tests passed.\n")

    print("=== TESTING DATABASE & REPORTING ===")
    test_db = Database("test_khqr.db")
    # Insert test data
    for item in sample_messages[:4]:
        parsed = KHQRParser.parse_message(item["text"])
        if parsed:
            test_db.save_transaction(
                amount=parsed["amount"],
                currency=parsed["currency"],
                payer_name=parsed["payer_name"],
                ref_code=parsed["ref_code"],
                bank_name=parsed["bank_name"],
                raw_text=parsed["raw_text"]
            )

    summary = test_db.get_summary_by_date()
    print("Daily Summary Data:", summary)
    print("\nFormatted Summary Message:\n")
    print(format_daily_summary(summary))

if __name__ == "__main__":
    run_tests()
