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
import time
from zoneinfo import ZoneInfo
from typing import Optional, Any, cast, Awaitable, Dict

# Ensure UTF-8 output on Windows terminals
if sys.platform == "win32":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

from telethon import TelegramClient, events, Button
from telethon.errors import FloodWaitError, MessageNotModifiedError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import config
from database import Database, CAMBODIA_TZ, get_cambodia_now, get_cambodia_today_str
from parser import KHQRParser
from reporter import (
    format_daily_summary,
    format_yearly_summary,
    format_monthly_summary,
    format_range_summary,
    format_transaction_alert,
    format_currency,
    format_recent_transactions
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
            Button.inline("📆 ប្រចាំឆ្នាំ", data=b"btn_year"),
            Button.inline("❌ Exit", data=b"btn_exit"),
        ]
    ]


async def send_daily_summary(client: TelegramClient, target_chat_id: Optional[Any] = None):
    """Generates and sends the daily summary report to the target chat with sales comparison."""
    chat_id = target_chat_id or config.REPORT_CHAT_ID or config.MONITOR_CHAT_ID
    if not chat_id:
        logger.warning("No REPORT_CHAT_ID or MONITOR_CHAT_ID configured. Cannot send daily summary.")
        return

    today_str = get_cambodia_today_str()
    summary = db.get_summary_by_date(today_str)
    comparison = db.get_daily_comparison(today_str)
    message_text = format_daily_summary(summary, comparison=comparison, title_prefix="ប្រចាំថ្ងៃ")

    try:
        await client.send_message(chat_id, message_text, parse_mode="html", buttons=get_menu_buttons())
        logger.info(f"Daily summary successfully sent for {today_str} to {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send daily summary to {chat_id}: {e}")


# Cache for pending access requests and debouncing notifications
pending_requests: Dict[int, dict] = {}
last_request_time: Dict[int, float] = {}
last_callback_time: Dict[str, float] = {}
last_command_time: Dict[str, float] = {}


async def safe_edit_or_respond(event, text: str, buttons=None):
    """
    Safely updates the existing message in-place to prevent flooding the group with new messages.
    Falls back to respond if editing is not possible, and gracefully ignores MessageNotModified.
    Safely catches Telegram FloodWait.
    """
    try:
        if hasattr(event, 'edit'):
            try:
                await event.edit(text, parse_mode="html", buttons=buttons)
                return
            except MessageNotModifiedError:
                await event.answer("👌 ទិន្នន័យនេះកំពុងបង្ហាញស្រាប់ហើយ", alert=False)
                return
            except Exception as e:
                err_str = str(e).lower()
                if "not modified" in err_str:
                    await event.answer("👌 ទិន្នន័យនេះកំពុងបង្ហាញស្រាប់ហើយ", alert=False)
                    return
                logger.debug(f"event.edit failed, falling back to respond: {e}")

        await event.respond(text, parse_mode="html", buttons=buttons)
    except FloodWaitError as e:
        logger.warning(f"Telegram FloodWait triggered! Wait required: {e.seconds}s")
        if hasattr(event, 'answer'):
            await event.answer(f"⏳ សូមរង់ចាំ {e.seconds} វិនាទី...", alert=True)
    except Exception as e:
        logger.error(f"Error in safe_edit_or_respond: {e}")


async def safe_reply(event, text: str, buttons=None):
    """
    Safely replies to a message, catching Telegram FloodWait and transient errors.
    """
    try:
        return await event.reply(text, parse_mode="html", buttons=buttons)
    except FloodWaitError as e:
        logger.warning(f"Telegram FloodWait on reply: {e.seconds}s")
        await asyncio.sleep(min(e.seconds, 5))
    except Exception as e:
        logger.error(f"Error in safe_reply: {e}")



def check_permission(sender_id: Optional[Any], chat_id: Optional[int] = None) -> bool:
    """
    Checks if a user is permitted to view financial reports.
    Strictly enforced: Only Bot Owner(s) (Avata / ADMIN_USER_IDS) and staff explicitly approved
    in SQLite database (db.is_user_authorized) are allowed to view reports.
    Even the Group Owner or Group Admins MUST be approved by the Bot Owner (Avata) first.
    """
    if sender_id is None:
        return False
    try:
        s_id = int(sender_id)
    except (ValueError, TypeError):
        return False
    if s_id <= 0:
        return False
    # 1. Master Bot Owner Avata (7299682335) has permanent Super Admin rights
    if s_id == config.MASTER_BOT_OWNER_ID:
        return True
    if not config.RESTRICT_REPORTS_TO_ADMIN:
        return True
    if config.ADMIN_USER_IDS and s_id in config.ADMIN_USER_IDS:
        return True
    return db.is_user_authorized(s_id, chat_id)


def is_admin(sender_id: Optional[Any], chat_id: Optional[int] = None) -> bool:
    """
    Checks if a user has full Bot Owner privileges (Avata / ADMIN_USER_IDS).
    Group Owners or Group Admins do NOT have admin rights over this bot.
    Only the Bot Owner can approve/deny access requests or manage authorized staff.
    """
    if sender_id is None:
        return False
    try:
        s_id = int(sender_id)
    except (ValueError, TypeError):
        return False
    if s_id <= 0:
        return False
    # 1. Master Bot Owner Avata (7299682335) has permanent Super Admin rights
    if s_id == config.MASTER_BOT_OWNER_ID:
        return True
    # 2. Configured admin user IDs from environment
    if config.ADMIN_USER_IDS and s_id in config.ADMIN_USER_IDS:
        return True
    # 3. Database stored owner/admin role
    role = db.get_user_role(s_id, chat_id)
    if role in ("owner", "admin"):
        return True
    return False


async def get_user_group_role(client: TelegramClient, chat_id: int, user_id: int) -> str:
    """Determines whether a user is the owner, admin, or regular member in that group."""
    try:
        perms = await client.get_permissions(chat_id, user_id)
        if perms.is_creator:
            return "owner"
        elif perms.is_admin:
            return "admin"
        else:
            return "សមាជិក"
    except Exception:
        return "សមាជិក"


async def notify_owner_of_access_request(
    client: TelegramClient,
    user_id: int,
    chat_id: int,
    user_entity: Optional[Any] = None,
    source: str = "command",
    group_role: Optional[str] = None
):
    """
    Sends an immediate direct message to Bot Owner(s) when an unauthorized member
    requests access or attempts to view reports, with 1-click [Approve] / [Deny] buttons.
    Organized strictly by group with user's role confirmation (owner, admin, or member).
    """
    now = time.time()
    # Debounce: don't spam owner if clicked repeatedly within 30 seconds
    if user_id in last_request_time and (now - last_request_time[user_id]) < 30:
        return

    last_request_time[user_id] = now

    # Determine user's role in the group if not already provided
    if not group_role:
        group_role = await get_user_group_role(client, chat_id, user_id)

    # Extract user details robustly
    full_name = "User"
    username_str = "គ្មាន Username"
    if user_entity:
        first = getattr(user_entity, "first_name", "") or ""
        last = getattr(user_entity, "last_name", "") or ""
        full_name = f"{first} {last}".strip()
        uname = getattr(user_entity, "username", None)
        if uname:
            username_str = f"@{uname}"
    if not full_name or full_name == "User":
        try:
            ent = await client.get_entity(user_id)
            first = getattr(ent, "first_name", "") or ""
            last = getattr(ent, "last_name", "") or ""
            full_name = f"{first} {last}".strip() or f"User {user_id}"
            uname = getattr(ent, "username", None)
            if uname:
                username_str = f"@{uname}"
        except Exception:
            full_name = f"User {user_id}"

    # Extract chat title
    chat_title = "Meeting cafe ☕"
    try:
        chat_ent = await client.get_entity(chat_id)
        chat_title = getattr(chat_ent, "title", "Group") or "Meeting cafe ☕"
    except Exception:
        pass

    # Save to memory cache organized by group and role
    pending_requests[user_id] = {
        "user_id": user_id,
        "full_name": full_name,
        "username": username_str,
        "chat_id": chat_id,
        "chat_title": chat_title,
        "group_role": group_role,
    }

    current_time_str = get_cambodia_now().strftime("%Y-%m-%d %H:%M:%S")

    alert_msg = (
        "🔔 <b>មានសំណើសុំសិទ្ធិមើលរបាយការណ៍ហិរញ្ញវត្ថុថ្មី!</b>\n\n"
        f"👥 <b>មកពី Group:</b> {chat_title}\n"
        f"👤 <b>ឈ្មោះ:</b> {full_name} ({group_role})\n"
        f"🏷️ <b>Username:</b> {username_str}\n"
        f"🔢 <b>Telegram User ID:</b> <code>{user_id}</code>\n"
        f"⏰ <b>ម៉ោង:</b> {current_time_str}\n\n"
        "👉 <i>តើលោកអ្នក (Avata) យល់ព្រមអនុញ្ញាតឱ្យគណនីនេះមើលរបាយការណ៍លក់ក្នុង Group នេះដែរឬទេ?</i>"
    )

    approval_buttons = [
        [
            Button.inline("✅ អនុញ្ញាត (Approve)", data=f"appr_{user_id}".encode()),
            Button.inline("❌ មិនអនុញ្ញាត (Not Approve)", data=f"deny_{user_id}".encode()),
        ],
        [
            Button.inline(f"👥 គ្រប់គ្រងសមាជិក Group {chat_title[:12]}", data=f"mgm_grp_{chat_title[:20]}".encode()),
            Button.inline("👑 Admin Panel", data=b"admin_panel")
        ]
    ]

    for admin_id in config.ADMIN_USER_IDS:
        try:
            await client.send_message(admin_id, alert_msg, parse_mode="html", buttons=approval_buttons)
            logger.info(f"Forwarded access request for User {user_id} ({full_name}) from {chat_title} to Owner {admin_id}")
        except Exception as e:
            logger.warning(f"Could not send DM to Owner {admin_id}: {e}")


def get_owner_reply_keyboard():
    """Persistent keyboard docked at the bottom of the chat for Bot Owner (Avata)."""
    return [
        [
            Button.text("👥 គ្រប់គ្រង Group", resize=True),
            Button.text("📊 របាយការណ៍លក់", resize=True)
        ],
        [
            Button.text("👑 Admin Panel", resize=True),
            Button.text("ℹ️ ស្ថានភាព / Version", resize=True)
        ]
    ]


def build_admin_panel():
    """Constructs the Master Admin Control Panel for Bot Owner (Avata)."""
    total_tx = db.get_transaction_count()
    users_count = len(db.list_authorized_users())
    groups = db.list_groups_summary()
    uptime_str = get_cambodia_now().strftime("%Y-%m-%d %H:%M:%S")

    text = (
        "👑 <b>ផ្ទាំងបញ្ជាគ្រប់គ្រងមេ (Bot Owner Control Center)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 <b>ម្ចាស់ Bot:</b> <b>AVATA 🇸🇸</b> (<code>{config.MASTER_BOT_OWNER_ID}</code>)\n"
        f"🏷️ <b>Version:</b> <code>v{config.BOT_VERSION}</code> (Enterprise Edition)\n"
        f"🛡️ <b>ប្រព័ន្ធសុវត្ថិភាព:</b> <code>Strict Bot Owner RBAC (Active)</code>\n"
        f"📊 <b>ប្រតិបត្តិការក្នុង DB:</b> <code>{total_tx} លើក</code>\n"
        f"👥 <b>បុគ្គលិកមានសិទ្ធិសរុប:</b> <code>{users_count} នាក់</code>\n"
        f"🏢 <b>ចំនួន Group មានទិន្នន័យ:</b> <code>{len(groups)} Groups</code>\n"
        f"⏰ <b>ម៉ោងប្រព័ន្ធបច្ចុប្បន្ន:</b> <code>{uptime_str}</code>\n\n"
        "👇 <b>សូមចុចលើប៊ូតុងខាងក្រោមដើម្បីគ្រប់គ្រងការងារ៖</b>"
    )
    buttons = [
        [
            Button.inline("👥 គ្រប់គ្រងសមាជិកតាម Group", data=b"admin_groups"),
            Button.inline("📊 មើលរបាយការណ៍លក់", data=b"btn_today"),
        ],
        [
            Button.inline("📋 បញ្ជីបុគ្គលិកទាំងអស់", data=b"admin_all_users"),
            Button.inline("🧹 Clear សិទ្ធិទាំងអស់", data=b"admin_confirm_clear"),
        ],
        [
            Button.inline("🚀 Update & Restart Bot", data=b"admin_trigger_update"),
            Button.inline("ℹ️ ស្ថានភាព / Version", data=b"admin_status"),
        ],
        [
            Button.inline("🔄 Sync សារចាស់ៗ", data=b"admin_sync_menu"),
            Button.inline("❌ បិទផ្ទាំង (Close)", data=b"mgm_close")
        ]
    ]
    return text, buttons


def build_group_selector():
    """Builds interactive group selection buttons for Bot Owner."""
    summaries = db.list_groups_summary()
    btn_rows = []
    seen = set()

    for s in summaries:
        c_title = s.get("chat_title") or f"Group {s['chat_id']}"
        seen.add(c_title.strip().lower())
        cnt = s.get("member_count", 0)
        btn_rows.append([Button.inline(f"👥 {c_title} ({cnt} នាក់)", data=f"mgm_grp_{c_title[:20]}".encode())])

    # Always ensure Meeting cafe ☕ is available
    if "meeting cafe ☕".lower() not in seen and "meeting cafe".lower() not in seen:
        btn_rows.insert(0, [Button.inline("👥 Meeting cafe ☕", data=b"mgm_grp_Meeting cafe")])

    btn_rows.append([
        Button.inline("👑 ត្រឡប់ទៅ Admin Panel", data=b"admin_panel"),
        Button.inline("❌ បិទ (Close)", data=b"mgm_close")
    ])

    text = (
        "👑 <b>ផ្ទាំងគ្រប់គ្រងសមាជិកតាម Group (Bot Owner Panel)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "សូមជ្រើសរើស Group ដែលលោកអ្នក (Avata) ចង់គ្រប់គ្រងសមាជិក៖"
    )
    return text, btn_rows


def build_group_management_panel(group_query: str):
    """
    Constructs an interactive group member management view with numbered list and numbered buttons.
    Exclusively used by Bot Owner (Avata).
    """
    members = db.list_authorized_users_by_group(group_query)
    title = group_query or "Meeting cafe ☕"
    chat_id_val = 0
    if members:
        title = members[0].get("chat_title") or title
        chat_id_val = members[0].get("chat_id", 0)

    if not members:
        text = (
            f"👥 <b>ផ្ទាំងគ្រប់គ្រង Group:</b> <code>{title}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<i>មិនទាន់មានសមាជិកណាត្រូវបានអនុញ្ញាតក្នុង Group នេះនៅឡើយទេ។</i>\n\n"
            f"💡 <i>រាល់ពេលមានអ្នកចុចមើលរបាយការណ៍ នឹងមានសារ Alert មកកាន់ Avata ដើម្បី Approve។</i>"
        )
        buttons = [
            [
                Button.inline("🔄 Refresh", data=f"mgm_grp_{title[:20]}".encode()),
                Button.inline("🔙 រើស Group ផ្សេង", data=b"admin_groups")
            ],
            [
                Button.inline("👑 Admin Panel", data=b"admin_panel"),
                Button.inline("❌ បិទ (Close)", data=b"mgm_close")
            ]
        ]
        return text, buttons

    lines = [
        f"👥 <b>បញ្ជីសមាជិកមានសិទ្ធិក្នុង Group:</b> <code>{title}</code>",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    ]

    num_buttons = []
    current_row = []

    for idx, m in enumerate(members, start=1):
        name = m.get("full_name") or m.get("username") or f"User {m['user_id']}"
        g_role = m.get("group_role") or "សមាជិក"
        uname = f"@{m['username']} " if m.get("username") else ""
        c_id = m.get("chat_id") or chat_id_val
        lines.append(f"<b>{idx}.</b> <b>{name}</b> ({g_role}) — {uname}[<code>{m['user_id']}</code>]")

        btn_data = f"mgm_pick_{c_id}_{m['user_id']}".encode()
        current_row.append(Button.inline(f" {idx} ", data=btn_data))
        if len(current_row) == 5:
            num_buttons.append(current_row)
            current_row = []

    if current_row:
        num_buttons.append(current_row)

    lines.append("\n👇 <b>សូមចុចលើលេខរៀងខាងក្រោម ដើម្បីលុប ឬរក្សាទុកសិទ្ធិ៖</b>")
    num_buttons.append([
        Button.inline("🔄 Refresh", data=f"mgm_grp_{title[:20]}".encode()),
        Button.inline("🔙 រើស Group ផ្សេង", data=b"admin_groups")
    ])
    num_buttons.append([
        Button.inline("👑 Admin Panel", data=b"admin_panel"),
        Button.inline("❌ បិទ (Close)", data=b"mgm_close")
    ])
    return "\n".join(lines), num_buttons


def restart_process():
    """Performs clean process restart, replacing the current process or exiting cleanly."""
    logger.info("Executing clean process restart...")
    try:
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        logger.warning(f"os.execv failed ({e}), falling back to os._exit(0)")
        os._exit(0)


def setup_handlers(client: TelegramClient):
    """Sets up event handlers for incoming messages, commands, and button clicks."""

    # 1. Callback query handler for inline button taps
    async def _process_callback(event: events.CallbackQuery.Event):
        sender_id = event.sender_id
        data = event.data

        # Debounce rapid button taps from same user/button within 1.5 seconds
        cb_key = f"{sender_id}_{data}"
        now_ts = time.time()
        if cb_key in last_callback_time and (now_ts - last_callback_time[cb_key]) < 1.5:
            await event.answer()
            return
        last_callback_time[cb_key] = now_ts

        # Handle Owner Approval / Denial buttons in Owner's private chat
        if data.startswith(b"appr_"):
            if not is_admin(sender_id, event.chat_id):
                await event.answer("⛔ មានតែម្ចាស់អាជីវកម្ម (Owner) ប៉ុណ្ណោះដែលអាច Approve បាន!", alert=True)
                return

            target_id = int(data.decode().split("_")[1])
            req_info = pending_requests.get(target_id, {})
            target_name = req_info.get("full_name") or f"User {target_id}"
            target_uname = req_info.get("username")
            if target_uname and target_uname.startswith("@"):
                target_uname = target_uname[1:]
            chat_id = req_info.get("chat_id") or config.MONITOR_CHAT_ID or 0
            chat_title = req_info.get("chat_title") or "Meeting cafe ☕"
            group_role = req_info.get("group_role") or "សមាជិក"

            # Add to authorized database per group
            db.add_authorized_user(
                user_id=target_id,
                username=target_uname,
                full_name=target_name,
                role="staff",
                chat_id=chat_id,
                chat_title=chat_title,
                group_role=group_role,
                added_by=sender_id
            )

            now_str = get_cambodia_now().strftime("%Y-%m-%d %H:%M:%S")
            approved_text = (
                "✅ <b>បានអនុញ្ញាតសិទ្ធិដោយជោគជ័យ! (Approved)</b>\n\n"
                f"👥 Group: <b>{chat_title}</b>\n"
                f"👤 បុគ្គលិក: <b>{target_name} ({group_role})</b> (<code>{target_id}</code>)\n"
                f"🛡️ តួនាទី: <b>STAFF (បុគ្គលិកមានសិទ្ធិ)</b>\n"
                f"⏰ ម៉ោងអនុម័ត: <b>{now_str}</b>\n"
                f"👑 អនុម័តដោយម្ចាស់ Bot: <b>AVATA 🇸🇸</b>\n\n"
                f"<i>បុគ្គលិកនេះអាចមើលរបាយការណ៍ហិរញ្ញវត្ថុក្នុង Group {chat_title} បានហើយ។</i>"
            )
            await event.edit(approved_text, parse_mode="html")
            await event.answer("✅ បានអនុម័តជោគជ័យ (Approved)!")

            # Announce in the group chat so staff knows immediately
            notify_chat = req_info.get("chat_id") or config.MONITOR_CHAT_ID
            if notify_chat:
                try:
                    await client.send_message(
                        notify_chat,
                        f"🎉 <b>ការស្នើសុំសិទ្ធិត្រូវបានអនុម័ត! (Approved)</b>\n\n"
                        f"👤 <b>{target_name} ({group_role})</b> ត្រូវបានម្ចាស់ Bot (Avata) អនុញ្ញាតឱ្យមើលរបាយការណ៍ហិរញ្ញវត្ថុក្នុង Group នេះបានហើយ។\n\n"
                        f"👉 លោកអ្នកអាចចុច <code>/today</code> ឬប៊ូតុងខាងក្រោមដើម្បីពិនិត្យការលក់:",
                        parse_mode="html",
                        buttons=get_menu_buttons()
                    )
                except Exception as e:
                    logger.warning(f"Could not announce approval in group: {e}")
            return

        elif data.startswith(b"deny_"):
            if not is_admin(sender_id, event.chat_id):
                await event.answer("⛔ មានតែម្ចាស់អាជីវកម្មប៉ុណ្ណោះដែលអាចបដិសេធបាន!", alert=True)
                return

            target_id = int(data.decode().split("_")[1])
            req_info = pending_requests.get(target_id, {})
            target_name = req_info.get("full_name") or f"User {target_id}"

            denied_text = (
                f"❌ <b>មិនអនុញ្ញាត (Not Approved)</b>\n\n"
                f"បុគ្គលិក <b>{target_name}</b> (<code>{target_id}</code>) មិនត្រូវបានអនុញ្ញាតឱ្យមើលរបាយការណ៍ឡើយ។"
            )
            await event.edit(denied_text, parse_mode="html")
            await event.answer("❌ មិនអនុញ្ញាត (Not Approved)!")
            return

        # Handle Group Member Management Callbacks (Avata Bot Owner only)
        elif data.startswith(b"mgm_"):
            if not is_admin(sender_id, event.chat_id):
                await event.answer("⛔ មុខងារនេះសម្រាប់តែម្ចាស់ Bot (Avata) ប៉ុណ្ណោះ!", alert=True)
                return

            if data == b"mgm_close":
                await event.delete()
                return

            elif data.startswith(b"mgm_grp_"):
                grp_q = data[8:].decode("utf-8", errors="ignore")
                text_panel, buttons_panel = build_group_management_panel(grp_q)
                await event.edit(text_panel, parse_mode="html", buttons=buttons_panel)
                return

            elif data.startswith(b"mgm_pick_"):
                parts = data.decode("utf-8").split("_")
                if len(parts) >= 4:
                    c_id = int(parts[2])
                    u_id = int(parts[3])
                    u_info = db.get_authorized_user_by_id(u_id, c_id)
                    if not u_info:
                        await event.answer("⚠️ រកមិនឃើញគណនីនេះក្នុងបញ្ជីឡើយ!", alert=True)
                        return

                    u_name = u_info.get("full_name") or f"User {u_id}"
                    g_role = u_info.get("group_role") or "សមាជិក"
                    c_title = u_info.get("chat_title") or f"Group {c_id}"
                    uname = f"@{u_info['username']}" if u_info.get("username") else "គ្មាន Username"

                    confirm_text = (
                        "⚠️ <b>បញ្ជាក់ការគ្រប់គ្រងសិទ្ធិ (Permission Action)</b>\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"👥 <b>Group:</b> {c_title}\n"
                        f"👤 <b>ឈ្មោះគណនី:</b> <b>{u_name} ({g_role})</b>\n"
                        f"🏷️ <b>Username:</b> {uname}\n"
                        f"🔢 <b>Telegram User ID:</b> <code>{u_id}</code>\n\n"
                        "👉 <i>តើលោកអ្នក (Avata) ចង់ «លុបសិទ្ធិ» ឬ «រក្សាទុក» គណនីនេះ?</i>"
                    )
                    confirm_buttons = [
                        [
                            Button.inline("🗑️ លុប (Delete)", data=f"mgm_del_{c_id}_{u_id}".encode()),
                            Button.inline("💾 រក្សាទុក (Keep)", data=f"mgm_keep_{c_title[:20]}".encode()),
                        ]
                    ]
                    await event.edit(confirm_text, parse_mode="html", buttons=confirm_buttons)
                    return

            elif data.startswith(b"mgm_del_"):
                parts = data.decode("utf-8").split("_")
                if len(parts) >= 4:
                    c_id = int(parts[2])
                    u_id = int(parts[3])
                    u_info = db.get_authorized_user_by_id(u_id, c_id)
                    u_name = (u_info.get("full_name") if u_info else "") or f"ID {u_id}"
                    c_title = (u_info.get("chat_title") if u_info else "") or "Meeting cafe ☕"

                    db.remove_authorized_user(u_id, c_id)
                    await event.answer(f"🗑️ បានលុបសិទ្ធិរបស់ {u_name} រួចរាល់!", alert=True)

                    # Return to updated numbered list
                    text_panel, buttons_panel = build_group_management_panel(c_title)
                    await event.edit(text_panel, parse_mode="html", buttons=buttons_panel)
                    return

            elif data.startswith(b"mgm_keep_"):
                c_title = data[9:].decode("utf-8", errors="ignore")
                await event.answer("👌 បានរក្សាទុកសិទ្ធិដដែល", alert=False)
                text_panel, buttons_panel = build_group_management_panel(c_title)
                await event.edit(text_panel, parse_mode="html", buttons=buttons_panel)
                return

        # Master Admin Control Panel Callbacks (Bot Owner Avata only)
        if data == b"admin_panel":
            if not is_admin(sender_id, event.chat_id):
                await event.answer("⛔ មុខងារនេះសម្រាប់តែម្ចាស់ Bot (Avata) ប៉ុណ្ណោះ!", alert=True)
                return
            t, b = build_admin_panel()
            await event.edit(t, parse_mode="html", buttons=b)
            return

        elif data == b"admin_groups":
            if not is_admin(sender_id, event.chat_id):
                await event.answer("⛔ មុខងារនេះសម្រាប់តែម្ចាស់ Bot (Avata) ប៉ុណ្ណោះ!", alert=True)
                return
            t, b = build_group_selector()
            await event.edit(t, parse_mode="html", buttons=b)
            return

        elif data == b"admin_all_users":
            if not is_admin(sender_id, event.chat_id):
                await event.answer("⛔ មុខងារនេះសម្រាប់តែម្ចាស់ Bot (Avata) ប៉ុណ្ណោះ!", alert=True)
                return
            users = db.list_authorized_users()
            lines = [
                "📋 <b>បញ្ជីបុគ្គលិកមានសិទ្ធិទាំងអស់ក្នុងប្រព័ន្ធ:</b>",
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            ]
            if not users:
                lines.append("<i>មិនទាន់មានបុគ្គលិកណាមានសិទ្ធិឡើយ។</i>")
            else:
                for idx, u in enumerate(users, start=1):
                    name = u.get("full_name") or u.get("username") or f"User {u['user_id']}"
                    role = u.get("role", "staff").upper()
                    g_title = u.get("chat_title") or "ទូទៅ"
                    g_role = u.get("group_role") or "សមាជិក"
                    lines.append(f"<b>{idx}.</b> 👤 <b>{name}</b> ({g_role}) — [<code>{u['user_id']}</code>]\n   └ 🏢 <i>{g_title}</i> | តួនាទី: <b>{role}</b>")

            b = [
                [Button.inline("🔙 ត្រឡប់ទៅ Admin Panel", data=b"admin_panel")],
                [Button.inline("❌ បិទ (Close)", data=b"mgm_close")]
            ]
            await event.edit("\n".join(lines), parse_mode="html", buttons=b)
            return

        elif data == b"admin_confirm_clear":
            if not is_admin(sender_id, event.chat_id):
                await event.answer("⛔ មុខងារនេះសម្រាប់តែម្ចាស់ Bot (Avata) ប៉ុណ្ណោះ!", alert=True)
                return
            clear_text = (
                "⚠️ <b>ការបញ្ជាក់៖ សម្អាត (Clear) សិទ្ធិបុគ្គលិកទាំងអស់</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "តើលោកអ្នក (Avata) ពិតជាចង់ Clear សិទ្ធិបុគ្គលិកទាំងអស់ចេញពីគ្រប់ Group មែនទេ?\n\n"
                "🛡️ <i>ចំណាំ៖ ម្ចាស់ Bot (Avata ID: 7299682335) នៅតែរក្សាសិទ្ធិពេញលេញជានិច្ច។</i>"
            )
            b = [
                [
                    Button.inline("⚠️ បញ្ជាក់ការ Clear ទាំងអស់", data=b"admin_do_clear"),
                    Button.inline("🔙 ថយក្រោយ", data=b"admin_panel")
                ]
            ]
            await event.edit(clear_text, parse_mode="html", buttons=b)
            return

        elif data == b"admin_do_clear":
            if not is_admin(sender_id, event.chat_id):
                await event.answer("⛔ មុខងារនេះសម្រាប់តែម្ចាស់ Bot (Avata) ប៉ុណ្ណោះ!", alert=True)
                return
            del_cnt = db.clear_authorized_users(keep_admin_ids=[config.MASTER_BOT_OWNER_ID])
            res_text = (
                f"🧹 <b>បានសម្អាត (Clear) សិទ្ធិបុគ្គលិកចំនួន {del_cnt} នាក់ជោគជ័យ!</b>\n\n"
                "👑 បច្ចុប្បន្នមានតែម្ចាស់ Bot (Avata) មួយគត់ដែលអាចចូលមើលរបាយការណ៍បាន។"
            )
            b = [
                [Button.inline("🔙 ត្រឡប់ទៅ Admin Panel", data=b"admin_panel")]
            ]
            await event.edit(res_text, parse_mode="html", buttons=b)
            await event.answer("🧹 Clear សិទ្ធិជោគជ័យ!")
        elif data == b"admin_trigger_update":
            if not is_admin(sender_id, event.chat_id):
                await event.answer("⛔ មុខងារនេះសម្រាប់តែម្ចាស់ Bot (Avata) ប៉ុណ្ណោះ!", alert=True)
                return

            update_text = (
                "🚀 <b>ផ្ទាំងគ្រប់គ្រង Version & Update (Auto-Deploy Control)</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🏷️ <b>Version បច្ចុប្បន្ន:</b> <code>v{config.BOT_VERSION}</code> (Ultra-Stable)\n"
                f"👑 <b>ម្ចាស់ Bot:</b> <b>AVATA 🇸🇸</b>\n\n"
                "👉 <i>សូមជ្រើសរើសជម្រើសខាងក្រោម៖</i>\n\n"
                "• <b>⚡ Auto Pull & Restart:</b> ទាញយកកូដថ្មីពី GitHub និង Restart ស្វ័យប្រវត្តភ្លាមៗ\n"
                "• <b>☁️ Render Auto-Deploy:</b> បញ្ជាឱ្យប្រព័ន្ធ Render Build & Deploy ជំនាន់ថ្មី\n"
                "• <b>🔄 Quick Restart:</b> Restart Bot ភ្លាមៗដើម្បី Refresh ប្រព័ន្ធ\n"
            )
            b = [
                [Button.inline("⚡ Auto Pull & Restart (Git)", data=b"admin_do_git_update")],
                [Button.inline("☁️ Render Auto-Deploy", data=b"admin_do_render_deploy")],
                [Button.inline("🔄 Quick Restart ភ្លាមៗ", data=b"admin_do_restart")],
                [Button.inline("🔙 ត្រឡប់ទៅ Admin Panel", data=b"admin_panel")]
            ]
            await event.edit(update_text, parse_mode="html", buttons=b)
            return

        elif data == b"admin_do_git_update":
            if not is_admin(sender_id, event.chat_id):
                await event.answer("⛔ មុខងារនេះសម្រាប់តែម្ចាស់ Bot (Avata) ប៉ុណ្ណោះ!", alert=True)
                return

            await event.answer("⏳ កំពុងទាញយក Version ថ្មីពី GitHub...", alert=False)
            await event.edit(
                "⏳ <b>កំពុងដំណើរការទាញយកកូដ Version ថ្មីពី GitHub (Git Pull)...</b>\n\n"
                "<i>សូមរង់ចាំបន្តិច...</i>",
                parse_mode="html"
            )

            pull_output = ""
            try:
                proc = await asyncio.create_subprocess_exec(
                    "git", "pull", "origin", "main",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                pull_output = (stdout.decode(errors="ignore") + stderr.decode(errors="ignore")).strip()
            except Exception as e:
                pull_output = f"Git error: {e}"

            done_msg = (
                "✅ <b>បានទាញយក Version ថ្មីពី GitHub រួចរាល់!</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📋 <b>លទ្ធផល Git Pull:</b>\n<code>{pull_output[:300] or 'Already up to date.'}</code>\n\n"
                "🔄 <b>ប្រព័ន្ធកំពុង Restart ស្វ័យប្រវត្តក្នុងរយៈពេល ២ វិនាទី...</b>\n"
                "💡 <i>(Bot នឹងផ្ញើសារ Alert មកកាន់បងវិញនៅពេលដំណើរការឡើងវិញរួចរាល់)</i>"
            )
            await event.edit(done_msg, parse_mode="html")
            asyncio.get_event_loop().call_later(2.0, restart_process)
            return

        elif data == b"admin_do_render_deploy":
            if not is_admin(sender_id, event.chat_id):
                await event.answer("⛔ មុខងារនេះសម្រាប់តែម្ចាស់ Bot (Avata) ប៉ុណ្ណោះ!", alert=True)
                return

            hook_url = getattr(config, "RENDER_DEPLOY_HOOK", "")
            if hook_url and hook_url.startswith("http"):
                try:
                    import urllib.request
                    req = urllib.request.Request(hook_url, data=b"", method="POST")
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        logger.info(f"Triggered Render deploy hook: status {resp.status}")

                    deploy_text = (
                        "🚀 <b>បានបញ្ជា Render ឱ្យ Re-deploy ជោគជ័យ!</b>\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        "📡 ប្រព័ន្ធ Render កំពុង Build និងទាញយក Version ថ្មីមកដំណើរការ...\n"
                        "⏳ រយៈពេល Build ជាមធ្យម: <b>1 ទៅ 2 នាទី</b>\n\n"
                        "✅ <i>នៅពេល Build ចប់ Bot ថ្មីនឹងបើកដំណើរការ និងផ្ញើសារមកកាន់បងដោយស្វ័យប្រវត្ត!</i>"
                    )
                    b = [[Button.inline("🔙 ត្រឡប់ទៅ Admin Panel", data=b"admin_panel")]]
                    await event.edit(deploy_text, parse_mode="html", buttons=b)
                    await event.answer("🚀 បានបញ្ជា Render Deploy ជោគជ័យ!")
                    return
                except Exception as e:
                    logger.error(f"Render deploy hook failed: {e}")
                    await event.answer(f"⚠️ មិនអាចបញ្ជា Deploy បាន: {e}", alert=True)
                    return
            else:
                no_hook_text = (
                    "⚠️ <b>មិនទាន់បានកំណត់ RENDER_DEPLOY_HOOK ក្នុង .env នៅឡើយទេ</b>\n\n"
                    "💡 លោកអ្នកអាចប្រើប៊ូតុង <b>⚡ Auto Pull & Restart</b> ឬ <b>🔄 Quick Restart</b> ជំនួសវិញបាន។"
                )
                b = [
                    [Button.inline("⚡ Auto Pull & Restart", data=b"admin_do_git_update")],
                    [Button.inline("🔄 Quick Restart", data=b"admin_do_restart")],
                    [Button.inline("🔙 ត្រឡប់ទៅ Admin Panel", data=b"admin_panel")]
                ]
                await event.edit(no_hook_text, parse_mode="html", buttons=b)
                return

        elif data == b"admin_do_restart":
            if not is_admin(sender_id, event.chat_id):
                await event.answer("⛔ មុខងារនេះសម្រាប់តែម្ចាស់ Bot (Avata) ប៉ុណ្ណោះ!", alert=True)
                return

            await event.answer("🔄 កំពុង Restart Bot...", alert=True)
            await event.edit(
                "🔄 <b>ប្រព័ន្ធកំពុងដំណើរការ Restart ស្វ័យប្រវត្ត...</b>\n\n"
                "⏳ សូមរង់ចាំប្រហែល ១៥ ទៅ ៣០ វិនាទី។ Bot នឹងផ្ញើសារ Alert មកវិញនៅពេលដំណើរការរួចរាល់!",
                parse_mode="html"
            )
            asyncio.get_event_loop().call_later(1.0, restart_process)
            return

        elif data == b"admin_status":
            uptime_str = get_cambodia_now().strftime("%Y-%m-%d %H:%M:%S")
            total_tx = db.get_transaction_count()
            users_count = len(db.list_authorized_users())
            status_text = (
                f"🤖 <b>ប្រព័ន្ធ KHQR Daily Report Bot</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏷️ <b>Version:</b> <code>v{config.BOT_VERSION}</code> (Enterprise Edition)\n"
                f"👑 <b>Bot Owner:</b> <code>AVATA 🇸🇸 (ID: {config.MASTER_BOT_OWNER_ID})</code>\n"
                f"🛡️ <b>ប្រព័ន្ធសុវត្ថិភាព:</b> <code>Strict Bot Owner RBAC (Active)</code>\n"
                f"📊 <b>ប្រតិបត្តិការសរុបក្នុង DB:</b> <code>{total_tx} លើក</code>\n"
                f"👥 <b>បុគ្គលិកមានសិទ្ធិ:</b> <code>{users_count} នាក់</code>\n"
                f"⏰ <b>ម៉ោងបច្ចុប្បន្ន:</b> <code>{uptime_str}</code>\n\n"
                f"✅ <i>ប្រព័ន្ធកំពុងដំណើរការកំណែចុងក្រោយបំផុតដោយជោគជ័យ។</i>"
            )
            b = [
                [Button.inline("🔙 ត្រឡប់ទៅ Admin Panel", data=b"admin_panel")],
                [Button.inline("❌ បិទ (Close)", data=b"mgm_close")]
            ]
            await event.edit(status_text, parse_mode="html", buttons=b)
            return

        elif data == b"admin_sync_menu":
            if not is_admin(sender_id, event.chat_id):
                await event.answer("⛔ មុខងារនេះសម្រាប់តែម្ចាស់ Bot (Avata) ប៉ុណ្ណោះ!", alert=True)
                return
            s_text = (
                "🔄 <b>ទាញយកសារចាស់ៗក្នុង Group (Auto History Sync)</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "សូមជ្រើសរើសចំនួនសារចាស់ៗដែលចង់ឱ្យ Bot ពិនិត្យរកប្រតិបត្តិការទូទាត់ KHQR៖"
            )
            b = [
                [
                    Button.inline("🔄 Sync 100 សារ", data=b"admin_do_sync_100"),
                    Button.inline("🔄 Sync 200 សារ", data=b"admin_do_sync_200"),
                ],
                [
                    Button.inline("🔙 ត្រឡប់ទៅ Admin Panel", data=b"admin_panel")
                ]
            ]
            await event.edit(s_text, parse_mode="html", buttons=b)
            return

        elif data in (b"admin_do_sync_100", b"admin_do_sync_200"):
            if not is_admin(sender_id, event.chat_id):
                await event.answer("⛔ មុខងារនេះសម្រាប់តែម្ចាស់ Bot (Avata) ប៉ុណ្ណោះ!", alert=True)
                return
            limit_val = 100 if data == b"admin_do_sync_100" else 200
            await event.edit(f"⏳ <b>កំពុងដំណើរការ Sync ទាញយកសារចាស់ៗចំនួន {limit_val} សារ... សូមរង់ចាំបន្តិច</b>", parse_mode="html")
            from sync_history import sync_previous_messages
            target_chat = config.MONITOR_CHAT_ID or event.chat_id
            res = await sync_previous_messages(client, target_chat, limit=limit_val)
            if res and not res.get("bot_restricted"):
                rep_t = (
                    "✅ <b>ការ Sync ទិន្នន័យចាស់ៗជោគជ័យ:</b>\n\n"
                    f"• សារបានពិនិត្យ: <b>{res['total_scanned']}</b>\n"
                    f"• ប្រតិបត្តិការថ្មី: <b>{res['new_added']}</b>\n"
                    f"• ទឹកប្រាក់ថ្មី: <b>${res['usd_total']:,.2f}</b> | <b>{int(res['khr_total']):,} ៛</b>"
                )
            else:
                rep_t = "👌 បានបញ្ចប់ការត្រួតពិនិត្យសារចាស់ៗក្នុង Group រួចរាល់។"
            b = [
                [Button.inline("🔙 ត្រឡប់ទៅ Admin Panel", data=b"admin_panel")]
            ]
            await event.edit(rep_t, parse_mode="html", buttons=b)
            return

        # Check permission for report inline buttons
        if not check_permission(sender_id, event.chat_id):
            if sender_id is not None and sender_id > 0:
                sender_ent = await event.get_sender()
                first = getattr(sender_ent, "first_name", "") or ""
                last = getattr(sender_ent, "last_name", "") or ""
                fname = f"{first} {last}".strip() or f"User {sender_id}"
                
                # Determine requester's role in the group
                g_role = await get_user_group_role(client, event.chat_id, sender_id)

                await notify_owner_of_access_request(
                    client=client,
                    user_id=sender_id,
                    chat_id=event.chat_id,
                    user_entity=sender_ent,
                    source="button",
                    group_role=g_role
                )
                await event.answer(
                    f"⛔ គ្មានសិទ្ធិមើលរបាយការណ៍!\n"
                    f"👤 ឈ្មោះ: {fname} ({g_role}) [ID: {sender_id}]\n"
                    f"📩 បានបញ្ជូនឈ្មោះ និង ID ទៅម្ចាស់ Bot (Avata) ដើម្បីសុំ Approve រួចហើយ!",
                    alert=True
                )
            else:
                await event.answer(
                    "⛔ ការចូលប្រើប្រាស់ត្រូវបានបដិសេធ!\n\n"
                    "⚠️ លោកអ្នកកំពុងបើក Send anonymously។ សូមបិទមុខងារនេះជាមុនសិន ទើបប្រព័ន្ធអាចចាប់យកឈ្មោះ និង Telegram ID របស់អ្នកសុំការ Approve បាន!",
                    alert=True
                )
            return

        if data == b"btn_today":
            today_str = get_cambodia_today_str()
            summary = db.get_summary_by_date(today_str)
            comparison = db.get_daily_comparison(today_str)
            msg = format_daily_summary(summary, comparison=comparison, title_prefix="ថ្ងៃនេះ (Today)")
            await safe_edit_or_respond(event, msg, buttons=get_menu_buttons())

        elif data == b"btn_yesterday":
            yesterday = (get_cambodia_now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            summary = db.get_summary_by_date(yesterday)
            msg = format_daily_summary(summary, title_prefix="ម្សិលមិញ (Yesterday)")
            await safe_edit_or_respond(event, msg, buttons=get_menu_buttons())

        elif data == b"btn_week":
            summary = db.get_summary_by_days(7)
            msg = format_range_summary(summary, title_prefix="៧ថ្ងៃចុងក្រោយ")
            await safe_edit_or_respond(event, msg, buttons=get_menu_buttons())

        elif data == b"btn_month":
            current_month = get_cambodia_now().strftime("%Y-%m")
            summary = db.get_summary_by_month(current_month)
            msg = format_monthly_summary(summary)
            await safe_edit_or_respond(event, msg, buttons=get_menu_buttons())

        elif data == b"btn_year":
            current_year = get_cambodia_now().strftime("%Y")
            summary = db.get_summary_by_year(current_year)
            msg = format_yearly_summary(summary)
            await safe_edit_or_respond(event, msg, buttons=get_menu_buttons())

        elif data == b"btn_history":
            txns = db.get_recent_transactions(limit=5)
            msg = format_recent_transactions(txns, limit=5)
            await safe_edit_or_respond(event, msg, buttons=get_menu_buttons())

        elif data == b"btn_exit":
            try:
                await event.answer("🚪 បានបិទរបាយការណ៍ (Exit)")
                await event.delete()
            except Exception:
                await event.edit("🔒 <i>របាយការណ៍ត្រូវបានបិទ (Report Closed)</i>\n👉 <i>ចុច <code>/today</code> ដើម្បីបើកឡើងវិញ</i>", parse_mode="html", buttons=None)

    @client.on(events.CallbackQuery)
    async def callback_handler(event: events.CallbackQuery.Event):
        try:
            await _process_callback(event)
        except Exception as e:
            logger.error(f"Error handling callback query: {e}", exc_info=True)
            try:
                await event.answer("⚠️ មានបញ្ហាបច្ចេកទេសបន្តិចបន្តួច សូមសាកល្បងម្តងទៀត!", alert=True)
            except Exception:
                pass

    # 2. Listener for new messages (monitoring KHQR payments & text commands)
    async def _process_message(event: events.NewMessage.Event):
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

        # Safety Check: Inspect sender identity (groups only, to avoid entity lookup failure in PM)
        is_sender_bot = False
        if not event.is_private:
            try:
                sender = await event.get_sender()
                is_sender_bot = bool(sender and getattr(sender, 'bot', False))
            except Exception:
                is_sender_bot = False

        # SAFETY 1: NEVER process or respond to commands sent by other bots in groups!
        # This completely guarantees 0% chance of bot-to-bot loops or interference with bank bots.
        if is_sender_bot and text.startswith(("/", ".")):
            return

        # SAFETY 2: Anti-Flood Rate limit commands per user (minimum 1.0s cooldown)
        if text.startswith(("/", ".")) and event.sender_id is not None:
            user_key = f"cmd_{event.sender_id}"
            now_ts = time.time()
            if user_key in last_command_time and (now_ts - last_command_time[user_key]) < 1.0:
                logger.warning(f"Command throttled for user {event.sender_id} to prevent spam")
                return
            last_command_time[user_key] = now_ts

        # Handle Commands
        text_stripped = text.strip()
        cmd = text_stripped.split()[0].lower() if text_stripped else ""
        if "@" in cmd:
            cmd = cmd.split("@")[0]

        # Aliases for quick button clicks, persistent keyboard, or Khmer text shortcuts
        if "របាយការណ៍" in text_stripped.lower() or text_stripped in ("📊 របាយការណ៍លក់", "📊 របាយការណ៍", "របាយការណ៍លក់", "📊 របាយការណ៍ថ្ងៃនេះ"):
            cmd = "/today"
        elif "ស្ថានភាព / version" in text_stripped.lower() or text_stripped in ("ℹ️ ស្ថានភាព / Version", "ℹ️ ស្ថានភាព / version", "ស្ថានភាព", "version"):
            cmd = "/version"
        elif "admin panel" in text_stripped.lower() or text_stripped in ("👑 Admin Panel", "👑 admin panel"):
            cmd = "/admin"
        elif "គ្រប់គ្រង group" in text_stripped.lower() or text_stripped in ("👥 គ្រប់គ្រង Group", "👥 គ្រប់គ្រង group"):
            cmd = "/manage"

        # Determine admin privileges
        is_owner_user = is_admin(event.sender_id, chat_id)

        # Persistent Keyboard clicks & Quick Admin Triggers for Bot Owner Avata
        if is_owner_user:
            if cmd in ("/manage", ".manage", "/group", ".group", "/members", ".members"):
                parts = text_stripped.split(maxsplit=1)
                group_query = parts[1].strip() if len(parts) > 1 and not parts[1].startswith("/") else ""
                if not group_query:
                    text_panel, btns = build_group_selector()
                else:
                    text_panel, btns = build_group_management_panel(group_query)
                await event.reply(text_panel, parse_mode="html", buttons=btns)
                return

            if cmd in ("/admin", ".admin", "/panel", ".panel"):
                text_panel, btns = build_admin_panel()
                await event.reply(text_panel, parse_mode="html", buttons=btns)
                return

        # 0. Start command in private chat: Welcome Bot Owner with full dashboard and buttons
        if cmd in ("/start", ".start") and event.is_private:
            if is_owner_user:
                panel_text, panel_btns = build_admin_panel()
                welcome_msg = (
                    "👋 <b>ជំរាបសួរលោកអ្នក (AVATA 🇸🇸) ជាម្ចាស់ Bot!</b>\n\n"
                    "ប្រព័ន្ធបានរៀបចំប៊ូតុង និងផ្ទាំងគ្រប់គ្រងការងាររួចរាល់សម្រាប់លោកអ្នក។\n"
                    "👇 <i>សូមចុចប៊ូតុងខាងក្រោម ឬប្រើប្រាស់ផ្ទាំងគ្រប់គ្រង៖</i>"
                )
                await event.reply(welcome_msg, parse_mode="html", buttons=get_owner_reply_keyboard())
                await event.reply(panel_text, parse_mode="html", buttons=panel_btns)
                return

        # 1. Identity command: Check Telegram ID (Publicly accessible)
        if cmd in ("/myid", ".myid", "/id", ".id"):
            name = "User"
            try:
                sender = await event.get_sender()
                if sender:
                    name = getattr(sender, 'first_name', 'User') or 'User'
            except Exception:
                pass
            extra_chat = f"\n👥 Group ID: <code>{chat_id}</code>\n" if not event.is_private else "\n"
            await safe_reply(
                event,
                f"🆔 <b>ព័ត៌មានអត្តសញ្ញាណ Telegram របស់អ្នក:</b>\n\n"
                f"👤 ឈ្មោះ: <b>{name}</b>\n"
                f"🔢 Telegram User ID: <code>{event.sender_id}</code>"
                f"{extra_chat}\n"
                f"💡 <i>ផ្ញើ User ID នេះទៅកាន់ម្ចាស់ហាង (Admin) ដើម្បីស្នើសុំសិទ្ធិមើលរបាយការណ៍ហិរញ្ញវត្ថុ។</i>",
                parse_mode="html"
            )
            return

        # System version & status command (Publicly accessible to check version)
        if cmd in ("/version", ".version", "/status", ".status"):
            uptime_str = get_cambodia_now().strftime("%Y-%m-%d %H:%M:%S")
            total_tx = db.get_transaction_count()
            users_count = len(db.list_authorized_users())
            status_text = (
                f"🤖 <b>ប្រព័ន្ធ KHQR Daily Report Bot</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏷️ <b>Version:</b> <code>v{config.BOT_VERSION}</code> (Enterprise Edition)\n"
                f"👑 <b>Bot Owner:</b> <code>AVATA 🇸🇸 (ID: 7299682335)</code>\n"
                f"🛡️ <b>ប្រព័ន្ធសុវត្ថិភាព:</b> <code>Strict Bot Owner RBAC (Active)</code>\n"
                f"📊 <b>ប្រតិបត្តិការសរុបក្នុង DB:</b> <code>{total_tx} លើក</code>\n"
                f"👥 <b>បុគ្គលិកមានសិទ្ធិ:</b> <code>{users_count} នាក់</code>\n"
                f"⏰ <b>ម៉ោងបច្ចុប្បន្ន:</b> <code>{uptime_str}</code>\n\n"
                f"✅ <i>ប្រព័ន្ធកំពុងដំណើរការកំណែចុងក្រោយបំផុតដោយជោគជ័យ។</i>"
            )
            await event.reply(status_text, parse_mode="html")
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

        # 4b. RBAC Management: Clear all authorized staff (Bot Owner only)
        if cmd in ("/clearusers", ".clearusers", "/resetusers", ".resetusers"):
            if not is_admin(event.sender_id):
                await event.reply("⛔ មានតែម្ចាស់អាជីវកម្ម (Avata) ប៉ុណ្ណោះដែលអាច Clear សិទ្ធិបាន!", parse_mode="html")
                return

            deleted_count = db.clear_authorized_users(keep_admin_ids=config.ADMIN_USER_IDS)
            await event.reply(
                f"🧹 <b>បានសម្អាត (Clear) សិទ្ធិបុគ្គលិកទាំងអស់ចំនួន {deleted_count} នាក់រួចរាល់!</b>\n\n"
                f"👑 <b>បច្ចុប្បន្នមានតែម្ចាស់ Bot (Avata) មួយគត់ដែលអាចមើលរបាយការណ៍បាន។</b>\n"
                "<i>រាល់អ្នកផ្សេងដែលចុចមើលរបាយការណ៍ នឹងត្រូវបញ្ជូនឈ្មោះ និង Telegram ID មកសុំការ Approve ពី Avata ទាំងអស់។</i>",
                parse_mode="html"
            )
            return

        # 4c. RBAC Group Member Management: /manage or /group or /members (Bot Owner Avata only)
        if cmd.startswith(("/manage", ".manage", "/group", ".group", "/members", ".members")):
            if not is_admin(event.sender_id):
                await event.reply("⛔ មុខងារគ្រប់គ្រងសមាជិកនេះ សម្រាប់តែម្ចាស់ Bot (Avata) តែប៉ុណ្ណោះ!", parse_mode="html")
                return

            parts = text_stripped.split(maxsplit=1)
            group_query = parts[1].strip() if len(parts) > 1 else ""

            if not group_query:
                text_panel, btns = build_group_selector()
                await event.reply(text_panel, parse_mode="html", buttons=btns)
                return

            text_panel, btns = build_group_management_panel(group_query)
            await event.reply(text_panel, parse_mode="html", buttons=btns)
            return

        # 5. Permission Gate: Protect financial report commands
        report_cmd_prefixes = (
            "/today", ".today", "បូកសរុបថ្ងៃនេះ",
            "/yesterday", ".yesterday", "ម្សិលមិញ",
            "/week", ".week", "/weekly", ".weekly", "សប្តាហ៍នេះ",
            "/month", ".month", "បូកសរុបខែនេះ",
            "/year", ".year", "/yearly", ".yearly", "ប្រចាំឆ្នាំ",
            "/history", ".history", "/recent", ".recent", "ប្រវត្តិ", "ប្រវត្តិចុងក្រោយ",
            "/report", ".report",
            "/sync", ".sync", "/backfill"
        )
        if any(cmd.startswith(p) for p in report_cmd_prefixes):
            if not check_permission(event.sender_id, chat_id):
                if event.sender_id is not None and event.sender_id > 0:
                    sender = None
                    try:
                        sender = await event.get_sender()
                    except Exception:
                        pass
                    first = getattr(sender, "first_name", "") if sender else ""
                    last = getattr(sender, "last_name", "") if sender else ""
                    fname = f"{first} {last}".strip() or f"User {event.sender_id}"
                    uname_val = getattr(sender, "username", None) if sender else None
                    uname_str = f" (@{uname_val})" if uname_val else ""

                    # Determine requester's role in the group (owner, admin, or member)
                    g_role = await get_user_group_role(client, chat_id, event.sender_id)

                    await notify_owner_of_access_request(
                        client=client,
                        user_id=event.sender_id,
                        chat_id=chat_id,
                        user_entity=sender,
                        source="command",
                        group_role=g_role
                    )
                    await event.reply(
                        "⛔ <b>ការចូលប្រើប្រាស់ត្រូវបានបដិសេធ (Access Denied)</b>\n\n"
                        "🔒 <b>របាយការណ៍ហិរញ្ញវត្ថុ និងប្រាក់ចំណូល ត្រូវបានការពារដោយសុវត្ថិភាពខ្ពស់។</b>\n"
                        "<i>(ទោះបីជា Owner ឬ Admin របស់ Group ក៏ត្រូវតែទទួលបានការអនុញ្ញាតពីម្ចាស់ Bot ជាមុនសិនដែរ)</i>\n\n"
                        f"👤 <b>ឈ្មោះ:</b> {fname} ({g_role}){uname_str}\n"
                        f"🔢 <b>Telegram User ID:</b> <code>{event.sender_id}</code>\n\n"
                        "📩 <b>ប្រព័ន្ធបានចាប់យកឈ្មោះ និង Telegram ID របស់អ្នកបញ្ជូនទៅម្ចាស់ Bot (Avata) រួចរាល់ហើយ!</b>\n"
                        "💡 <i>សូមរង់ចាំម្ចាស់ Bot ចុចយល់ព្រម (Approve) មួយភ្លែត។</i>",
                        parse_mode="html"
                    )
                else:
                    await safe_reply(
                        event,
                        "📊 <b>ផ្ទាំងរបាយការណ៍លក់ប្រចាំថ្ងៃ (Daily Sales Report)</b>\n\n"
                        "👇 <b>សូមចុចលើប៊ូតុងខាងក្រោម ដើម្បីបើកមើលរបាយការណ៍ភ្លាមៗ៖</b>\n"
                        "💡 <i>(ការចុចលើប៊ូតុងខាងក្រោម នឹងអនុញ្ញាតឱ្យប្រព័ន្ធផ្ទៀងផ្ទាត់សិទ្ធិបុគ្គលិកដោយស្វ័យប្រវត្ត)</i>",
                        parse_mode="html",
                        buttons=get_menu_buttons()
                    )
                return

        # 6. Execute Allowed Report Commands
        if cmd in ("/today", ".today", "បូកសរុបថ្ងៃនេះ"):
            today_str = get_cambodia_today_str()
            summary = db.get_summary_by_date(today_str)
            comparison = db.get_daily_comparison(today_str)
            msg = format_daily_summary(summary, comparison=comparison, title_prefix="ថ្ងៃនេះ (Today)")
            await safe_reply(event, msg, buttons=get_menu_buttons())
            return

        elif cmd in ("/yesterday", ".yesterday", "ម្សិលមិញ"):
            yesterday = (get_cambodia_now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            summary = db.get_summary_by_date(yesterday)
            msg = format_daily_summary(summary, title_prefix="ម្សិលមិញ (Yesterday)")
            await safe_reply(event, msg, buttons=get_menu_buttons())
            return

        elif cmd in ("/week", ".week", "/weekly", ".weekly", "សប្តាហ៍នេះ"):
            summary = db.get_summary_by_days(7)
            msg = format_range_summary(summary, title_prefix="៧ថ្ងៃចុងក្រោយ")
            await safe_reply(event, msg, buttons=get_menu_buttons())
            return

        elif cmd in ("/month", ".month", "បូកសរុបខែនេះ"):
            current_month = get_cambodia_now().strftime("%Y-%m")
            summary = db.get_summary_by_month(current_month)
            msg = format_monthly_summary(summary)
            await safe_reply(event, msg, buttons=get_menu_buttons())
            return

        elif cmd in ("/year", ".year", "/yearly", ".yearly", "ប្រចាំឆ្នាំ", "បូកសរុបប្រចាំឆ្នាំ"):
            current_year = get_cambodia_now().strftime("%Y")
            summary = db.get_summary_by_year(current_year)
            msg = format_yearly_summary(summary)
            await safe_reply(event, msg, buttons=get_menu_buttons())
            return

        elif cmd in ("/history", ".history", "/recent", ".recent", "ប្រវត្តិ", "ប្រវត្តិចុងក្រោយ"):
            parts = text_stripped.split()
            limit = 5
            if len(parts) > 1 and parts[1].isdigit():
                limit = min(int(parts[1]), 50)
            txns = db.get_recent_transactions(limit=limit)
            msg = format_recent_transactions(txns, limit=limit)
            await safe_reply(event, msg, buttons=get_menu_buttons())
            return

        elif cmd.startswith(("/report", ".report")):
            parts = text_stripped.split()
            if len(parts) > 1:
                target_date = parts[1].strip()
                try:
                    datetime.datetime.strptime(target_date, "%Y-%m-%d")
                    summary = db.get_summary_by_date(target_date)
                    msg = format_daily_summary(summary, title_prefix=f"ថ្ងៃ {target_date}")
                    await safe_reply(event, msg, buttons=get_menu_buttons())
                except ValueError:
                    await safe_reply(
                        event,
                        "⚠️ ទម្រង់កាលបរិច្ឆេទមិនត្រឹមត្រូវ! សូមប្រើ: <code>/report YYYY-MM-DD</code>\nឧទាហរណ៍: <code>/report 2026-09-28</code>"
                    )
            else:
                today_str = get_cambodia_today_str()
                summary = db.get_summary_by_date(today_str)
                comparison = db.get_daily_comparison(today_str)
                msg = format_daily_summary(summary, comparison=comparison, title_prefix="ថ្ងៃនេះ (Today)")
                await safe_reply(event, msg, buttons=get_menu_buttons())
            return

        elif cmd.startswith(("/sync", ".sync", "/backfill")):
            parts = text_stripped.split()
            limit = 200
            if len(parts) > 1 and parts[1].isdigit():
                limit = int(parts[1])

            target_chat = config.MONITOR_CHAT_ID or chat_id
            await safe_reply(event, f"🔄 កំពុងទាញយក និងពិនិត្យសារចាស់ៗចំនួន <b>{limit}</b> សារពី Group...")
            
            from sync_history import sync_previous_messages
            res = await sync_previous_messages(client, target_chat, limit=limit)
            if res and res.get("bot_restricted"):
                await safe_reply(
                    event,
                    "⚠️ <b>គណនី Bot មិនមានសិទ្ធិអានសារចាស់ៗក្នុង Group ឡើយ (Telegram Bot Restriction):</b>\n\n"
                    "Telegram មិនអនុញ្ញាតឱ្យ Bot ប្រើប្រាស់មុខងារ GetHistoryRequest បានឡើយ។\n"
                    "💡 ប៉ុន្តែរាល់ការទូទាត់ថ្មីៗដែលផ្ញើចូល Group នឹងត្រូវបានកត់ត្រាដោយស្វ័យប្រវត្តក្នុងពេលជាក់ស្តែង (Real-time)!",
                    buttons=get_menu_buttons()
                )
            elif res:
                reply_text = (
                    "✅ <b>ការទាញយកទិន្នន័យចាស់ៗជោគជ័យ:</b>\n\n"
                    f"• សារដែលបានពិនិត្យ: <b>{res['total_scanned']}</b> សារ\n"
                    f"• ប្រតិបត្តិការ KHQR ទាំងអស់: <b>{res['found_payments']}</b> លើក\n"
                    f"• ប្រតិបត្តិការថ្មីដែលបានកត់ត្រា: <b>{res['new_added']}</b> លើក\n"
                    f"• ប្រតិបត្តិការចាស់ដែលមានរួចហើយ: <b>{res['duplicates']}</b> លើក\n"
                    f"• ទឹកប្រាក់ថ្មីដែលទើបកត់ត្រា: <b>${res['usd_total']:,.2f}</b> | <b>{int(res['khr_total']):,} ៛</b>\n\n"
                    "💡 <i>លោកអ្នកអាចវាយ <code>/today</code> ឬ <code>/history</code> ដើម្បីមើលរបាយការណ៍បច្ចុប្បន្នភាព!</i>"
                )
                await safe_reply(event, reply_text, buttons=get_menu_buttons())
            else:
                await safe_reply(event, "⚠️ មិនអាចទាញយកសារចាស់ៗបានទេ។ សូមពិនិត្យមើលសិទ្ធិរបស់ Bot ក្នុង Group។", buttons=get_menu_buttons())
            return

        elif cmd in ("/menu", ".menu", "/start", ".start", "/help", ".help"):
            is_adm = is_admin(event.sender_id)
            help_text = (
                "🤖 <b>KHQR Sales & Daily Report Telegram Bot</b>\n\n"
                "👑 <b>ម្ចាស់ Bot (Owner):</b> <b>AVATA 🇸🇸</b> (@avatalamiyamal)\n\n"
                "📌 <b>របាយការណ៍ដែលលោកអ្នកអាចមើលបាន:</b>\n"
                "• <b>ទឹកប្រាក់សរុប:</b> បែងចែកប្រាក់ដុល្លារ ($) និងប្រាក់រៀល (៛)\n"
                "• <b>ចំនួនលក់សរុប:</b> រាប់ចំនួនលើកនៃការទូទាត់ជោគជ័យ\n"
                "• <b>ប្រៀបធៀបការលក់:</b> បង្ហាញការកើនឡើង ឬថយចុះធៀបនឹងម្សិលមិញ\n"
                "• <b>របាយការណ៍ប្រចាំឆ្នាំ:</b> បង្ហាញចំណូលសរុបប្រចាំឆ្នាំ និងតាមខែនីមួយៗ\n\n"
                "🛡️ <b>សុវត្ថិភាព និងការគ្រប់គ្រងសិទ្ធិ:</b>\n"
                "• <code>/myid</code> — មើល Telegram User ID របស់អ្នក\n"
                "• <code>/today</code> — មើលរបាយការណ៍ថ្ងៃនេះ\n"
                "• <code>/yesterday</code> — មើលរបាយការណ៍ម្សិលមិញ\n"
                "• <code>/week</code> — មើលរបាយការណ៍ ៧ថ្ងៃចុងក្រោយ\n"
                "• <code>/month</code> — មើលរបាយការណ៍ប្រចាំខែ\n"
                "• <code>/year</code> — មើលរបាយការណ៍ប្រចាំឆ្នាំ\n"
                "• <code>/history [ចំនួន]</code> — មើលប្រវត្តិប្រតិបត្តិការចុងក្រោយ (ឧទាហរណ៍: <code>/history 10</code>)\n"
            )
            if is_adm:
                help_text += (
                    "• <code>/adduser ID [role]</code> — បន្ថែមសិទ្ធិឱ្យបុគ្គលិក\n"
                    "• <code>/removeuser ID</code> — ដកសិទ្ធិបុគ្គលិក\n"
                    "• <code>/users</code> — បង្ហាញបញ្ជីបុគ្គលិកមានសិទ្ធិ\n"
                    "• <code>/sync [ចំនួន]</code> — ទាញយកសារចាស់ៗពីមុនមកបូកបញ្ចូល\n\n"
                )
            help_text += "👇 <b>សូមចុចប៊ូតុងខាងក្រោមដើម្បីមើលរបាយការណ៍:</b>"
            await safe_reply(event, help_text, buttons=get_menu_buttons())
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
                    await event.reply(
                        alert_text,
                        parse_mode="html",
                        buttons=[[Button.inline("📊 មើលរបាយការណ៍ថ្ងៃនេះ (Today)", data=b"btn_today")]]
                    )
            else:
                logger.warning(f"Ignored transaction: {message}")

    @client.on(events.NewMessage)
    async def message_listener(event: events.NewMessage.Event):
        try:
            await _process_message(event)
        except Exception as e:
            logger.error(f"Error handling incoming message: {e}", exc_info=True)



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
    # 1. Start Cloud Health-check HTTP server immediately for Render/Koyeb so port binds in <0.1s
    await start_health_check_server()

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

    # Register official Telegram Bot Commands Menu (Blue Menu button [/] in Telegram)
    try:
        from telethon.tl.functions.bots import SetBotCommandsRequest
        from telethon.tl.types import BotCommand, BotCommandScopeDefault
        await client(SetBotCommandsRequest(
            scope=BotCommandScopeDefault(),
            lang_code="",
            commands=[
                BotCommand(command="today", description="📊 មើលរបាយការណ៍លក់ថ្ងៃនេះ (1-Click)"),
                BotCommand(command="yesterday", description="📅 របាយការណ៍ម្សិលមិញ"),
                BotCommand(command="week", description="🗓 របាយការណ៍ ៧ថ្ងៃចុងក្រោយ"),
                BotCommand(command="month", description="📈 របាយការណ៍ប្រចាំខែ"),
                BotCommand(command="year", description="📆 របាយការណ៍ប្រចាំឆ្នាំ"),
                BotCommand(command="admin", description="👑 ផ្ទាំងបញ្ជាម្ចាស់ Bot (Avata)"),
                BotCommand(command="status", description="ℹ️ ពិនិត្យស្ថានភាព Bot & Version"),
            ]
        ))
        logger.info("Registered official Telegram Bot Command Menu successfully.")
    except Exception as e:
        logger.debug(f"Could not register Bot Commands menu: {e}")

    print(f"⏰ ម៉ោងផ្ញើរបាយការណ៍បូកសរុបប្រចាំថ្ងៃ: {config.DAILY_REPORT_TIME} (ម៉ោងនៅកម្ពុជា)")
    print("📡 កំពុងរង់ចាំ និងស្តាប់សារពីប្រព័ន្ធ KHQR...")

    # Auto sync past messages on startup in background (so bot doesn't miss prior transactions)
    if config.SYNC_ON_STARTUP and config.MONITOR_CHAT_ID:
        print("🔄 កំពុងទាញយកសារចាស់ៗក្នុង Group មកពិនិត្យដោយស្វ័យប្រវត្ត (Auto History Sync)...")
        from sync_history import sync_previous_messages
        asyncio.create_task(sync_previous_messages(client, config.MONITOR_CHAT_ID, limit=config.SYNC_LIMIT))

    # Auto notify Bot Owner when updated/started
    try:
        if config.ADMIN_USER_ID:
            uptime_str = get_cambodia_now().strftime("%Y-%m-%d %H:%M:%S")
            total_tx = db.get_transaction_count()
            users_count = len(db.list_authorized_users())
            startup_msg = (
                f"🚀 <b>ប្រព័ន្ធ Bot បាន Update ទៅកាន់ Version ថ្មីជោគជ័យ!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏷️ <b>Version:</b> <code>v{config.BOT_VERSION}</code> (Enterprise Edition)\n"
                f"⏰ <b>ម៉ោងដំណើរការ:</b> <code>{uptime_str}</code>\n"
                f"🛡️ <b>ប្រព័ន្ធសុវត្ថិភាព:</b> <code>Strict Bot Owner RBAC (Active)</code>\n"
                f"📊 <b>ទិន្នន័យក្នុង DB:</b> <code>{total_tx} លើក</code>\n"
                f"👥 <b>ចំនួនបុគ្គលិកមានសិទ្ធិ:</b> <code>{users_count} នាក់</code>\n\n"
                f"✅ <i>រាល់មុខងារថ្មីៗ និងការការពារសុវត្ថិភាពត្រូវបាន Update ពេញលេញ។</i>"
            )
            # Send message with persistent keyboard docked at bottom of chat
            await client.send_message(
                config.ADMIN_USER_ID, 
                startup_msg, 
                parse_mode="html", 
                buttons=get_owner_reply_keyboard()
            )
            # Also send interactive Master Admin Control Center
            panel_text, panel_btns = build_admin_panel()
            await client.send_message(config.ADMIN_USER_ID, panel_text, parse_mode="html", buttons=panel_btns)
            logger.info("Sent startup version notification and Admin Panel to Bot Owner.")
    except Exception as e:
        logger.debug(f"Could not send startup notification: {e}")

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

