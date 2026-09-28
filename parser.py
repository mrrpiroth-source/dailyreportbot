"""
Parser module for extracting KHQR and Cambodian Bank Merchant payment notification messages.
Supports:
1. ABA PayWay (e.g., "៛4,000 paid by HOUY DINAL (*407) on Sep 28, 05:18 PM via ABA PAY at SUN SREYPOV. Trx. ID: 179059072854148, APV: 511802.")
2. Standard ABA Merchant (English & Khmer)
3. Bakong KHQR, ACLEDA, Sathapana, Canadia, Wing Bank
"""

import re
from typing import Optional, Dict, Any

class KHQRParser:
    # 1. Specialized ABA PayWay Regex Pattern
    PAYWAY_PATTERN = re.compile(
        r'(?:([៛$]|KHR|USD)?\s*([\d,]+(?:\.\d+)?)\s*([៛$]|KHR|USD|រៀល|ដុល្លារ)?)\s+paid\s+by\s+([^(\n\r]+?)(?:\s*\([^)]*\))?\s+on\s+([A-Za-z]+\s+\d+,\s+\d+:\d+\s+[AP]M)(?:\s+via\s+([^.]+?))?\s+at\s+([^.]+?)\.\s*(?:Trx\.\s*ID|Trans\s*ID|Txn\s*ID|Ref)[:\s]*([0-9A-Za-z]+)(?:[,\s]*(?:APV|Approval\s*Code)[:\s]*([0-9A-Za-z]+))?',
        re.IGNORECASE
    )

    @classmethod
    def parse_message(cls, text: str) -> Optional[Dict[str, Any]]:
        """
        Parses an incoming notification message.
        Returns a dictionary with parsed details if it's a payment notification,
        or None if the message is not a recognized payment notification.
        """
        if not text or not isinstance(text, str):
            return None

        clean_text = text.strip()

        # Step 1: Check specialized ABA PayWay format first
        pw_match = cls.PAYWAY_PATTERN.search(clean_text)
        if pw_match:
            c1, amt_s, c2, payer, dt_str, via, merchant, trx_id, apv = pw_match.groups()
            cur_sym = (c1 or c2 or "").strip()
            currency = "KHR" if any(k in cur_sym for k in ["៛", "KHR", "រៀល"]) else "USD"
            try:
                amount = float(amt_s.replace(",", ""))
            except ValueError:
                amount = None

            if amount and amount > 0:
                return {
                    "amount": amount,
                    "currency": currency,
                    "payer_name": payer.strip(),
                    "ref_code": trx_id.strip() if trx_id else None,
                    "bank_name": "ABA Bank (PayWay)",
                    "raw_text": clean_text
                }

        # Step 2: General / Fallback Payment parsing for standard ABA Merchant, Bakong, etc.
        payment_keywords = [
            "payment received", "received payment", "payment successful",
            "paid by", "payway", "aba pay", "bakong", "khqr",
            "ទូទាត់ប្រាក់", "ទទួលបានការទូទាត់", "បានទទួល", "បានទូទាត់",
            "amount:", "ចំនួនទឹកប្រាក់", "trans id", "trx. id", "trx id", "approval code", "apv:"
        ]
        text_lower = clean_text.lower()
        if not any(kw in text_lower for kw in payment_keywords):
            return None

        # Extract Amount and Currency
        amount = None
        currency = None

        amount_match = re.search(
            r'(?:amount|ចំនួនទឹកប្រាក់|ចំនួនប្រាក់|received|ទូទាត់)\s*[:=]?\s*(\$?\s*[\d,]+(?:\.\d+)?\s*(?:\$|usd|khr|៛|រៀល)?)',
            clean_text,
            re.IGNORECASE
        )

        raw_amount_str = ""
        if amount_match:
            raw_amount_str = amount_match.group(1).strip()
        else:
            fallback_match = re.search(
                r'(\$|USD|KHR|៛)\s*([\d,]+(?:\.\d+)?)|([\d,]+(?:\.\d+)?)\s*(\$|USD|KHR|៛|រៀល)',
                clean_text,
                re.IGNORECASE
            )
            if fallback_match:
                raw_amount_str = fallback_match.group(0).strip()

        if raw_amount_str:
            if any(c in raw_amount_str.upper() for c in ["$", "USD", "ដុល្លារ"]):
                currency = "USD"
            elif any(c in raw_amount_str.upper() for c in ["៛", "KHR", "រៀល"]):
                currency = "KHR"
            else:
                if "khr" in text_lower or "៛" in clean_text or "រៀល" in clean_text:
                    currency = "KHR"
                else:
                    currency = "USD"

            num_clean = re.sub(r'[^\d.]', '', raw_amount_str)
            try:
                amount = float(num_clean)
            except ValueError:
                amount = None

        if amount is None or amount <= 0:
            return None

        # Extract Payer
        payer_name = None
        payer_match = re.search(
            r'(?:From|ពី|Payer|Customer|Sender|paid by)\s*[:=]?\s*([^\n\r]+)',
            clean_text,
            re.IGNORECASE
        )
        if payer_match:
            payer_name = payer_match.group(1).strip()
            payer_name = re.split(r'\s+(?:on|via|Date|កាលបរិច្ឆេទ|Ref|Approval|Trans|Trx|Terminal|ID|លេខកូដ|លេខយោង)\b', payer_name, flags=re.IGNORECASE)[0].strip()
            payer_name = payer_name.rstrip(".,;: ")
            # Remove trailing (*407) phone masks if present
            payer_name = re.sub(r'\s*\([^)]*\)', '', payer_name).strip()

        # Extract Reference / Trx ID / Approval Code
        ref_code = None
        ref_match = re.search(
            r'(?:Ref\s*/?\s*Trans\s*ID|Ref\s*[:=]|Trans\s*ID\s*[:=]|Trx\.\s*ID\s*[:=]|Txn\s*ID\s*[:=]|Approval\s*Code\s*[:=]|APV\s*[:=]|លេខកូដអនុម័ត\s*[:=]|លេខយោង\s*[:=]|លេខកូដប្រតិបត្តិការ\s*[:=]|លេខកូដ\s*[:=])\s*([A-Za-z0-9_-]+)',
            clean_text,
            re.IGNORECASE
        )
        if ref_match:
            ref_code = ref_match.group(1).strip()
        else:
            alt_ref = re.search(r'\b(?:Ref|TXN|Trx)\b[:#\s]*([0-9A-Za-z]{6,})', clean_text, re.IGNORECASE)
            if alt_ref:
                ref_code = alt_ref.group(1).strip()

        # Detect Bank / Provider
        bank_name = "ABA Bank"
        if "bakong" in text_lower:
            bank_name = "Bakong KHQR"
        elif "acleda" in text_lower:
            bank_name = "ACLEDA Bank"
        elif "canadia" in text_lower:
            bank_name = "Canadia Bank"
        elif "sathapana" in text_lower:
            bank_name = "Sathapana Bank"
        elif "wing" in text_lower:
            bank_name = "Wing Bank"

        return {
            "amount": amount,
            "currency": currency,
            "payer_name": payer_name,
            "ref_code": ref_code,
            "bank_name": bank_name,
            "raw_text": clean_text
        }
