import sys
import json
import asyncio
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
import config

async def verify(code_str: str, password_str: str = ""):
    session_name = "user_session"
    client = TelegramClient(session_name, config.API_ID, config.API_HASH)
    await client.connect()
    
    with open("auth_temp.json", "r", encoding="utf-8") as f:
        auth_data = json.load(f)
    
    phone = auth_data["phone"]
    phone_code_hash = auth_data["phone_code_hash"]
    
    try:
        await client.sign_in(phone=phone, code=code_str, phone_code_hash=phone_code_hash)
        me = await client.get_me()
        print(f"SUCCESS: Logged in as {me.first_name} (@{me.username}) ID: {me.id}")
        return True
    except SessionPasswordNeededError:
        if password_str:
            await client.sign_in(password=password_str)
            me = await client.get_me()
            print(f"SUCCESS: Logged in with 2FA as {me.first_name} (@{me.username}) ID: {me.id}")
            return True
        else:
            print("2FA_REQUIRED: This Telegram account has Two-Factor Authentication (2FA) enabled. Please provide 2FA password.")
            return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False
    finally:
        await client.disconnect()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python verify_code.py <5-digit-code> [2fa-password]")
        sys.exit(1)
    code = sys.argv[1].strip()
    pwd = sys.argv[2].strip() if len(sys.argv) > 2 else ""
    asyncio.run(verify(code, pwd))
