"""
Telegram Bot implementation using Telethon.
Supports:
1. Monitoring KHQR payment notifications (from ABA Merchant bot or group messages)
2. Storing transactions to SQLite (preventing duplicates via Ref ID)
3. Daily summary scheduler (at user-configured time, e.g., 22:00 Phnom Penh Time)
4. Interactive commands: /today, /yesterday, /week, /month, /report, /recent, /help
5. Interactive Inline Buttons for 1-click reports
"""

import sys
import io
import os
import asyncio
import logging
import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Any, cast, Awaitable

# Ensure UTF-8 output on Windows terminals
if sys.platform == "win32":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

from telethon import TelegramClient, events, Button
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import config
from database import Database, CAMBODIA_TZ, get_cambodia_now, get_cambodia_today_str
from parser import KHQRParser
from reporter import (
    format_daily_summary,
    format_monthly_summary,
    format_range_summary,
    format_transaction_alert,
    format_currency
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("KHQR_Bot")

# Initialize database
db = Database(config.DB_PATH)


def get_menu_buttons():
    """Returns interactive inline buttons for quick report access."""
    return [
        [
            Button.inline("📊 ថ្ងៃនេះ (Today)", data=b"btn_today"),
            Button.inline("📅 ម្សិលមិញ (Yesterday)", data=b"btn_yesterday"),
        ],
        [
            Button.inline("🗓 ៧ថ្ងៃចុងក្រោយ (Week)", data=b"btn_week"),
            Button.inline("📈 ប្រចាំខែ (Month)", data=b"btn_month"),
        ],
        [
            Button.inline("📋 ប្រតិបត្តិការ ៥ ចុងក្រោយ", data=b"btn_recent")
        ]
    ]


async def send_daily_summary(client: TelegramClient, target_chat_id: Optional[Any] = None):
    """Generates and sends the daily summary report to the target chat."""
    chat_id = target_chat_id or config.REPORT_CHAT_ID or config.MONITOR_CHAT_ID
    if not chat_id:
        logger.warning("No REPORT_CHAT_ID or MONITOR_CHAT_ID configured. Cannot send daily summary.")
        return

    today_str = get_cambodia_today_str()
    summary = db.get_summary_by_date(today_str)
    message_text = format_daily_summary(summary, title_prefix="ប្រចាំថ្ងៃ")

    try:
        await client.send_message(chat_id, message_text, parse_mode="html", buttons=get_menu_buttons())
        logger.info(f"Daily summary successfully sent for {today_str} to {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send daily summary to {chat_id}: {e}")


def check_permission(sender_id: Optional[int]) -> bool:
    """Checks if a user is permitted to view financial reports."""
    if sender_id is None:
        return False
    if not config.RESTRICT_REPORTS_TO_ADMIN:
        return True
    if not config.ADMIN_USER_IDS:
        # If no admin IDs are configured in .env yet, allow access to prevent lockout
        return True
    if sender_id in config.ADMIN_USER_IDS:
        return True
    return db.is_user_authorized(sender_id)

def is_admin(sender_id: Optional[int]) -> bool:
    """Checks if a user has full Owner/Super Admin privileges."""
    if sender_id is None:
        return False
    if not config.ADMIN_USER_IDS:
        return True
    return sender_id in config.ADMIN_USER_IDS


def setup_handlers(client: TelegramClient):
    """Sets up event handlers for incoming messages, commands, and button clicks."""

    # 1. Callback query handler for inline button taps
    @client.on(events.CallbackQuery)
    async def callback_handler(event: events.CallbackQuery.Event):
        sender_id = event.sender_id
        if not check_permission(sender_id):
            await event.answer(
                "⛔ អ្នកមិនមានសិទ្ធិមើលរបាយការណ៍ហិរញ្ញវត្ថុនេះទេ! សូមទាក់ទងម្ចាស់ហាង (Admin)។",
                alert=True
            )
            return

        data = event.data

        if data == b"btn_today":
            summary = db.get_summary_by_date(get_cambodia_today_str())
            msg = format_daily_summary(summary, title_prefix="ថ្ងៃនេះ (Today)")
            await event.respond(msg, parse_mode="html", buttons=get_menu_buttons())
            await event.answer()

        elif data == b"btn_yesterday":
            yesterday = (get_cambodia_now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            summary = db.get_summary_by_date(yesterday)
            msg = format_daily_summary(summary, title_prefix="ម្សិលមិញ (Yesterday)")
            await event.respond(msg, parse_mode="html", buttons=get_menu_buttons())
            await event.answer()

        elif data == b"btn_week":
            summary = db.get_summary_by_days(7)
            msg = format_range_summary(summary, title_prefix="៧ថ្ងៃចុងក្រោយ")
            await event.respond(msg, parse_mode="html", buttons=get_menu_buttons())
            await event.answer()

        elif data == b"btn_month":
            current_month = get_cambodia_now().strftime("%Y-%m")
            summary = db.get_summary_by_month(current_month)
            msg = format_monthly_summary(summary)
            await event.respond(msg, parse_mode="html", buttons=get_menu_buttons())
            await event.answer()

        elif data == b"btn_recent":
            recent = db.get_recent_transactions(limit=5)
            if not recent:
                await event.respond("📭 មិនទាន់មានប្រតិបត្តិការត្រូវបានកត់ត្រានៅឡើយទេ។", parse_mode="html")
            else:
                reply_lines = ["📋 <b>ប្រតិបត្តិការ ៥ ចុងក្រោយ:</b>\n"]
                for item in recent:
                    amt_str = format_currency(item["amount"], item["currency"])
                    payer = item.get("payer_name") or "ភ្ញៀវ"
                    ref = item.get("ref_code") or "N/A"
                    time_str = item.get("transaction_time") or ""
                    reply_lines.append(f"• <b>{amt_str}</b> | {payer} | Ref: <code>{ref}</code> ({time_str})")
                await event.respond("\n".join(reply_lines), parse_mode="html", buttons=get_menu_buttons())
            await event.answer()

    # 2. Listener for new messages (monitoring KHQR payments & text commands)
    @client.on(events.NewMessage)
    async def message_listener(event: events.NewMessage.Event):
        text = event.raw_text
        if not text:
            return

        chat_id = event.chat_id
        logger.info(f"Incoming message (Chat: {chat_id}, Sender: {event.sender_id}): {repr(text[:60])}")

        # If MONITOR_CHAT_ID is specified, only process messages from that chat
        if config.MONITOR_CHAT_ID and chat_id != config.MONITOR_CHAT_ID:
            # Still allow commands in private chat
            if not event.is_private and not text.startswith(("/", ".")):
                return

        # Handle Commands
        text_stripped = text.strip()
        cmd = text_stripped.split()[0].lower() if text_stripped else ""

        # 1. Identity command: Check Telegram ID (Publicly accessible)
        if cmd in ("/myid", ".myid", "/id", ".id"):
            sender = await event.get_sender()
            name = getattr(sender, 'first_name', 'User') or 'User'
            extra_chat = f"\n👥 Group ID: <code>{chat_id}</code>\n" if not event.is_private else "\n"
            await event.reply(
                f"🆔 <b>ព័ត៌មានអត្តសញ្ញាណ Telegram របស់អ្នក:</b>\n\n"
                f"👤 ឈ្មោះ: <b>{name}</b>\n"
                f"🔢 Telegram User ID: <code>{event.sender_id}</code>"
                f"{extra_chat}\n"
                f"💡 <i>ផ្ញើ User ID នេះទៅកាន់ម្ចាស់ហាង (Admin) ដើម្បីស្នើសុំសិទ្ធិមើលរបាយការណ៍ហិរញ្ញវត្ថុ។</i>",
                parse_mode="html"
            )
            return

        # 2. RBAC Management: Add staff / authorize user (Admin only)
        if cmd in ("/adduser", ".adduser"):
            if not is_admin(event.sender_id):
                await event.reply("⛔ <b>សិទ្ធិត្រូវបានបដិសេធ:</b> មានតែម្ចាស់អាជីវកម្ម (Admin) ប៉ុណ្ណោះដែលអាចបន្ថែមសិទ្ធិបុគ្គលិកបាន!", parse_mode="html")
                return

            parts = text_stripped.split()
            target_id = None
            role = "staff"

            if event.is_reply:
                reply_msg = await event.get_reply_message()
                target_id = reply_msg.sender_id
                if len(parts) > 1:
                    role = parts[1].lower()
            elif len(parts) > 1 and parts[1].isdigit():
                target_id = int(parts[1])
                if len(parts) > 2:
                    role = parts[2].lower()

            if not target_id:
                await event.reply("⚠️ សូមបញ្ជាក់ User ID: <code>/adduser 12345678 [staff/admin]</code> ឬ Reply លើសាររបស់បុគ្គលិកនោះ!", parse_mode="html")
                return

            try:
                target_user = await client.get_entity(target_id)
                uname = getattr(target_user, 'username', None)
                fname = getattr(target_user, 'first_name', '') or ''
                if getattr(target_user, 'last_name', None):
                    fname += f" {target_user.last_name}"
            except Exception:
                uname = None
                fname = f"User {target_id}"

            ok = db.add_authorized_user(user_id=target_id, username=uname, full_name=fname, role=role, added_by=event.sender_id)
            if ok:
                await event.reply(
                    f"✅ <b>បានបន្ថែមសិទ្ធិដោយជោគជ័យ!</b>\n\n"
                    f"👤 ឈ្មោះ: <b>{fname}</b>\n"
                    f"🔢 ID: <code>{target_id}</code>\n"
                    f"🛡️ តួនាទី: <b>{role.upper()}</b>\n\n"
                    f"<i>បុគ្គលិកនេះត្រូវបានអនុញ្ញាតឱ្យមើលរបាយការណ៍លក់ និងប្រាក់ចំណូលបានហើយ។</i>",
                    parse_mode="html"
                )
            else:
                await event.reply("❌ បរាជ័យក្នុងការបន្ថែមសិទ្ធិ។", parse_mode="html")
            return

        # 3. RBAC Management: Revoke access (Admin only)
        if cmd in ("/removeuser", ".removeuser"):
            if not is_admin(event.sender_id):
                await event.reply("⛔ មានតែម្ចាស់អាជីវកម្ម (Admin) ប៉ុណ្ណោះដែលអាចដកសិទ្ធិបាន!", parse_mode="html")
                return

            parts = text_stripped.split()
            target_id = None
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                target_id = reply_msg.sender_id
            elif len(parts) > 1 and parts[1].isdigit():
                target_id = int(parts[1])

            if not target_id:
                await event.reply("⚠️ សូមបញ្ជាក់ User ID: <code>/removeuser 12345678</code> ឬ Reply លើសាររបស់បុគ្គលិកនោះ!", parse_mode="html")
                return

            ok = db.remove_authorized_user(target_id)
            if ok:
                await event.reply(f"🗑️ <b>បានដកសិទ្ធិប្រើប្រាស់សម្រាប់ ID <code>{target_id}</code> រួចរាល់!</b>", parse_mode="html")
            else:
                await event.reply("⚠️ មិនអាចរកឃើញបុគ្គលិកនេះក្នុងបញ្ជីសិទ្ធិឡើយ។", parse_mode="html")
            return

        # 4. RBAC Management: List authorized staff (Admin only)
        if cmd in ("/users", ".users", "/listusers", ".listusers"):
            if not is_admin(event.sender_id):
                await event.reply("⛔ មានតែម្ចាស់អាជីវកម្ម (Admin) ប៉ុណ្ណោះដែលអាចមើលបញ្ជីបុគ្គលិកបាន!", parse_mode="html")
                return

            users = db.list_authorized_users()
            lines = ["👥 <b>បញ្ជីអ្នកដែលមានសិទ្ធិមើលរបាយការណ៍ហិរញ្ញវត្ថុ:</b>\n"]
            for admin_id in config.ADMIN_USER_IDS:
                lines.append(f"👑 <b>Owner/Admin:</b> <code>{admin_id}</code>")

            if not users:
                lines.append("\n<i>មិនទាន់មានបុគ្គលិកបន្ថែមក្រៅពី Owner នៅឡើយទេ។ (ប្រើ <code>/adduser ID</code> ដើម្បីបន្ថែម)</i>")
            else:
                lines.append("\n<b>បុគ្គលិកដែលបានអនុញ្ញាត:</b>")
                for u in users:
                    name = u.get("full_name") or u.get("username") or f"ID {u['user_id']}"
                    role = u.get("role", "staff").upper()
                    lines.append(f"• 👤 <b>{name}</b> (<code>{u['user_id']}</code>) — [{role}]")

            await event.reply("\n".join(lines), parse_mode="html")
            return

        # 5. Permission Gate: Protect financial report commands
        report_cmd_prefixes = (
            "/today", ".today", "បូកសរុបថ្ងៃនេះ",
            "/yesterday", ".yesterday", "ម្សិលមិញ",
            "/week", ".week", "/weekly", ".weekly", "សប្តាហ៍នេះ",
            "/month", ".month", "បូកសរុបខែនេះ",
            "/report", ".report",
            "/recent", ".recent",
            "/sync", ".sync", "/backfill"
        )
        if any(cmd.startswith(p) for p in report_cmd_prefixes):
            if not check_permission(event.sender_id):
                await event.reply(
                    "⛔ <b>ការចូលប្រើប្រាស់ត្រូវបានបដិសេធ (Access Denied)</b>\n\n"
                    "🔒 របាយការណ៍ហិរញ្ញវត្ថុ និងប្រាក់ចំណូល ត្រូវបានការពារដោយសុវត្ថិភាពខ្ពស់។\n"
                    "មានតែម្ចាស់អាជីវកម្ម ឬបុគ្គលិកដែលមានការអនុញ្ញាតទើបអាចមើលបាន។\n\n"
                    f"💡 <i>សូមផ្ញើ Telegram User ID របស់អ្នក <code>{event.sender_id}</code> ទៅកាន់ Admin ដើម្បីស្នើសុំសិទ្ធិ។</i>",
                    parse_mode="html"
                )
                return

        # 6. Execute Allowed Report Commands
        if cmd in ("/today", ".today", "បូកសរុបថ្ងៃនេះ"):
            summary = db.get_summary_by_date(get_cambodia_today_str())
            msg = format_daily_summary(summary, title_prefix="ថ្ងៃនេះ (Today)")
            await event.reply(msg, parse_mode="html", buttons=get_menu_buttons())
            return

        elif cmd in ("/yesterday", ".yesterday", "ម្សិលមិញ"):
            yesterday = (get_cambodia_now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            summary = db.get_summary_by_date(yesterday)
            msg = format_daily_summary(summary, title_prefix="ម្សិលមិញ (Yesterday)")
            await event.reply(msg, parse_mode="html", buttons=get_menu_buttons())
            return

        elif cmd in ("/week", ".week", "/weekly", ".weekly", "សប្តាហ៍នេះ"):
            summary = db.get_summary_by_days(7)
            msg = format_range_summary(summary, title_prefix="៧ថ្ងៃចុងក្រោយ")
            await event.reply(msg, parse_mode="html", buttons=get_menu_buttons())
            return

        elif cmd in ("/month", ".month", "បូកសរុបខែនេះ"):
            current_month = get_cambodia_now().strftime("%Y-%m")
            summary = db.get_summary_by_month(current_month)
            msg = format_monthly_summary(summary)
            await event.reply(msg, parse_mode="html", buttons=get_menu_buttons())
            return

        elif cmd.startswith(("/report", ".report")):
            parts = text_stripped.split()
            if len(parts) > 1:
                target_date = parts[1].strip()
                try:
                    datetime.datetime.strptime(target_date, "%Y-%m-%d")
                    summary = db.get_summary_by_date(target_date)
                    msg = format_daily_summary(summary, title_prefix=f"ថ្ងៃ {target_date}")
                    await event.reply(msg, parse_mode="html", buttons=get_menu_buttons())
                except ValueError:
                    await event.reply(
                        "⚠️ ទម្រង់កាលបរិច្ឆេទមិនត្រឹមត្រូវ! សូមប្រើ: <code>/report YYYY-MM-DD</code>\nឧទាហរណ៍: <code>/report 2026-09-28</code>",
                        parse_mode="html"
                    )
            else:
                summary = db.get_summary_by_date(get_cambodia_today_str())
                msg = format_daily_summary(summary, title_prefix="ថ្ងៃនេះ (Today)")
                await event.reply(msg, parse_mode="html", buttons=get_menu_buttons())
            return

        elif cmd in ("/recent", ".recent"):
            recent = db.get_recent_transactions(limit=5)
            if not recent:
                await event.reply("📭 មិនទាន់មានប្រតិបត្តិការត្រូវបានកត់ត្រានៅឡើយទេ។", parse_mode="html")
                return
            reply_lines = ["📋 <b>ប្រតិបត្តិការ ៥ ចុងក្រោយ:</b>\n"]
            for item in recent:
                amt_str = format_currency(item["amount"], item["currency"])
                payer = item.get("payer_name") or "ភ្ញៀវ"
                ref = item.get("ref_code") or "N/A"
                time_str = item.get("transaction_time") or ""
                reply_lines.append(f"• <b>{amt_str}</b> | {payer} | Ref: <code>{ref}</code> ({time_str})")
            await event.reply("\n".join(reply_lines), parse_mode="html", buttons=get_menu_buttons())
            return

        elif cmd.startswith(("/sync", ".sync", "/backfill")):
            parts = text_stripped.split()
            limit = 200
            if len(parts) > 1 and parts[1].isdigit():
                limit = int(parts[1])

            target_chat = config.MONITOR_CHAT_ID or chat_id
            await event.reply(f"🔄 កំពុងទាញយក និងពិនិត្យសារចាស់ៗចំនួន <b>{limit}</b> សារពី Group...", parse_mode="html")
            
            from sync_history import sync_previous_messages
            res = await sync_previous_messages(client, target_chat, limit=limit)
            if res:
                reply_text = (
                    "✅ <b>ការទាញយកទិន្នន័យចាស់ៗជោគជ័យ:</b>\n\n"
                    f"• សារដែលបានពិនិត្យ: <b>{res['total_scanned']}</b> សារ\n"
                    f"• ប្រតិបត្តិការ KHQR ទាំងអស់: <b>{res['found_payments']}</b> លើក\n"
                    f"• ប្រតិបត្តិការថ្មីដែលបានកត់ត្រា: <b>{res['new_added']}</b> លើក\n"
                    f"• ប្រតិបត្តិការចាស់ដែលមានរួចហើយ: <b>{res['duplicates']}</b> លើក\n"
                    f"• ទឹកប្រាក់ថ្មីដែលទើបកត់ត្រា: <b>${res['usd_total']:,.2f}</b> | <b>{int(res['khr_total']):,} ៛</b>\n\n"
                    "💡 <i>លោកអ្នកអាចវាយ <code>/today</code> ឬ <code>/week</code> ដើម្បីមើលរបាយការណ៍បច្ចុប្បន្នភាព!</i>"
                )
                await event.reply(reply_text, parse_mode="html", buttons=get_menu_buttons())
            else:
                await event.reply("⚠️ មិនអាចទាញយកសារចាស់ៗបានទេ។ សូមពិនិត្យមើលសិទ្ធិរបស់ Bot ក្នុង Group។", parse_mode="html")
            return

        elif cmd in ("/menu", ".menu", "/start", ".start", "/help", ".help"):
            is_adm = is_admin(event.sender_id)
            help_text = (
                "🤖 <b>KHQR Sales & Daily Report Telegram Bot</b>\n\n"
                "📌 <b>របាយការណ៍ដែលលោកអ្នកអាចមើលបាន:</b>\n"
                "• <b>ទឹកប្រាក់សរុប:</b> បែងចែកប្រាក់ដុល្លារ ($) និងប្រាក់រៀល (៛)\n"
                "• <b>ចំនួនលក់សរុប:</b> រាប់ចំនួនលើកនៃការទូទាត់ជោគជ័យ\n"
                "• <b>មធ្យមភាគការលក់:</b> បង្ហាញតម្លៃមធ្យមក្នុងមួយវិក្កយបត្រ\n\n"
                "🛡️ <b>សុវត្ថិភាព និងការគ្រប់គ្រងសិទ្ធិ:</b>\n"
                "• <code>/myid</code> — មើល Telegram User ID របស់អ្នក\n"
            )
            if is_adm:
                help_text += (
                    "• <code>/adduser ID [role]</code> — បន្ថែមសិទ្ធិឱ្យបុគ្គលិក\n"
                    "• <code>/removeuser ID</code> — ដកសិទ្ធិបុគ្គលិក\n"
                    "• <code>/users</code> — បង្ហាញបញ្ជីបុគ្គលិកមានសិទ្ធិ\n"
                    "• <code>/sync</code> — ទាញយកសារចាស់ៗពីមុនមកបូកបញ្ចូល\n\n"
                )
            help_text += "👇 <b>សូមចុចប៊ូតុងខាងក្រោមដើម្បីមើលរបាយការណ៍:</b>"
            await event.reply(help_text, parse_mode="html", buttons=get_menu_buttons())
            return

        # 3. Check if the incoming message is a KHQR Payment Notification
        parsed_data = KHQRParser.parse_message(text)
        if parsed_data:
            # Determine transaction time
            msg_date = event.date.astimezone(CAMBODIA_TZ).strftime("%Y-%m-%d %H:%M:%S")

            success, message, txn_id = db.save_transaction(
                amount=parsed_data["amount"],
                currency=parsed_data["currency"],
                payer_name=parsed_data["payer_name"],
                ref_code=parsed_data["ref_code"],
                bank_name=parsed_data["bank_name"],
                raw_text=text,
                transaction_time=msg_date
            )

            if success:
                logger.info(
                    f"Saved Transaction #{txn_id}: {parsed_data['currency']} {parsed_data['amount']} "
                    f"from {parsed_data['payer_name']} (Ref: {parsed_data['ref_code']})"
                )
                if config.ENABLE_INSTANT_ALERT:
                    alert_text = format_transaction_alert(parsed_data)
                    await event.reply(alert_text, parse_mode="html")
            else:
                logger.warning(f"Ignored transaction: {message}")


def setup_scheduler(client: TelegramClient) -> AsyncIOScheduler:
    """Configures APScheduler for sending daily reports at the specified hour:minute."""
    scheduler = AsyncIOScheduler(timezone=CAMBODIA_TZ)
    try:
        report_time = config.DAILY_REPORT_TIME.strip()
        hour, minute = report_time.split(":")
        scheduler.add_job(
            send_daily_summary,
            CronTrigger(hour=int(hour), minute=int(minute), timezone=CAMBODIA_TZ),
            args=[client],
            id="khqr_daily_summary",
            name="KHQR Daily Summary Report",
            replace_existing=True
        )
        logger.info(f"Scheduled Daily Summary at {hour}:{minute} (Asia/Phnom_Penh)")
    except Exception as e:
        logger.error(f"Failed to setup daily report schedule: {e}")
    return scheduler


async def start_bot():
    """Main startup routine for the Telegram client."""
    if not config.API_ID or not config.API_HASH:
        print("\n" + "="*60)
        print("❌ កំហុស (ERROR): សូមបំពេញ TELEGRAM_API_ID និង TELEGRAM_API_HASH នៅក្នុងឯកសារ .env ជាមុនសិន!")
        print("អ្នកអាចយក API_ID & API_HASH បានដោយឥតគិតថ្លៃពី: https://my.telegram.org")
        print("="*60 + "\n")
        return

    session_name = "khqr_session"
    client = TelegramClient(session_name, config.API_ID, config.API_HASH)

    print("🚀 កំពុងដំណើរការ KHQR Daily Report Bot...")

    if config.BOT_TOKEN:
        await cast(Awaitable[Any], client.start(bot_token=config.BOT_TOKEN))
        me = await client.get_me()
        print(f"✅ Bot បានដំណើរការជោគជ័យជា Bot Account: @{me.username}")
    elif config.PHONE_NUMBER:
        await cast(Awaitable[Any], client.start(phone=config.PHONE_NUMBER))
        me = await client.get_me()
        user_name = me.first_name + (f" {me.last_name}" if me.last_name else "")
        print(f"✅ បានភ្ជាប់ជោគជ័យជា User Account: {user_name} (@{me.username or 'No username'})")
        print("💡 គណនីនេះនឹងអានសារពី Bank Bot នៅក្នុង Group បាន ១០០% ដោយគ្មានបញ្ហា Telegram Block Bot-to-Bot!")
    else:
        await cast(Awaitable[Any], client.start())
        me = await client.get_me()
        print(f"✅ បានភ្ជាប់ជោគជ័យ: {me.first_name} (@{me.username or 'No username'})")

    # Setup handlers and scheduler
    setup_handlers(client)
    scheduler = setup_scheduler(client)
    scheduler.start()

    print(f"⏰ ម៉ោងផ្ញើរបាយការណ៍បូកសរុបប្រចាំថ្ងៃ: {config.DAILY_REPORT_TIME} (ម៉ោងនៅកម្ពុជា)")
    print("📡 កំពុងរង់ចាំ និងស្តាប់សារពីប្រព័ន្ធ KHQR...")

    # Auto sync past messages on startup in background (so bot doesn't miss prior transactions)
    if config.SYNC_ON_STARTUP and config.MONITOR_CHAT_ID:
        print("🔄 កំពុងទាញយកសារចាស់ៗក្នុង Group មកពិនិត្យដោយស្វ័យប្រវត្ត (Auto History Sync)...")
        from sync_history import sync_previous_messages
        asyncio.create_task(sync_previous_messages(client, config.MONITOR_CHAT_ID, limit=config.SYNC_LIMIT))

    # Start Cloud Health-check HTTP server if running on Render / Koyeb / Heroku (PORT env var present)
    await start_health_check_server()

    # Run until disconnected
    await client.run_until_disconnected()


async def start_health_check_server():
    """Lightweight HTTP server for cloud platforms (Render, Koyeb) to keep service healthy and awake."""
    port_str = os.environ.get("PORT")
    if not port_str:
        return None

    try:
        port = int(port_str)
        async def handle_client(reader, writer):
            try:
                await reader.read(1024)
                resp = (
                    "HTTP/1.1 200 OK\r\n"
                    "Content-Type: application/json; charset=utf-8\r\n"
                    "Connection: close\r\n\r\n"
                    '{"status":"ok","service":"KHQR Telegram Bot"}'
                )
                writer.write(resp.encode("utf-8"))
                await writer.drain()
            except Exception:
                pass
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_server(handle_client, "0.0.0.0", port)
        logger.info(f"Cloud health-check server running on port {port}")
        return server
    except Exception as e:
        logger.warning(f"Could not start health check server: {e}")
        return None

