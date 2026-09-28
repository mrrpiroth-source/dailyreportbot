import sys
import io
import asyncio
from typing import cast, Any, Awaitable

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from telethon import TelegramClient
import config

async def test_bot():
    client = TelegramClient("test_bot_session", config.API_ID, config.API_HASH)
    print("Testing connection with Bot Token...")
    await cast(Awaitable[Any], client.start(bot_token=config.BOT_TOKEN))
    me = await client.get_me()
    print(f"CONNECTED SUCCESSFULLY as @{me.username} (ID: {me.id})")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test_bot())
