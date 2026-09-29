import sys
import os
if sys.platform == "win32":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

from telethon.sessions import StringSession, SQLiteSession
import config

def convert_session(filename):
    if not os.path.exists(filename):
        print(f"❌ មិនមានឯកសារ {filename} ទេ!")
        return None
        
    sql_session = SQLiteSession(filename)
    str_session = StringSession()
    
    str_session.set_dc(sql_session.dc_id, sql_session.server_address, sql_session.port)
    str_session.auth_key = sql_session.auth_key
    
    return str_session.save()

def main():
    print("==================================================")
    print("កំពុងបំប្លែង Session ទៅជាកូដ...")
    user_str = convert_session('user_session.session')
    
    print("\n✅ USER_SESSION_STRING:")
    print(user_str)
    print("==================================================")
    
if __name__ == '__main__':
    main()
