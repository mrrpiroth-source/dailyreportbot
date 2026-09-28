import sys
import json
import asyncio
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from telethon import TelegramClient
import config

async def request_code():
    session_name = "user_session"
    client = TelegramClient(session_name, config.API_ID, config.API_HASH)
    await client.connect()
    
    phone = config.PHONE_NUMBER
    print(f"Requesting login code for {phone}...")
    sent_code = await client.send_code_request(phone)
    print(f"Code sent successfully! Type: {sent_code.type}")
    
    # Save code hash for the next step
    auth_data = {
        "phone": phone,
        "phone_code_hash": sent_code.phone_code_hash
    }
    with open("auth_temp.json", "w", encoding="utf-8") as f:
        json.dump(auth_data, f)
    
    print("SAVED_HASH_OK")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(request_code())
