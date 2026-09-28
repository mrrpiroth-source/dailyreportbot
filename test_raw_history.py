import sys
import asyncio
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
import config

async def test():
    client = TelegramClient('user_session', config.API_ID, config.API_HASH)
    await client.connect()
    chat = await client.get_input_entity(-1004325343684)
    res = await client(GetHistoryRequest(
        peer=chat,
        offset_id=0,
        offset_date=None,
        add_offset=0,
        limit=50,
        max_id=0,
        min_id=0,
        hash=0
    ))
    print(f"Raw messages returned: {len(res.messages)}")
    for m in res.messages:
        text = getattr(m, 'message', '') or ''
        print(f"[{m.date}] ID {m.id}: {repr(text[:80])}")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test())
