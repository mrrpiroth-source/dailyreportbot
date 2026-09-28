"""
Reporter module for formatting KHQR sales and payment summaries in Khmer.
Provides clear breakdowns of:
- ទឹកប្រាក់សរុប (Total Amount in USD & KHR)
- ចំនួនលក់សរុប (Total Sales Count)
- ការប្រៀបធៀបការលក់ (ម្សិលមិញ VS ថ្ងៃនេះ - Growth / Decline)
- របាយការណ៍ប្រចាំឆ្នាំ (Yearly Report with monthly breakdown)
"""

from typing import Dict, Any, List, Optional


def format_currency(amount: float, currency: str) -> str:
    """Formats money with commas and currency symbol."""
    if currency == "USD":
        return f"${amount:,.2f}"
    else:  # KHR
        return f"{int(round(amount)):,} ៛"


def format_transaction_alert(data: Dict[str, Any]) -> str:
    """Formats an instant alert when a new payment is captured and saved."""
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
    title_prefix: str = "ប្រចាំថ្ងៃ"
) -> str:
    """
    Formats the daily summary message in Khmer detailing total amounts and sales counts.
    Replaces average with Yesterday VS Today sales comparison (growth / decline).
    """
    target_date = summary.get("date", "Today")
    total_usd = summary.get("total_usd", 0.0)
    count_usd = summary.get("count_usd", 0)
    
    total_khr = summary.get("total_khr", 0.0)
    count_khr = summary.get("count_khr", 0)
    
    total_count = summary.get("total_count", 0)

    usd_str = format_currency(total_usd, "USD")
    khr_str = format_currency(total_khr, "KHR")

    msg = (
        f"📊 <b>របាយការណ៍បូកសរុបការលក់ KHQR {title_prefix}</b>\n"
        f"🗓 <b>កាលបរិច្ឆេទ:</b> <code>{target_date}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛒 <b>ចំនួនលក់សរុប:</b> <b>{total_count}</b> លើក\n\n"
        f"💵 <b>ប្រាក់ដុល្លារ (USD):</b>\n"
        f"  • ទឹកប្រាក់សរុប: <b><code>{usd_str}</code></b> ({count_usd} លើក)\n\n"
        f"🇰🇭 <b>ប្រាក់រៀល (KHR):</b>\n"
        f"  • ទឹកប្រាក់សរុប: <b><code>{khr_str}</code></b> ({count_khr} លើក)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )

    # Yesterday VS Today Comparison section
    if comparison:
        diff_usd = comparison.get("diff_usd", 0.0)
        diff_khr = comparison.get("diff_khr", 0.0)
        diff_cnt = comparison.get("diff_count", 0)
        yest_date = comparison.get("yesterday_date", "ម្សិលមិញ")

        # USD difference
        if diff_usd > 0:
            usd_diff_str = f"+ ${diff_usd:,.2f} 📈 (កើនឡើង)"
        elif diff_usd < 0:
            usd_diff_str = f"- ${abs(diff_usd):,.2f} 📉 (ថយចុះ)"
        else:
            usd_diff_str = "ស្មើគ្នា ($0.00)"

        # KHR difference
        if diff_khr > 0:
            khr_diff_str = f"+ {int(abs(diff_khr)):,} ៛ 📈 (កើនឡើង)"
        elif diff_khr < 0:
            khr_diff_str = f"- {int(abs(diff_khr)):,} ៛ 📉 (ថយចុះ)"
        else:
            khr_diff_str = "ស្មើគ្នា (0 ៛)"

        # Transaction count difference
        if diff_cnt > 0:
            cnt_diff_str = f"+ {diff_cnt} លើក 📈 (កើនឡើង)"
        elif diff_cnt < 0:
            cnt_diff_str = f"- {abs(diff_cnt)} លើក 📉 (ថយចុះ)"
        else:
            cnt_diff_str = "ស្មើគ្នា"

        msg += (
            f"⚖️ <b>ការប្រៀបធៀបការលក់ ({yest_date} VS {target_date}):</b>\n"
            f"  • ប្រាក់ដុល្លារ ($): <b>{usd_diff_str}</b>\n"
            f"  • ប្រាក់រៀល (៛): <b>{khr_diff_str}</b>\n"
            f"  • ចំនួនប្រតិបត្តិការ: <b>{cnt_diff_str}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        )

    if total_count == 0:
        msg += "<i>📭 មិនទាន់មានប្រតិបត្តិការទូទាត់សម្រាប់ថ្ងៃនេះនៅឡើយទេ។</i>\n"
    else:
        msg += "✨ <i>ទិន្នន័យត្រូវបានកត់ត្រា និងបូកសរុបស្វ័យប្រវត្ត</i>"

    return msg


def format_yearly_summary(summary: Dict[str, Any]) -> str:
    """
    Formats the yearly summary message in Khmer detailing annual revenue and monthly breakdown.
    """
    target_year = summary.get("year", "This Year")
    total_usd = summary.get("total_usd", 0.0)
    count_usd = summary.get("count_usd", 0)
    total_khr = summary.get("total_khr", 0.0)
    count_khr = summary.get("count_khr", 0)
    total_count = summary.get("total_count", 0)
    active_days = summary.get("active_days", 0)

    usd_str = format_currency(total_usd, "USD")
    khr_str = format_currency(total_khr, "KHR")

    msg = (
        f"📆 <b>របាយការណ៍បូកសរុបការលក់ KHQR ប្រចាំឆ្នាំ</b>\n"
        f"🗓 <b>ប្រចាំឆ្នាំ:</b> <code>{target_year}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛒 <b>ចំនួនលក់សរុបពេញមួយឆ្នាំ:</b> <b>{total_count}</b> លើក\n"
        f"📅 <b>ចំនួនថ្ងៃដែលមានការលក់:</b> <b>{active_days}</b> ថ្ងៃ\n\n"
        f"💵 <b>សរុបប្រាក់ដុល្លារ (USD):</b> <b><code>{usd_str}</code></b> ({count_usd} លើក)\n"
        f"🇰🇭 <b>សរុបប្រាក់រៀល (KHR):</b> <b><code>{khr_str}</code></b> ({count_khr} លើក)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )

    breakdown = summary.get("monthly_breakdown", [])
    if breakdown:
        msg += "📅 <b>តារាងចំណូលតាមខែនីមួយៗ:</b>\n"
        for item in breakdown:
            m = item.get("month", "00")
            m_usd = format_currency(item.get("total_usd", 0.0), "USD")
            m_khr = format_currency(item.get("total_khr", 0.0), "KHR")
            m_cnt = item.get("count", 0)
            msg += f"  • <b>ខែ {m}:</b> {m_usd} | {m_khr} (<b>{m_cnt}</b> លើក)\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━\n"

    if total_count == 0:
        msg += f"<i>📭 មិនទាន់មានប្រតិបត្តិការសម្រាប់ឆ្នាំ {target_year} នៅឡើយទេ។</i>\n"
    else:
        msg += "✨ <i>របាយការណ៍បូកសរុបប្រាក់ចំណូលប្រចាំឆ្នាំស្វ័យប្រវត្ត</i>"

    return msg


def format_monthly_summary(summary: Dict[str, Any]) -> str:
    """
    Formats the monthly summary message in Khmer detailing total revenue and sales volume.
    """
    target_month = summary.get("month", "This Month")
    total_usd = summary.get("total_usd", 0.0)
    count_usd = summary.get("count_usd", 0)
    
    total_khr = summary.get("total_khr", 0.0)
    count_khr = summary.get("count_khr", 0)
    
    total_count = summary.get("total_count", 0)
    active_days = summary.get("active_days", 0)

    usd_str = format_currency(total_usd, "USD")
    khr_str = format_currency(total_khr, "KHR")

    return (
        f"📈 <b>របាយការណ៍បូកសរុបការលក់ KHQR ប្រចាំខែ</b>\n"
        f"🗓 <b>ប្រចាំខែ:</b> <code>{target_month}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛒 <b>ចំនួនលក់សរុបពេញមួយខែ:</b> <b>{total_count}</b> លើក\n"
        f"📅 <b>ចំនួនថ្ងៃដែលមានការលក់:</b> <b>{active_days}</b> ថ្ងៃ\n\n"
        f"💵 <b>សរុបប្រាក់ដុល្លារ (USD):</b> <b><code>{usd_str}</code></b> ({count_usd} លើក)\n"
        f"🇰🇭 <b>សរុបប្រាក់រៀល (KHR):</b> <b><code>{khr_str}</code></b> ({count_khr} លើក)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✨ <i>របាយការណ៍បូកសរុបប្រាក់ចំណូល និងបរិមាណលក់ប្រចាំខែ</i>"
    )


def format_range_summary(summary: Dict[str, Any], title_prefix: str = "៧ថ្ងៃចុងក្រោយ") -> str:
    """
    Formats multi-day/weekly summary report in Khmer.
    """
    start_date = summary.get("start_date", "")
    end_date = summary.get("end_date", "")
    total_usd = summary.get("total_usd", 0.0)
    count_usd = summary.get("count_usd", 0)
    
    total_khr = summary.get("total_khr", 0.0)
    count_khr = summary.get("count_khr", 0)
    
    total_count = summary.get("total_count", 0)

    usd_str = format_currency(total_usd, "USD")
    khr_str = format_currency(total_khr, "KHR")

    return (
        f"📊 <b>របាយការណ៍បូកសរុបការលក់ KHQR ({title_prefix})</b>\n"
        f"🗓 <b>ចន្លោះកាលបរិច្ឆេទ:</b> <code>{start_date}</code> ដល់ <code>{end_date}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛒 <b>ចំនួនលក់សរុប:</b> <b>{total_count}</b> លើក\n\n"
        f"💵 <b>សរុបប្រាក់ដុល្លារ (USD):</b> <b><code>{usd_str}</code></b> ({count_usd} លើក)\n"
        f"🇰🇭 <b>សរុបប្រាក់រៀល (KHR):</b> <b><code>{khr_str}</code></b> ({count_khr} លើក)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )
