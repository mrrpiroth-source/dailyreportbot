import os
import sys
from dotenv import load_dotenv

load_dotenv()

if not os.getenv("DATABASE_URL"):
    print("No DATABASE_URL found!")
    sys.exit(1)

import psycopg2

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()

# Find duplicates
cur.execute("""
    SELECT count(*) FROM transactions;
""")
total_before = cur.fetchone()[0]
print(f"Total transactions before: {total_before}")

# Delete duplicates keeping the lowest ID for each raw_text
cur.execute("""
    DELETE FROM transactions
    WHERE id NOT IN (
        SELECT MIN(id)
        FROM transactions
        GROUP BY raw_text
    );
""")
deleted = cur.rowcount
print(f"Deleted {deleted} duplicate transactions!")

conn.commit()

cur.execute("""
    SELECT count(*) FROM transactions;
""")
total_after = cur.fetchone()[0]
print(f"Total transactions after: {total_after}")

cur.close()
conn.close()
