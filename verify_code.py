import os
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
        
        # Save session string
        from telethon.sessions import StringSession
        str_sess = StringSession()
        str_sess.set_dc(client.session.dc_id, client.session.server_address, client.session.port)
        str_sess.auth_key = client.session.auth_key
        session_str = str_sess.save()
        
        # Update .env
        import re
        if os.path.exists(".env"):
            with open(".env", "r", encoding="utf-8") as f:
                env_content = f.read()
            env_content = re.sub(r"USER_SESSION_STRING=[^\r\n]*", f"USER_SESSION_STRING={session_str}", env_content)
            env_content = re.sub(r"TELEGRAM_PHONE_NUMBER=[^\r\n]*", f"TELEGRAM_PHONE_NUMBER={phone}", env_content)
            with open(".env", "w", encoding="utf-8") as f:
                f.write(env_content)
            print("✅ Updated .env with new USER_SESSION_STRING and TELEGRAM_PHONE_NUMBER successfully!")
        
        return True
    except SessionPasswordNeededError:
        if password_str:
            await client.sign_in(password=password_str)
            me = await client.get_me()
            print(f"SUCCESS: Logged in with 2FA as {me.first_name} (@{me.username}) ID: {me.id}")
            
            # Save session string
            from telethon.sessions import StringSession
            str_sess = StringSession()
            str_sess.set_dc(client.session.dc_id, client.session.server_address, client.session.port)
            str_sess.auth_key = client.session.auth_key
            session_str = str_sess.save()
            
            # Update .env
            import re
            if os.path.exists(".env"):
                with open(".env", "r", encoding="utf-8") as f:
                    env_content = f.read()
                env_content = re.sub(r"USER_SESSION_STRING=[^\r\n]*", f"USER_SESSION_STRING={session_str}", env_content)
                env_content = re.sub(r"TELEGRAM_PHONE_NUMBER=[^\r\n]*", f"TELEGRAM_PHONE_NUMBER={phone}", env_content)
                with open(".env", "w", encoding="utf-8") as f:
                    f.write(env_content)
                print("✅ Updated .env with new USER_SESSION_STRING and TELEGRAM_PHONE_NUMBER successfully!")
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
