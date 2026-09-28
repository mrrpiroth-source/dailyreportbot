"""
Database management for KHQR Telegram Daily Report Bot.
Stores all parsed transactions and generates daily/monthly summaries.
"""

import sqlite3
import datetime
from typing import Optional, Dict, Any, List, Tuple
from zoneinfo import ZoneInfo

# Cambodia Timezone (UTC+7)
CAMBODIA_TZ = ZoneInfo("Asia/Phnom_Penh")

def get_cambodia_now() -> datetime.datetime:
    """Returns current datetime in Cambodia timezone."""
    return datetime.datetime.now(CAMBODIA_TZ)

def get_cambodia_today_str() -> str:
    """Returns today's date formatted as YYYY-MM-DD in Cambodia timezone."""
    return get_cambodia_now().strftime("%Y-%m-%d")


class Database:
    def __init__(self, db_path: str = "khqr_reports.db"):
        self.db_path = db_path
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Initializes database tables if they do not exist."""
        conn = self.get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        amount REAL NOT NULL,
                        currency TEXT NOT NULL, -- 'USD' or 'KHR'
                        payer_name TEXT,
                        ref_code TEXT,
                        bank_name TEXT DEFAULT 'ABA Bank',
                        raw_text TEXT,
                        transaction_time TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                cursor.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_ref_code 
                    ON transactions(ref_code) 
                    WHERE ref_code IS NOT NULL AND ref_code != '';
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_transactions_created_date 
                    ON transactions(transaction_time);
                """)

                # Authorized Users table for high-security Role-Based Access Control (RBAC)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS authorized_users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        full_name TEXT,
                        role TEXT DEFAULT 'staff', -- 'owner', 'admin', 'staff'
                        added_by INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
        finally:
            conn.close()

    def save_transaction(
        self,
        amount: float,
        currency: str,
        payer_name: Optional[str] = None,
        ref_code: Optional[str] = None,
        bank_name: str = "ABA Bank",
        raw_text: Optional[str] = None,
        transaction_time: Optional[str] = None
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Saves a payment transaction.
        Returns: (success: bool, message: str, transaction_id: Optional[int])
        """
        if not transaction_time:
            transaction_time = get_cambodia_now().strftime("%Y-%m-%d %H:%M:%S")

        currency = currency.upper().strip()
        if currency not in ("USD", "KHR"):
            if "$" in currency:
                currency = "USD"
            elif "៛" in currency or "RIEL" in currency:
                currency = "KHR"

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO transactions (
                        amount, currency, payer_name, ref_code, 
                        bank_name, raw_text, transaction_time
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    amount,
                    currency,
                    payer_name.strip() if payer_name else None,
                    ref_code.strip() if ref_code else None,
                    bank_name.strip() if bank_name else "ABA Bank",
                    raw_text,
                    transaction_time
                ))
                conn.commit()
                return True, "បានកត់ត្រាជោគជ័យ (Saved successfully)", cursor.lastrowid
            except sqlite3.IntegrityError:
                # Duplicate ref_code detected! Prevent double-counting.
                return False, f"ប្រតិបត្តិការនេះមានរួចហើយ (Duplicate transaction Ref: {ref_code})", None
            except Exception as e:
                return False, f"កំហុសក្នុងការកត់ត្រា (Error): {str(e)}", None
        finally:
            conn.close()

    def get_summary_by_date(self, target_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculates total USD, total KHR, and transaction counts for a specific date (YYYY-MM-DD).
        Defaults to today in Cambodia Time.
        """
        if not target_date:
            target_date = get_cambodia_today_str()

        # Date pattern for SQLite LIKE 'YYYY-MM-DD%'
        date_pattern = f"{target_date}%"

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # USD stats
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(amount), 0) as total,
                    COUNT(id) as count,
                    COALESCE(AVG(amount), 0) as avg_amount
                FROM transactions
                WHERE currency = 'USD' 
                  AND (transaction_time LIKE ? OR (transaction_time IS NULL AND created_at LIKE ?))
            """, (date_pattern, date_pattern))
            usd_row = cursor.fetchone()
            total_usd = float(usd_row["total"]) if usd_row else 0.0
            count_usd = int(usd_row["count"]) if usd_row else 0
            avg_usd = float(usd_row["avg_amount"]) if usd_row else 0.0

            # KHR stats
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(amount), 0) as total,
                    COUNT(id) as count,
                    COALESCE(AVG(amount), 0) as avg_amount
                FROM transactions
                WHERE currency = 'KHR' 
                  AND (transaction_time LIKE ? OR (transaction_time IS NULL AND created_at LIKE ?))
            """, (date_pattern, date_pattern))
            khr_row = cursor.fetchone()
            total_khr = float(khr_row["total"]) if khr_row else 0.0
            count_khr = int(khr_row["count"]) if khr_row else 0
            avg_khr = float(khr_row["avg_amount"]) if khr_row else 0.0

            return {
                "date": target_date,
                "total_usd": total_usd,
                "count_usd": count_usd,
                "avg_usd": avg_usd,
                "total_khr": total_khr,
                "count_khr": count_khr,
                "avg_khr": avg_khr,
                "total_count": count_usd + count_khr
            }
        finally:
            conn.close()

    def get_summary_by_month(self, target_month: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculates monthly summary for YYYY-MM. Defaults to current month.
        """
        if not target_month:
            target_month = get_cambodia_now().strftime("%Y-%m")

        month_pattern = f"{target_month}%"

        conn = self.get_connection()
        try:
            cursor = conn.cursor()

            # USD
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(amount), 0) as total, 
                    COUNT(id) as count,
                    COALESCE(AVG(amount), 0) as avg_amount
                FROM transactions
                WHERE currency = 'USD' AND transaction_time LIKE ?
            """, (month_pattern,))
            usd_row = cursor.fetchone()
            total_usd = float(usd_row["total"]) if usd_row else 0.0
            count_usd = int(usd_row["count"]) if usd_row else 0
            avg_usd = float(usd_row["avg_amount"]) if usd_row else 0.0

            # KHR
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(amount), 0) as total, 
                    COUNT(id) as count,
                    COALESCE(AVG(amount), 0) as avg_amount
                FROM transactions
                WHERE currency = 'KHR' AND transaction_time LIKE ?
            """, (month_pattern,))
            khr_row = cursor.fetchone()
            total_khr = float(khr_row["total"]) if khr_row else 0.0
            count_khr = int(khr_row["count"]) if khr_row else 0
            avg_khr = float(khr_row["avg_amount"]) if khr_row else 0.0

            # Active days in month
            cursor.execute("""
                SELECT COUNT(DISTINCT SUBSTR(transaction_time, 1, 10)) as active_days
                FROM transactions
                WHERE transaction_time LIKE ?
            """, (month_pattern,))
            active_days_row = cursor.fetchone()
            active_days = int(active_days_row["active_days"]) if active_days_row else 0

            return {
                "month": target_month,
                "total_usd": total_usd,
                "count_usd": count_usd,
                "avg_usd": avg_usd,
                "total_khr": total_khr,
                "count_khr": count_khr,
                "avg_khr": avg_khr,
                "total_count": count_usd + count_khr,
                "active_days": active_days
            }
        finally:
            conn.close()

    def get_summary_by_days(self, days: int = 7) -> Dict[str, Any]:
        """
        Calculates summary for the last N days (default 7 days for weekly report).
        """
        start_date = (get_cambodia_now() - datetime.timedelta(days=days - 1)).strftime("%Y-%m-%d")
        today_str = get_cambodia_today_str()

        conn = self.get_connection()
        try:
            cursor = conn.cursor()

            # USD
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(amount), 0) as total, 
                    COUNT(id) as count,
                    COALESCE(AVG(amount), 0) as avg_amount
                FROM transactions
                WHERE currency = 'USD' 
                  AND SUBSTR(transaction_time, 1, 10) BETWEEN ? AND ?
            """, (start_date, today_str))
            usd_row = cursor.fetchone()
            total_usd = float(usd_row["total"]) if usd_row else 0.0
            count_usd = int(usd_row["count"]) if usd_row else 0
            avg_usd = float(usd_row["avg_amount"]) if usd_row else 0.0

            # KHR
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(amount), 0) as total, 
                    COUNT(id) as count,
                    COALESCE(AVG(amount), 0) as avg_amount
                FROM transactions
                WHERE currency = 'KHR' 
                  AND SUBSTR(transaction_time, 1, 10) BETWEEN ? AND ?
            """, (start_date, today_str))
            khr_row = cursor.fetchone()
            total_khr = float(khr_row["total"]) if khr_row else 0.0
            count_khr = int(khr_row["count"]) if khr_row else 0
            avg_khr = float(khr_row["avg_amount"]) if khr_row else 0.0

            return {
                "start_date": start_date,
                "end_date": today_str,
                "days": days,
                "total_usd": total_usd,
                "count_usd": count_usd,
                "avg_usd": avg_usd,
                "total_khr": total_khr,
                "count_khr": count_khr,
                "avg_khr": avg_khr,
                "total_count": count_usd + count_khr
            }
        finally:
            conn.close()

    def get_recent_transactions(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Returns the most recent transactions."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, amount, currency, payer_name, ref_code, bank_name, transaction_time
                FROM transactions
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def add_authorized_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        full_name: Optional[str] = None,
        role: str = "staff",
        added_by: Optional[int] = None
    ) -> bool:
        """Adds or updates an authorized user."""
        conn = self.get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO authorized_users (user_id, username, full_name, role, added_by)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        username = excluded.username,
                        full_name = excluded.full_name,
                        role = excluded.role;
                """, (user_id, username, full_name, role, added_by))
                return True
        except Exception:
            return False
        finally:
            conn.close()

    def remove_authorized_user(self, user_id: int) -> bool:
        """Revokes access for a user."""
        conn = self.get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM authorized_users WHERE user_id = ?", (user_id,))
                return cursor.rowcount > 0
        except Exception:
            return False
        finally:
            conn.close()

    def is_user_authorized(self, user_id: int) -> bool:
        """Checks if a user is permitted to use the bot and view reports."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM authorized_users WHERE user_id = ?", (user_id,))
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def list_authorized_users(self) -> List[Dict[str, Any]]:
        """Returns all authorized users."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username, full_name, role, created_at FROM authorized_users ORDER BY role DESC, created_at ASC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

