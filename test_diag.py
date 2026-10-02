import asyncio
from telethon import TelegramClient
import config
from sync_history import sync_previous_messages

async def main():
    bot = TelegramClient('test_diag_bot', config.API_ID, config.API_HASH)
    await bot.start(bot_token=config.BOT_TOKEN) # type: ignore
    print("Bot started!")
    # Now run the exact same function
    await sync_previous_messages(bot, config.MONITOR_CHAT_ID, limit=5)
    await bot.disconnect()

asyncio.run(main())
