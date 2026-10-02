"""
Reporter module for formatting KHQR sales and payment summaries in Khmer.
"""

from typing import Dict, Any, List, Optional
import datetime

MONTHS_KH = {
    "01": "មករា", "02": "កុម្ភៈ", "03": "មីនា", "04": "មេសា",
    "05": "ឧសភា", "06": "មិថុនា", "07": "កក្កដា", "08": "សីហា",
    "09": "កញ្ញា", "10": "តុលា", "11": "វិច្ឆិកា", "12": "ធ្នូ"
}

def format_currency(amount: float, currency: str) -> str:
    if currency == "USD":
        return f"${amount:,.2f}"
    else:  # KHR
        return f"{int(round(amount)):,} ៛"

def format_khmer_date(date_str: str) -> str:
    # "2025-08-04" -> "4 សីហា 2025"
    try:
        y, m, d = date_str.split('-')
        return f"{int(d)} {MONTHS_KH.get(m, m)} {y}"
    except:
        return date_str

def format_khmer_month(month_str: str) -> str:
    # "2025-08" -> "សីហា 2025"
    try:
        y, m = month_str.split('-')
        return f"{MONTHS_KH.get(m, m)} {y}"
    except:
        return month_str

def format_12h_time(time_str: str) -> str:
    # "14:21" -> "02:21PM"
    if not time_str:
        return ""
    try:
        h, m = map(int, time_str.split(':'))
        ampm = "AM" if h < 12 else "PM"
        h = h % 12
        if h == 0:
            h = 12
        return f"{h:02d}:{m:02d}{ampm}"
    except:
        return time_str

def format_transaction_alert(data: Dict[str, Any]) -> str:
    amount_str = format_currency(data["amount"], data["currency"])
    payer = data.get("payer_name") or "ភ្ញៀវ (Customer)"
    ref = data.get("ref_code") or "N/A"
    bank = data.get("bank_name") or "KHQR"
    return (
        f"✅ <b>ទទួលបានការទូទាត់ថ្មី ({bank})</b>\n\n"
        f"💵 <b>ចំនួនទឹកប្រាក់:</b> <code>{amount_str}</code>\n"
        f"👤 <b>ពីអតិថិជន:</b> <code>{payer}</code>\n"
        f"🔖 <b>លេខកូដយោង (Ref):</b> <code>{ref}</code>\n"
    )

def format_daily_summary(
    summary: Dict[str, Any], 
    comparison: Optional[Dict[str, Any]] = None,
    title_prefix: str = ""
) -> str:
    target_date = summary.get("date", "Today")
    total_usd = summary.get("total_usd", 0.0)
    count_usd = summary.get("count_usd", 0)
    total_khr = summary.get("total_khr", 0.0)
    count_khr = summary.get("count_khr", 0)
    
    khmer_date = format_khmer_date(target_date)
    
    # Get current time
    now_time = datetime.datetime.now().strftime("%H:%M")
    now_time_12h = format_12h_time(now_time)

    min_time = format_12h_time(summary.get("min_time", ""))
    max_time = format_12h_time(summary.get("max_time", ""))
    time_range = f"{min_time} -> {max_time}" if min_time and max_time else "គ្មានប្រតិបត្តិការ"

    msg = (
        f"សរុបប្រតិបត្តិការថ្ងៃទី <b>{khmer_date}</b>\n"
        f"ម៉ោងបូកសរុប <b>{now_time_12h}</b>\n\n"
        f"<pre>\n"
        f"(៛): {int(total_khr):<8} | ប្រតិបត្តិការ: {count_khr}\n"
        f"($): {total_usd:<8.2f} | ប្រតិបត្តិការ: {count_usd}\n"
        f"</pre>\n"
        f"ម៉ោងប្រតិបត្តិការ: {time_range}\n"
    )
    return msg

def build_table_report(title: str, breakdowns: List[Dict[str, Any]], total_khr: float, total_usd: float, total_count: int, is_month: bool = False) -> str:
    msg = f"{title}\n\n"
    
    for row in breakdowns:
        day_str = row.get("day", "00")
        try:
            day_str = str(int(day_str))
        except:
            pass
        
        k_val = int(row.get("total_khr", 0.0))
        u_val = float(row.get("total_usd", 0.0))
        cnt = int(row.get("count", 0))
        
        # Format as list: 📅 ថ្ងៃទី X: ៛1000 | $1.00 | 5 លក់
        if is_month:
            msg += f"📅 ថ្ងៃទី {day_str}: ៛{k_val:,} | ${u_val:,.2f} | {cnt} លក់\n"
        else:
            msg += f"📅 ថ្ងៃ {day_str}: ៛{k_val:,} | ${u_val:,.2f} | {cnt} លក់\n"
        
    msg += "\n"
    msg += f"<b>Tot.: ៛{int(total_khr):,} | ${total_usd:,.2f} | {total_count} លក់</b>\n"
    return msg

def format_yearly_summary(summary: Dict[str, Any]) -> str:
    target_year = summary.get("year", "This Year")
    total_usd = summary.get("total_usd", 0.0)
    total_khr = summary.get("total_khr", 0.0)
    total_count = summary.get("total_count", 0)
    
    breakdown = summary.get("monthly_breakdown", [])
    
    title = f"សរុបប្រតិបត្តិការ ឆ្នាំ {target_year}"
    msg = f"{title}\n\n<pre>\n"
    msg += f"{'ខែ':<4} {'(៛)':<10} {'($)':<8} {'សរុបចំនួន'}\n"
    msg += "-" * 33 + "\n"
    
    for row in breakdown:
        m_str = row.get("month", "00")
        try:
            m_str = str(int(m_str))
        except:
            pass
        k_val = int(row.get("total_khr", 0.0))
        u_val = float(row.get("total_usd", 0.0))
        cnt = int(row.get("count", 0))
        msg += f"{m_str:<4} {k_val:<10} {u_val:<8.2f} {cnt}\n"
        
    msg += "-" * 33 + "\n"
    msg += f"Tot.: ៛{int(total_khr):<8} ${total_usd:<8.2f} {total_count}\n</pre>\n"
    return msg

def format_monthly_summary(summary: Dict[str, Any]) -> str:
    target_month = summary.get("month", "This Month")
    khmer_month = format_khmer_month(target_month)
    total_usd = summary.get("total_usd", 0.0)
    total_khr = summary.get("total_khr", 0.0)
    total_count = summary.get("total_count", 0)
    breakdowns = summary.get("daily_breakdown", [])
    
    title = f"សរុបប្រតិបត្តិការ {khmer_month}"
    return build_table_report(title, breakdowns, total_khr, total_usd, total_count, is_month=True)

def format_range_summary(summary: Dict[str, Any], title_prefix: str = "") -> str:
    start_date = summary.get("start_date", "")
    end_date = summary.get("end_date", "")
    khmer_start = format_khmer_date(start_date)
    khmer_end = format_khmer_date(end_date)
    
    # Try to simplify range e.g. "28-3 សីហា 2025"
    title_date = f"{khmer_start} - {khmer_end}"
    try:
        sy, sm, sd = start_date.split('-')
        ey, em, ed = end_date.split('-')
        if sy == ey and sm == em:
            title_date = f"{int(sd)}-{int(ed)} {MONTHS_KH.get(sm, sm)} {sy}"
        elif sy == ey:
            title_date = f"{int(sd)} {MONTHS_KH.get(sm, sm)} - {int(ed)} {MONTHS_KH.get(em, em)} {sy}"
    except:
        pass
        
    total_usd = summary.get("total_usd", 0.0)
    total_khr = summary.get("total_khr", 0.0)
    total_count = summary.get("total_count", 0)
    breakdowns = summary.get("daily_breakdown", [])
    
    title = f"សរុបប្រតិបត្តិការ ថ្ងៃទី {title_date}"
    return build_table_report(title, breakdowns, total_khr, total_usd, total_count)

def format_recent_transactions(transactions: List[Dict[str, Any]], limit: int = 5) -> str:
    if not transactions:
        return "មិនទាន់មានប្រតិបត្តិការ។"
    msg = "ប្រតិបត្តិការចុងក្រោយ:\n\n<pre>\n"
    for txn in transactions:
        amt_str = format_currency(txn["amount"], txn["currency"])
        time_str = txn.get("transaction_time", "")[-8:-3] # HH:MM
        msg += f"{time_str} {amt_str}\n"
    msg += "</pre>"
    return msg
