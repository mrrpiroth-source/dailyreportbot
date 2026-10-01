import os
import sys
from dotenv import load_dotenv
import psycopg2
from tabulate import tabulate

load_dotenv()

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()

cur.execute("""
    SELECT id, amount, currency, payer_name, ref_code, transaction_time, raw_text
    FROM transactions
    WHERE currency = 'USD'
    ORDER BY id DESC
    LIMIT 15;
""")
rows = cur.fetchall()

headers = ["id", "amount", "cur", "payer", "ref_code", "time", "raw_text_snippet"]
table = []
for r in rows:
    raw_text = r[6]
    snippet = raw_text[:50].replace('\n', ' ') if raw_text else "None"
    table.append([r[0], r[1], r[2], r[3], r[4], r[5], snippet])

print("USD Transactions:")
for r in table:
    print(r)

cur.close()
conn.close()
