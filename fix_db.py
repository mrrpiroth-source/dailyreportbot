import config
import psycopg2

def fix_and_add():
    conn = psycopg2.connect(config.DATABASE_URL)
    conn.autocommit = True
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE authorized_users ALTER COLUMN user_id TYPE BIGINT;")
        cursor.execute("ALTER TABLE authorized_users ALTER COLUMN chat_id TYPE BIGINT;")
        cursor.execute("ALTER TABLE authorized_users ALTER COLUMN added_by TYPE BIGINT;")
        print("Schema altered to BIGINT.")
    except Exception as e:
        print(f"Error altering schema: {e}")
        
    try:
        cursor.execute("""
            INSERT INTO authorized_users (user_id, username, full_name, role, chat_id, chat_title, group_role, added_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, chat_id) DO UPDATE SET
                username = EXCLUDED.username,
                full_name = EXCLUDED.full_name,
                role = EXCLUDED.role,
                chat_title = EXCLUDED.chat_title,
                group_role = EXCLUDED.group_role;
        """, (5359573118, 'sunsreypov', 'ស៊ន់ ស្រីពៅ (owner)', 'staff', 0, 'Meeting cafe ☕', 'owner', None))
        print("User added successfully.")
    except Exception as e:
        print(f"Error adding user: {e}")
        
if __name__ == '__main__':
    fix_and_add()
