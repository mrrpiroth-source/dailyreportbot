import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()

cur.execute("""
    DELETE FROM transactions 
    WHERE raw_text LIKE '%ទើបទទួលបានការទូទាត់ជោគជ័យ%' 
       OR raw_text LIKE '%✅%'
       OR raw_text LIKE '%KHQR Sales%';
""")
print(f"Deleted {cur.rowcount} fake alert transactions!")

conn.commit()
cur.close()
conn.close()
