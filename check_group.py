import sys
import asyncio
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from telethon import TelegramClient
import config

async def check():
    client = TelegramClient('user_session', config.API_ID, config.API_HASH)
    await client.connect()
    dialogs = await client.get_dialogs(limit=30)
    found = None
    for d in dialogs:
        if d.is_group and ('Meeting' in (d.title or '') or 'cafe' in (d.title or '').lower() or d.id == -1004325343684):
            found = d
            break
    if found:
        print(f"SUCCESS: Found group '{found.title}' (ID: {found.id})")
    else:
        print("NOT FOUND. All groups:")
        for d in dialogs:
            if d.is_group:
                print(f"- [{d.id}] {d.title}")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(check())
