"""
Database management for KHQR Telegram Daily Report Bot.
Stores all parsed transactions and generates daily/monthly summaries.
"""


import sqlite3
try:
    import psycopg2
    from psycopg2.extras import DictCursor
except ImportError:
    psycopg2 = None
import config

import logging
import datetime
from typing import Optional, Dict, Any, List, Tuple
from zoneinfo import ZoneInfo

logger = logging.getLogger("KHQR_DB")

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

    def get_connection(self):
        if hasattr(config, 'DATABASE_URL') and config.DATABASE_URL and config.DATABASE_URL.startswith('postgres'):
            if not psycopg2:
                raise RuntimeError("psycopg2 is not installed!")
            conn = psycopg2.connect(config.DATABASE_URL)
            conn.autocommit = True
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
            sql = sql.replace('created_at LIKE', 'CAST(created_at AS TEXT) LIKE')
            sql = sql.replace('transaction_time LIKE', 'CAST(transaction_time AS TEXT) LIKE')
        cursor.execute(sql, params)

    def init_db(self):
        """Initializes database tables if they do not exist."""
        conn = self.get_connection()
        try:
            cursor = self.get_cursor(conn)
            self.execute_sql(cursor, """
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

            self.execute_sql(cursor, """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_ref_code 
                ON transactions(ref_code) 
                WHERE ref_code IS NOT NULL AND ref_code != '';
            """)

            self.execute_sql(cursor, """
                CREATE INDEX IF NOT EXISTS idx_transactions_created_date 
                ON transactions(transaction_time);
            """)

            # Authorized Users table for high-security Role-Based Access Control (RBAC) organized by Group
            self.execute_sql(cursor, """
                CREATE TABLE IF NOT EXISTS authorized_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    full_name TEXT,
                    role TEXT DEFAULT 'staff', -- 'owner', 'admin', 'staff'
                    chat_id INTEGER DEFAULT 0,
                    chat_title TEXT DEFAULT '',
                    group_role TEXT DEFAULT 'សមាជិក', -- 'owner', 'admin', 'សមាជិក'
                    added_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, chat_id)
                );
            """)
            # Seamless migrations for existing tables
            for col_sql in [
                "ALTER TABLE authorized_users ADD COLUMN chat_id INTEGER DEFAULT 0;",
                "ALTER TABLE authorized_users ADD COLUMN chat_title TEXT DEFAULT '';",
                "ALTER TABLE authorized_users ADD COLUMN group_role TEXT DEFAULT 'សមាជិក';"
            ]:
                try:
                    self.execute_sql(cursor, col_sql)
                except Exception:
                    pass

            self.execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_auth_chat_id ON authorized_users(chat_id);")
            self.execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_auth_chat_title ON authorized_users(chat_title);")
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
            cursor = self.get_cursor(conn)
            
            # Prevent duplicates by raw_text
            self.execute_sql(cursor, "SELECT id FROM transactions WHERE raw_text = ?", (raw_text,))
            if cursor.fetchone():
                return False, f"ប្រតិបត្តិការនេះមានរួចហើយ (Duplicate transaction text)", None

            try:
                self.execute_sql(cursor, """
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
                if hasattr(config, 'DATABASE_URL') and config.DATABASE_URL and config.DATABASE_URL.startswith('postgres'):
                    # psycopg2 doesn't have lastrowid
                    return True, "បានកត់ត្រាជោគជ័យ (Saved successfully)", None
                else:
                    return True, "បានកត់ត្រាជោគជ័យ (Saved successfully)", cursor.lastrowid
            except (sqlite3.IntegrityError, Exception) as e:
                if "UNIQUE" not in str(e) and "duplicate" not in str(e).lower():
                    raise e
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
            cursor = self.get_cursor(conn)
            
            # USD stats
            self.execute_sql(cursor, """
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
            self.execute_sql(cursor, """
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
            cursor = self.get_cursor(conn)

            # USD
            self.execute_sql(cursor, """
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
            self.execute_sql(cursor, """
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
            self.execute_sql(cursor, """
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
            cursor = self.get_cursor(conn)

            # USD
            self.execute_sql(cursor, """
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
            self.execute_sql(cursor, """
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

    def get_summary_by_year(self, target_year: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculates yearly summary for YYYY. Defaults to current year.
        Includes monthly breakdown for all months with transactions.
        """
        if not target_year:
            target_year = get_cambodia_now().strftime("%Y")

        year_pattern = f"{target_year}%"

        conn = self.get_connection()
        try:
            cursor = self.get_cursor(conn)

            # USD
            self.execute_sql(cursor, """
                SELECT 
                    COALESCE(SUM(amount), 0) as total, 
                    COUNT(id) as count
                FROM transactions
                WHERE currency = 'USD' AND transaction_time LIKE ?
            """, (year_pattern,))
            usd_row = cursor.fetchone()
            total_usd = float(usd_row["total"]) if usd_row else 0.0
            count_usd = int(usd_row["count"]) if usd_row else 0

            # KHR
            self.execute_sql(cursor, """
                SELECT 
                    COALESCE(SUM(amount), 0) as total, 
                    COUNT(id) as count
                FROM transactions
                WHERE currency = 'KHR' AND transaction_time LIKE ?
            """, (year_pattern,))
            khr_row = cursor.fetchone()
            total_khr = float(khr_row["total"]) if khr_row else 0.0
            count_khr = int(khr_row["count"]) if khr_row else 0

            # Active days in year
            self.execute_sql(cursor, """
                SELECT COUNT(DISTINCT SUBSTR(transaction_time, 1, 10)) as active_days
                FROM transactions
                WHERE transaction_time LIKE ?
            """, (year_pattern,))
            active_days_row = cursor.fetchone()
            active_days = int(active_days_row["active_days"]) if active_days_row else 0

            # Monthly breakdown
            self.execute_sql(cursor, """
                SELECT 
                    SUBSTR(transaction_time, 6, 2) as month_num,
                    currency,
                    COALESCE(SUM(amount), 0) as total,
                    COUNT(id) as count
                FROM transactions
                WHERE transaction_time LIKE ?
                GROUP BY SUBSTR(transaction_time, 6, 2), currency
                ORDER BY month_num ASC
            """, (year_pattern,))
            breakdown_rows = cursor.fetchall()
            
            # Aggregate by month
            months_dict = {}
            for r in breakdown_rows:
                m = r["month_num"]
                curr = r["currency"]
                if m not in months_dict:
                    months_dict[m] = {"month": m, "total_usd": 0.0, "total_khr": 0.0, "count": 0}
                months_dict[m]["count"] += int(r["count"])
                if curr == "USD":
                    months_dict[m]["total_usd"] += float(r["total"])
                elif curr == "KHR":
                    months_dict[m]["total_khr"] += float(r["total"])

            return {
                "year": target_year,
                "total_usd": total_usd,
                "count_usd": count_usd,
                "total_khr": total_khr,
                "count_khr": count_khr,
                "total_count": count_usd + count_khr,
                "active_days": active_days,
                "monthly_breakdown": list(months_dict.values())
            }
        finally:
            conn.close()

    def get_daily_comparison(self, target_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Compares sales between target_date (default today) and yesterday.
        Calculates increase or decrease in USD, KHR, and transaction count.
        """
        if not target_date:
            target_date = get_cambodia_today_str()

        target_dt = datetime.datetime.strptime(target_date, "%Y-%m-%d")
        yesterday_str = (target_dt - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

        today_summary = self.get_summary_by_date(target_date)
        yesterday_summary = self.get_summary_by_date(yesterday_str)

        diff_usd = today_summary["total_usd"] - yesterday_summary["total_usd"]
        diff_khr = today_summary["total_khr"] - yesterday_summary["total_khr"]
        diff_count = today_summary["total_count"] - yesterday_summary["total_count"]

        return {
            "today": today_summary,
            "yesterday": yesterday_summary,
            "yesterday_date": yesterday_str,
            "diff_usd": diff_usd,
            "diff_khr": diff_khr,
            "diff_count": diff_count,
        }

    def get_recent_transactions(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Returns the most recent transactions."""
        conn = self.get_connection()
        try:
            cursor = self.get_cursor(conn)
            self.execute_sql(cursor, """
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
        chat_id: int = 0,
        chat_title: str = "",
        group_role: str = "សមាជិក",
        added_by: Optional[int] = None
    ) -> bool:
        """Adds or updates an authorized user for a specific group."""
        conn = self.get_connection()
        try:
            with conn:
                cursor = self.get_cursor(conn)
                self.execute_sql(cursor, """
                    INSERT INTO authorized_users (user_id, username, full_name, role, chat_id, chat_title, group_role, added_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, chat_id) DO UPDATE SET
                        username = excluded.username,
                        full_name = excluded.full_name,
                        role = excluded.role,
                        chat_title = excluded.chat_title,
                        group_role = excluded.group_role;
                """, (user_id, username, full_name, role, chat_id, chat_title, group_role, added_by))
                return True
        except Exception as e:
            logger.error(f"Failed to add authorized user: {e}")
            return False
        finally:
            conn.close()

    def remove_authorized_user(self, user_id: int, chat_id: Optional[int] = None) -> bool:
        """Revokes access for a user in a specific group or across all groups."""
        conn = self.get_connection()
        try:
            with conn:
                cursor = self.get_cursor(conn)
                if chat_id is not None and chat_id != 0:
                    self.execute_sql(cursor, "DELETE FROM authorized_users WHERE user_id = ? AND chat_id = ?", (user_id, chat_id))
                else:
                    self.execute_sql(cursor, "DELETE FROM authorized_users WHERE user_id = ?", (user_id,))
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to remove authorized user: {e}")
            return False
        finally:
            conn.close()

    def is_user_authorized(self, user_id: int, chat_id: Optional[int] = None) -> bool:
        """Checks if a user is permitted to use the bot in a group."""
        conn = self.get_connection()
        try:
            cursor = self.get_cursor(conn)
            if chat_id is not None and chat_id != 0:
                self.execute_sql(cursor, "SELECT 1 FROM authorized_users WHERE user_id = ? AND (chat_id = ? OR chat_id = 0)", (user_id, chat_id))
            else:
                self.execute_sql(cursor, "SELECT 1 FROM authorized_users WHERE user_id = ?", (user_id,))
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def get_user_role(self, user_id: int, chat_id: Optional[int] = None) -> Optional[str]:
        """Returns role ('owner', 'admin', 'staff') of a user if authorized, else None."""
        conn = self.get_connection()
        try:
            cursor = self.get_cursor(conn)
            if chat_id is not None and chat_id != 0:
                self.execute_sql(cursor, "SELECT role FROM authorized_users WHERE user_id = ? AND (chat_id = ? OR chat_id = 0) ORDER BY id ASC LIMIT 1", (user_id, chat_id))
            else:
                self.execute_sql(cursor, "SELECT role FROM authorized_users WHERE user_id = ? ORDER BY id ASC LIMIT 1", (user_id,))
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def list_authorized_users(self, chat_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Returns all authorized users, optionally filtered by group chat_id."""
        conn = self.get_connection()
        try:
            cursor = self.get_cursor(conn)
            if chat_id is not None and chat_id != 0:
                self.execute_sql(cursor, 
                    "SELECT id, user_id, username, full_name, role, chat_id, chat_title, group_role, created_at "
                    "FROM authorized_users WHERE chat_id = ? ORDER BY id ASC", (chat_id,)
                )
            else:
                self.execute_sql(cursor, 
                    "SELECT id, user_id, username, full_name, role, chat_id, chat_title, group_role, created_at "
                    "FROM authorized_users ORDER BY chat_title ASC, id ASC"
                )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def list_authorized_users_by_group(self, group_query: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Returns authorized users for a specific group searched by chat_id or chat_title (e.g. 'Meeting cafe ☕').
        """
        conn = self.get_connection()
        try:
            cursor = self.get_cursor(conn)
            if group_query:
                clean_q = str(group_query).strip()
                if clean_q.lstrip("-").isdigit():
                    self.execute_sql(cursor, 
                        "SELECT id, user_id, username, full_name, role, chat_id, chat_title, group_role, created_at "
                        "FROM authorized_users WHERE chat_id = ? ORDER BY id ASC", (int(clean_q),)
                    )
                else:
                    self.execute_sql(cursor, 
                        "SELECT id, user_id, username, full_name, role, chat_id, chat_title, group_role, created_at "
                        "FROM authorized_users WHERE LOWER(chat_title) LIKE ? ORDER BY id ASC",
                        (f"%{clean_q.lower()}%",)
                    )
            else:
                self.execute_sql(cursor, 
                    "SELECT id, user_id, username, full_name, role, chat_id, chat_title, group_role, created_at "
                    "FROM authorized_users ORDER BY chat_title ASC, id ASC"
                )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_authorized_user_by_id(self, user_id: int, chat_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Returns details of a specific authorized user."""
        conn = self.get_connection()
        try:
            cursor = self.get_cursor(conn)
            if chat_id is not None and chat_id != 0:
                self.execute_sql(cursor, "SELECT * FROM authorized_users WHERE user_id = ? AND chat_id = ?", (user_id, chat_id))
            else:
                self.execute_sql(cursor, "SELECT * FROM authorized_users WHERE user_id = ? LIMIT 1", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_groups_summary(self) -> List[Dict[str, Any]]:
        """Returns distinct groups with authorized member counts."""
        conn = self.get_connection()
        try:
            cursor = self.get_cursor(conn)
            self.execute_sql(cursor, """
                SELECT chat_id, chat_title, COUNT(*) as member_count
                FROM authorized_users
                WHERE chat_id != 0
                GROUP BY chat_id, chat_title
                ORDER BY member_count DESC, chat_title ASC
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def clear_authorized_users(self, keep_admin_ids: Optional[List[int]] = None, chat_id: Optional[int] = None) -> int:
        """Clears authorized users from database, optionally keeping master bot owners or per group."""
        conn = self.get_connection()
        try:
            with conn:
                cursor = self.get_cursor(conn)
                query = "DELETE FROM authorized_users"
                params: List[Any] = []
                conditions = []

                if keep_admin_ids:
                    placeholders = ",".join("?" for _ in keep_admin_ids)
                    conditions.append(f"user_id NOT IN ({placeholders})")
                    params.extend(keep_admin_ids)

                if chat_id is not None and chat_id != 0:
                    conditions.append("chat_id = ?")
                    params.append(chat_id)

                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

                self.execute_sql(cursor, query, params)
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Failed to clear authorized users: {e}")
            return 0
        finally:
            conn.close()

    def get_transaction_count(self) -> int:
        """Returns total count of transactions stored in database."""
        conn = self.get_connection()
        try:
            cursor = self.get_cursor(conn)
            self.execute_sql(cursor, "SELECT COUNT(*) FROM transactions")
            row = cursor.fetchone()
            return row[0] if row else 0
        finally:
            conn.close()




