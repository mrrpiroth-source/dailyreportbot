import asyncio
import os
import sys
from telethon import TelegramClient
from telethon.sessions import StringSession
import telethon.errors
from dotenv import load_dotenv

if sys.platform == "win32":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
PHONE_NUMBER = os.getenv("TELEGRAM_PHONE_NUMBER")

async def main():
    print("==================================================")
    print("🚀 កម្មវិធីបង្កើត Session ថ្មី (Login) សម្រាប់ KHQR Bot")
    print("==================================================")
    
    if not API_ID or not API_HASH:
        print("❌ សូមបញ្ចូល TELEGRAM_API_ID និង HASH នៅក្នុងឯកសារ .env ជាមុនសិន។")
        return

    print("កំពុងភ្ជាប់ទៅកាន់ Telegram...")
    
    client = TelegramClient(StringSession(), int(API_ID), API_HASH)
    await client.connect()
    
    if not await client.is_user_authorized():
        print("ការភ្ជាប់តម្រូវឲ្យមានការបញ្ជាក់លេខកូដ (OTP)...")
        if not PHONE_NUMBER:
            PHONE_NUMBER_INPUT = input("សូមបញ្ចូលលេខទូរសព្ទរបស់អ្នក (ឧទាហរណ៍ +855...): ")
        else:
            PHONE_NUMBER_INPUT = PHONE_NUMBER
            print(f"ប្រើប្រាស់លេខទូរសព្ទពី .env: {PHONE_NUMBER_INPUT}")
            
        await client.send_code_request(PHONE_NUMBER_INPUT)
        code = input("សូមបញ្ចូលលេខកូដ 5 ខ្ទង់ដែល Telegram បានផ្ញើទៅកាន់ App របស់អ្នក: ")
        
        try:
            await client.sign_in(PHONE_NUMBER_INPUT, code)
        except telethon.errors.SessionPasswordNeededError:
            print("\nគណនីរបស់អ្នកមានដាក់លេខកូដសុវត្ថិភាព ២ ជាន់ (2-Step Verification)!")
            password = input("សូមបញ្ចូលលេខសម្ងាត់ 2-Step របស់អ្នក (ចុច Enter ដើម្បីប្រើ Default): ")
            if not password:
                password = "Piroth@168!?"
            try:
                await client.sign_in(password=password)
            except Exception as e:
                print(f"❌ កំហុសលេខសម្ងាត់ 2-Step: {e}")
                return
        except Exception as e:
            print(f"❌ កំហុស: {e}")
            return
            
    me = await client.get_me()
    print(f"\n✅ ចូលប្រើប្រាស់បានជោគជ័យជាគណនី: {me.first_name} (@{me.username}) ID: {me.id}")
    
    session_string = client.session.save()
    
    # Auto-save session string and phone number into .env
    import re
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            env_content = f.read()
        env_content = re.sub(r"USER_SESSION_STRING=[^\r\n]*", f"USER_SESSION_STRING={session_string}", env_content)
        env_content = re.sub(r"TELEGRAM_PHONE_NUMBER=[^\r\n]*", f"TELEGRAM_PHONE_NUMBER={PHONE_NUMBER_INPUT}", env_content)
        with open(".env", "w", encoding="utf-8") as f:
            f.write(env_content)
        print("✅ បានរក្សាទុក Session String និងលេខទូរសព្ទទៅក្នុងឯកសារ .env ដោយស្វ័យប្រវត្តិ!")

    # Auto-save SQLite session file
    try:
        from telethon.sessions import SQLiteSession
        sql_sess = SQLiteSession("user_session")
        sql_sess.set_dc(client.session.dc_id, client.session.server_address, client.session.port)
        sql_sess.auth_key = client.session.auth_key
        sql_sess.save()
        print("✅ បានរក្សាទុក user_session.session សម្រាប់ប្រើប្រាស់ក្នុងកុំព្យូទ័រនេះ!")
    except Exception as sqle:
        print(f"⚠️ SQLite session save: {sqle}")

    print("\n==================================================")
    print("✅ នេះគឺជា USER_SESSION_STRING ថ្មីរបស់អ្នក:")
    print("👇 សូម Copy កូដខាងក្រោមនេះ ទៅកាន់វិបសាយ Render (បើមានប្រើ Render):")
    print("==================================================")
    print(session_string)
    print("==================================================\n")

    try:
        # Send to Saved Messages for security
        await client.send_message(
            "me", 
            f"🔐 <b>USER_SESSION_STRING ថ្មីរបស់អ្នក:</b>\n\n<code>{session_string}</code>\n\n⚠️ <i>សូមរក្សាកូដនេះជាការសម្ងាត់កុំឱ្យនរណាម្នាក់ដឹង (កូដនេះអាចគ្រប់គ្រងគណនីរបស់អ្នកបាន)!</i>", 
            parse_mode="html"
        )
        print("✅ បានផ្ញើ Session String ចូលទៅកាន់ Saved Messages ក្នុង Telegram របស់អ្នកដោយសុវត្ថិភាព។")
        
        # Also try to send to admin if configured
        MASTER_BOT_OWNER_ID = os.getenv("MASTER_BOT_OWNER_ID")
        if MASTER_BOT_OWNER_ID:
            await client.send_message(
                int(MASTER_BOT_OWNER_ID), 
                f"🚨 <b>(Security Alert)</b> មានការ Log in បង្កើត Session ថ្មីពីគណនី {me.first_name}។", 
                parse_mode="html"
            )
    except Exception as e:
        print(f"⚠️ មិនអាចផ្ញើចូល Telegram បានទេ: {e}")

if __name__ == '__main__':
    asyncio.run(main())
