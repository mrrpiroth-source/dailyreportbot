import os
import sys
import json
import asyncio
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from telethon import TelegramClient
import config

async def request_code(phone_override: str = ""):
    phone = phone_override.strip() if phone_override.strip() else config.PHONE_NUMBER
    if not phone:
        print("ERROR: No phone number provided. Usage: python send_code.py <phone_number>")
        return

    session_name = "user_session"
    # If starting login for a new phone number, reset existing SQLite session file if present
    if os.path.exists(f"{session_name}.session"):
        try:
            os.remove(f"{session_name}.session")
        except Exception:
            pass

    client = TelegramClient(session_name, config.API_ID, config.API_HASH)
    await client.connect()
    
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
    phone_arg = sys.argv[1] if len(sys.argv) > 1 else ""
    asyncio.run(request_code(phone_arg))
