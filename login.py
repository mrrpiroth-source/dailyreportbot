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
            password = input("សូមបញ្ចូលលេខសម្ងាត់ 2-Step របស់អ្នក: ")
            try:
                await client.sign_in(password=password)
            except Exception as e:
                print(f"❌ កំហុសលេខសម្ងាត់ 2-Step: {e}")
                return
        except Exception as e:
            print(f"❌ កំហុស: {e}")
            return
            
    me = await client.get_me()
    print(f"\n✅ ចូលប្រើប្រាស់បានជោគជ័យជាគណនី: {me.first_name}")
    
    print("\n==================================================")
    print("✅ នេះគឺជា USER_SESSION_STRING ថ្មីរបស់អ្នក:")
    print("👇 សូម Copy កូដខាងក្រោមនេះ ទៅកាន់វិបសាយ Render")
    print("==================================================")
    print(client.session.save())
    print("==================================================\n")

if __name__ == '__main__':
    asyncio.run(main())
