"""
Helper script to list all Telegram Groups and Channels with their Chat IDs.
Run this script to find the exact Group ID for MONITOR_CHAT_ID and REPORT_CHAT_ID in .env!
"""

import sys
import io
import asyncio

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from telethon import TelegramClient
from telethon.tl.types import Channel, Chat
from typing import cast, Any, Awaitable
import config

async def list_groups():
    if not config.API_ID or not config.API_HASH:
        print("❌ សូមបំពេញ TELEGRAM_API_ID និង TELEGRAM_API_HASH នៅក្នុង .env ជាមុនសិន!")
        return

    session_name = "khqr_session"
    client = TelegramClient(session_name, config.API_ID, config.API_HASH)

    if config.BOT_TOKEN:
        print("🤖 កំពុងភ្ជាប់ជាមួយ Bot Token...")
        await cast(Awaitable[Any], client.start(bot_token=config.BOT_TOKEN))
    elif config.PHONE_NUMBER:
        print(f"📱 កំពុងភ្ជាប់ជាមួយលេខទូរសព្ទ {config.PHONE_NUMBER}...")
        await cast(Awaitable[Any], client.start(phone=config.PHONE_NUMBER))
    else:
        print("🔑 កំពុងភ្ជាប់ Telegram Client...")
        await cast(Awaitable[Any], client.start())

    print("\n🔍 កំពុងទាញយកបញ្ជី Telegram Groups & Channels របស់អ្នក...\n")
    print("=" * 70)
    print(f"{'ប្រភេទ (Type)':<15} | {'ឈ្មោះ Group / Channel':<32} | {'Chat ID'}")
    print("=" * 70)

    found_count = 0
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        if isinstance(entity, (Channel, Chat)):
            title = dialog.name
            chat_id = dialog.id
            entity_type = "Group/Channel"
            if getattr(entity, 'megagroup', False):
                entity_type = "Supergroup"
            elif isinstance(entity, Chat):
                entity_type = "Basic Group"
            elif getattr(entity, 'broadcast', False):
                entity_type = "Channel"

            print(f"{entity_type:<15} | {title[:30]:<32} | {chat_id}")
            found_count += 1

    print("=" * 70)
    print(f"\n✅ បានរកឃើញចំនួនសរុប: {found_count} Groups/Channels.")
    print("👉 សូមចម្លង Chat ID របស់ Group ដែលមានសារធនាគារ យកទៅដាក់ក្នុង .env :")
    print("   MONITOR_CHAT_ID=-100xxxxxxxxxx")
    print("   REPORT_CHAT_ID=-100xxxxxxxxxx\n")

if __name__ == "__main__":
    asyncio.run(list_groups())
