import os
import sys
from dotenv import load_dotenv
import psycopg2

load_dotenv()

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()

cur.execute("""
    SELECT count(*) FROM transactions;
""")
print(f"Total before: {cur.fetchone()[0]}")

cur.execute("""
    DELETE FROM transactions 
    WHERE raw_text LIKE '%របាយការណ៍បូកសរុប%' 
       OR raw_text LIKE '%KHQR Sales%' 
       OR raw_text LIKE '%ផ្ទាំងគ្រប់គ្រង%';
""")
print(f"Deleted {cur.rowcount} fake report transactions!")

conn.commit()

cur.execute("""
    SELECT count(*) FROM transactions;
""")
print(f"Total after: {cur.fetchone()[0]}")

cur.close()
conn.close()
