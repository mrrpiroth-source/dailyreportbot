import asyncio
from telethon import TelegramClient
import config

async def main():
    client = TelegramClient('user_session', config.API_ID, config.API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        print("Not authorized!")
        return
    me = await client.get_me()
    print("Logged in as:", me.first_name)
    try:
        messages = await client.get_messages(config.MONITOR_CHAT_ID, limit=5)
        print("Got messages!", len(messages))
    except Exception as e:
        print("Error:", e)
    await client.disconnect()

asyncio.run(main())
