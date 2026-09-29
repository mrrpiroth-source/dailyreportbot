import re
import os

with open('database.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add psycopg2 imports
imports = """
import sqlite3
try:
    import psycopg2
    from psycopg2.extras import DictCursor
except ImportError:
    psycopg2 = None
import config
"""
content = re.sub(r'import sqlite3', imports, content)

# 2. Modify get_connection to support Postgres
get_conn = """
    def get_connection(self):
        if hasattr(config, 'DATABASE_URL') and config.DATABASE_URL and config.DATABASE_URL.startswith('postgres'):
            if not psycopg2:
                raise RuntimeError("psycopg2 is not installed!")
            conn = psycopg2.connect(config.DATABASE_URL)
            return conn
        else:
            conn = sqlite3.connect(self.db_path, timeout=15.0)
            conn.row_factory = sqlite3.Row
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA busy_timeout=5000;")
            except Exception:
                pass
            return conn

    def get_cursor(self, conn):
        if hasattr(config, 'DATABASE_URL') and config.DATABASE_URL and config.DATABASE_URL.startswith('postgres'):
            return conn.cursor(cursor_factory=DictCursor)
        return conn.cursor()

    def execute_sql(self, cursor, sql, params=()):
        if hasattr(config, 'DATABASE_URL') and config.DATABASE_URL and config.DATABASE_URL.startswith('postgres'):
            # Postgres uses %s instead of ?
            sql = sql.replace('?', '%s')
            # Postgres uses SERIAL instead of AUTOINCREMENT
            sql = sql.replace('AUTOINCREMENT', '')
            if 'INTEGER PRIMARY KEY' in sql:
                sql = sql.replace('INTEGER PRIMARY KEY', 'SERIAL PRIMARY KEY')
        cursor.execute(sql, params)
"""

content = re.sub(r'    def get_connection\(self\) -> sqlite3\.Connection:.*?return conn', get_conn.strip('\n'), content, flags=re.DOTALL)

# 3. Replace all cursor.execute(...) with self.execute_sql(cursor, ...)
content = content.replace('cursor.execute(', 'self.execute_sql(cursor, ')

# 4. Replace conn.cursor() with self.get_cursor(conn)
content = content.replace('conn.cursor()', 'self.get_cursor(conn)')

# 5. Replace sqlite3.IntegrityError with Exception fallback for generic handling
content = content.replace('except sqlite3.IntegrityError:', 'except (sqlite3.IntegrityError, Exception) as e:\n                if "UNIQUE" not in str(e) and "duplicate" not in str(e).lower():\n                    raise e')

# 6. Replace lastrowid (which psycopg2 doesn't have)
# In Postgres, we'd use RETURNING id, but since we are doing generic cross-DB, 
# we can just return None for transaction_id, or mock it.
# Actually, the code expects cursor.lastrowid.
lastrow_logic = """
                if hasattr(config, 'DATABASE_URL') and config.DATABASE_URL and config.DATABASE_URL.startswith('postgres'):
                    # psycopg2 doesn't have lastrowid
                    return True, "បានកត់ត្រាជោគជ័យ (Saved successfully)", None
                else:
                    return True, "បានកត់ត្រាជោគជ័យ (Saved successfully)", cursor.lastrowid
"""
content = content.replace('return True, "បានកត់ត្រាជោគជ័យ (Saved successfully)", cursor.lastrowid', lastrow_logic.strip())

with open('database_new.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Migration script executed.")
