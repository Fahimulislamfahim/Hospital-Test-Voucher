"""
Hospital POS & Billing System - Database Engine
Target Platform: Windows 7 (32-bit/64-bit) | Python 3.8.10 (32-bit)
Database: Local SQLite3 with WAL mode, foreign keys, and atomic transactions.
"""

import sqlite3
import os
import threading
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any

from config import DB_PATH

# Thread lock for safe concurrent operations (e.g. background backup worker & UI)
_db_lock = threading.RLock()


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """
    Establish and configure a connection to SQLite database.
    Enables WAL mode and foreign key constraints for robust reliability on Windows 7.
    """
    conn = sqlite3.connect(db_path, timeout=15.0)
    conn.row_factory = sqlite3.Row
    # Enforce foreign key constraints
    conn.execute("PRAGMA foreign_keys = ON;")
    # WAL mode prevents 'database is locked' errors during concurrent reads/writes
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def init_db(db_path: str = DB_PATH):
    """
    Create the complete database schema and seed initial baseline data
    if tables are empty.
    """
    with _db_lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()

        # 1. Categories Table (e.g., Hematology, Biochemistry, Radiology, Microbiology)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                code TEXT UNIQUE,
                description TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. Diagnostic Tests Table
        # 'code' is the shortcode receptionist types (e.g., '101', 'cbc', 'rbs')
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
                name TEXT NOT NULL,
                code TEXT NOT NULL UNIQUE,
                price REAL NOT NULL DEFAULT 0.0,
                cost REAL NOT NULL DEFAULT 0.0,
                sample_type TEXT DEFAULT 'Blood',
                delivery_time TEXT DEFAULT 'Same Day',
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Indexes for fast test search / autocomplete
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tests_code ON tests(code);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tests_name ON tests(name);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tests_category ON tests(category_id);")

        # 3. Vouchers (Invoices/Bills) Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vouchers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                voucher_no TEXT NOT NULL UNIQUE,
                patient_name TEXT NOT NULL,
                patient_age INTEGER DEFAULT 0,
                patient_gender TEXT DEFAULT 'Male',
                patient_phone TEXT DEFAULT '',
                referred_by TEXT DEFAULT 'Self / General',
                subtotal REAL NOT NULL DEFAULT 0.0,
                discount_type TEXT DEFAULT 'fixed',
                discount_val REAL NOT NULL DEFAULT 0.0,
                discount_amount REAL NOT NULL DEFAULT 0.0,
                total_amount REAL NOT NULL DEFAULT 0.0,
                paid_amount REAL NOT NULL DEFAULT 0.0,
                due_amount REAL NOT NULL DEFAULT 0.0,
                payment_method TEXT DEFAULT 'CASH',
                payment_status TEXT DEFAULT 'PAID',
                remarks TEXT DEFAULT '',
                created_by TEXT DEFAULT 'Reception',
                printed_count INTEGER DEFAULT 0,
                last_printed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vouchers_no ON vouchers(voucher_no);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vouchers_date ON vouchers(created_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vouchers_phone ON vouchers(patient_phone);")

        # 4. Voucher Items (Line items for each diagnostic test in voucher)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS voucher_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                voucher_id INTEGER NOT NULL REFERENCES vouchers(id) ON DELETE CASCADE,
                test_id INTEGER REFERENCES tests(id) ON DELETE SET NULL,
                test_code TEXT NOT NULL,
                test_name TEXT NOT NULL,
                unit_price REAL NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                item_total REAL NOT NULL
            );
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vitems_vid ON voucher_items(voucher_id);")

        # 5. Application Settings Key-Value Store
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)

        conn.commit()

        # Seed initial system configuration and common diagnostic tests
        _seed_default_data(conn)
        conn.close()


def _seed_default_data(conn: sqlite3.Connection):
    """Seed initial settings and common tests so the application is immediately usable."""
    cursor = conn.cursor()

    # Default Settings
    default_settings = [
        ("hospital_name", "City Care Diagnostic & Hospital"),
        ("hospital_tagline", "24/7 Digital Diagnostic Center"),
        ("hospital_address", "Medical College Road, Central Gate"),
        ("hospital_phone", "+880 1711-000000"),
        ("voucher_footer", "Report delivery within 24 hours. Valid with doctor signature."),
        ("printer_name", "DEFAULT"),
        ("paper_size", "80mm"),
        ("currency_symbol", "Tk"),
        ("storage_root_path", r"D:\Hospital_POS_Data"),
        ("backup_local_path", r"D:\Hospital_POS_Data\Backups"),
        ("voucher_pdf_dir", r"D:\Hospital_POS_Data\Vouchers_PDF"),
        ("reports_pdf_dir", r"D:\Hospital_POS_Data\Daily_Reports"),
        ("voucher_json_dir", r"D:\Hospital_POS_Data\Vouchers_JSON"),
        ("usb_drive_label", "HOSPITAL_BAK"),
        ("telegram_bot_token", ""),
        ("telegram_chat_id", ""),
        ("mongo_atlas_uri", ""),
        ("mongo_db_name", "Hospital_POS_Cloud"),
        ("mongo_auto_sync", "1"),
        ("admin_pin", "1234"),
    ]

    for key, val in default_settings:
        cursor.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?);", (key, val))

    # Check if categories already exist
    cursor.execute("SELECT COUNT(*) FROM categories;")
    if cursor.fetchone()[0] == 0:
        categories = [
            ("Hematology", "HEM", "Blood tests and cell counts"),
            ("Biochemistry", "BIO", "Blood chemistry and liver/kidney profiles"),
            ("Clinical Pathology", "CP", "Urine, stool, and fluid analysis"),
            ("Immunology & Serology", "IMM", "Hormones, viral markers, antibodies"),
            ("Radiology & Imaging", "RAD", "X-Ray, Ultrasonography, ECG"),
        ]
        cursor.executemany(
            "INSERT INTO categories (name, code, description) VALUES (?, ?, ?);",
            categories
        )

        # Seed Common Diagnostic Tests with realistic shortcodes
        # Get category IDs
        cursor.execute("SELECT id, code FROM categories;")
        cat_map = {row["code"]: row["id"] for row in cursor.fetchall()}

        tests = [
            # Hematology
            (cat_map.get("HEM"), "Complete Blood Count (CBC with ESR)", "101", 400.0, 120.0, "Blood (EDTA)", "Same Day"),
            (cat_map.get("HEM"), "Hemoglobin (Hb%)", "102", 150.0, 40.0, "Blood (EDTA)", "Same Day"),
            (cat_map.get("HEM"), "Blood Grouping & Rh Factor", "103", 150.0, 30.0, "Blood", "Same Day"),
            (cat_map.get("HEM"), "Platelet Count", "104", 250.0, 60.0, "Blood (EDTA)", "Same Day"),
            # Biochemistry
            (cat_map.get("BIO"), "Random Blood Sugar (RBS)", "201", 120.0, 25.0, "Fluoride Blood", "Same Day"),
            (cat_map.get("BIO"), "Fasting Blood Sugar (FBS)", "202", 120.0, 25.0, "Fluoride Blood", "Same Day"),
            (cat_map.get("BIO"), "HbA1c (Glycated Hemoglobin)", "203", 800.0, 250.0, "Blood (EDTA)", "Same Day"),
            (cat_map.get("BIO"), "Serum Creatinine", "204", 300.0, 80.0, "Serum", "Same Day"),
            (cat_map.get("BIO"), "Lipid Profile (Full)", "205", 900.0, 280.0, "Serum (Fasting)", "Same Day"),
            (cat_map.get("BIO"), "Liver Function Test (LFT/SGPT/SGOT/Bili)", "206", 850.0, 260.0, "Serum", "Same Day"),
            (cat_map.get("BIO"), "Serum Uric Acid", "207", 300.0, 80.0, "Serum", "Same Day"),
            (cat_map.get("BIO"), "Serum Electrolytes (Na/K/Cl)", "208", 750.0, 220.0, "Serum", "Same Day"),
            # Clinical Pathology
            (cat_map.get("CP"), "Urine Routine & Microscopic (R/M/E)", "301", 200.0, 40.0, "Urine", "Same Day"),
            (cat_map.get("CP"), "Stool Routine Examination (R/E)", "302", 180.0, 35.0, "Stool", "Same Day"),
            # Immunology
            (cat_map.get("IMM"), "Thyroid Stimulating Hormone (TSH)", "401", 600.0, 180.0, "Serum", "Next Day"),
            (cat_map.get("IMM"), "HBsAg (Screening)", "402", 350.0, 90.0, "Serum", "Same Day"),
            (cat_map.get("IMM"), "Widal Test (Typhoid)", "403", 300.0, 70.0, "Serum", "Same Day"),
            (cat_map.get("IMM"), "Dengue NS1 Antigen", "404", 500.0, 150.0, "Serum", "Same Day"),
            # Radiology
            (cat_map.get("RAD"), "Electrocardiogram (ECG)", "501", 300.0, 50.0, "Procedure", "Immediate"),
            (cat_map.get("RAD"), "Chest X-Ray (P/A View Digital)", "502", 500.0, 120.0, "Procedure", "Same Day"),
            (cat_map.get("RAD"), "USG of Whole Abdomen", "503", 1200.0, 200.0, "Procedure", "Same Day"),
        ]

        cursor.executemany("""
            INSERT INTO tests 
            (category_id, name, code, price, cost, sample_type, delivery_time)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, tests)

    conn.commit()


# ==============================================================================
# VOUCHER NUMBER GENERATION
# ==============================================================================

def generate_voucher_no(db_path: str = DB_PATH) -> str:
    """
    Generate sequential daily voucher number in format: V-YYYYMMDD-XXXX
    Example: V-20261021-0001
    """
    today_prefix = datetime.now().strftime("V-%Y%m%d-")
    with _db_lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT voucher_no FROM vouchers 
            WHERE voucher_no LIKE ? 
            ORDER BY id DESC LIMIT 1;
        """, (f"{today_prefix}%",))
        row = cursor.fetchone()
        conn.close()

        if row:
            last_no = row["voucher_no"]
            try:
                last_seq = int(last_no.split("-")[-1])
                new_seq = last_seq + 1
            except ValueError:
                new_seq = 1
        else:
            new_seq = 1

        return f"{today_prefix}{new_seq:04d}"


# ==============================================================================
# TEST AUTOCOMPLETE & SEARCH (Zero-Mouse Optimization)
# ==============================================================================

def search_tests(query: str, limit: int = 15, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """
    Fast search for autocomplete.
    Matches exact shortcode, code prefix, or name substring.
    Prioritizes exact code match so receptionists typing '101' get instant match.
    """
    query = query.strip()
    if not query:
        return []

    with _db_lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()

        # Query order: exact code match first, then code prefix, then name match
        sql = """
            SELECT t.id, t.name, t.code, t.price, t.sample_type, t.delivery_time, c.name as category_name,
                   CASE 
                       WHEN LOWER(t.code) = LOWER(?) THEN 1
                       WHEN LOWER(t.code) LIKE LOWER(?) || '%' THEN 2
                       WHEN LOWER(t.name) LIKE LOWER(?) || '%' THEN 3
                       ELSE 4
                   END as match_rank
            FROM tests t
            LEFT JOIN categories c ON t.category_id = c.id
            WHERE t.is_active = 1 AND (
                LOWER(t.code) LIKE '%' || LOWER(?) || '%' OR
                LOWER(t.name) LIKE '%' || LOWER(?) || '%'
            )
            ORDER BY match_rank ASC, t.code ASC
            LIMIT ?;
        """
        cursor.execute(sql, (query, query, query, query, query, limit))
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows


def get_test_by_exact_code(code: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Lookup test by exact code or shortcode (case-insensitive)."""
    with _db_lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.id, t.name, t.code, t.price, t.sample_type, t.delivery_time, c.name as category_name
            FROM tests t
            LEFT JOIN categories c ON t.category_id = c.id
            WHERE t.is_active = 1 AND LOWER(t.code) = LOWER(?);
        """, (code.strip(),))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None


# ==============================================================================
# VOUCHER CRUD & ATOMIC TRANSACTION
# ==============================================================================

def create_voucher(
    patient_data: Dict[str, Any],
    items: List[Dict[str, Any]],
    discount_data: Optional[Dict[str, Any]] = None,
    payment_data: Optional[Dict[str, Any]] = None,
    db_path: str = DB_PATH
) -> Dict[str, Any]:
    """
    Atomically creates a voucher and all associated voucher_items in a single transaction.
    
    patient_data: {'name': str, 'age': int, 'gender': str, 'phone': str, 'referred_by': str}
    items: list of {'test_id': int, 'test_code': str, 'test_name': str, 'price': float, 'quantity': int}
    discount_data: {'type': 'fixed'|'percent', 'value': float}
    payment_data: {'paid_amount': float, 'payment_method': str, 'remarks': str}
    """
    if not items:
        raise ValueError("Cannot create a voucher with zero items.")

    # Calculate Subtotal
    subtotal = sum(float(item["price"]) * int(item.get("quantity", 1)) for item in items)

    # Calculate Discount
    discount_type = (discount_data or {}).get("type", "fixed")
    discount_val = float((discount_data or {}).get("value", 0.0))
    if discount_type == "percent":
        discount_amount = round((subtotal * discount_val) / 100.0, 2)
    else:
        discount_amount = round(discount_val, 2)

    # Total after discount (cannot be negative)
    total_amount = max(0.0, round(subtotal - discount_amount, 2))

    # Payment calculations
    paid_amount = float((payment_data or {}).get("paid_amount", total_amount))
    due_amount = max(0.0, round(total_amount - paid_amount, 2))
    payment_method = (payment_data or {}).get("payment_method", "CASH")
    remarks = (payment_data or {}).get("remarks", "")

    if due_amount == 0.0:
        payment_status = "PAID"
    elif paid_amount == 0.0:
        payment_status = "DUE"
    else:
        payment_status = "PARTIAL"

    with _db_lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()

        try:
            # Begin atomic transaction
            conn.execute("BEGIN IMMEDIATE TRANSACTION;")

            # Generate unique voucher number
            voucher_no = generate_voucher_no(db_path)

            cursor.execute("""
                INSERT INTO vouchers (
                    voucher_no, patient_name, patient_age, patient_gender, patient_phone,
                    referred_by, subtotal, discount_type, discount_val, discount_amount,
                    total_amount, paid_amount, due_amount, payment_method, payment_status,
                    remarks, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                voucher_no,
                patient_data.get("name", "").strip(),
                int(patient_data.get("age", 0) or 0),
                patient_data.get("gender", "Male"),
                patient_data.get("phone", "").strip(),
                patient_data.get("referred_by", "Self / General").strip(),
                subtotal,
                discount_type,
                discount_val,
                discount_amount,
                total_amount,
                paid_amount,
                due_amount,
                payment_method,
                payment_status,
                remarks,
                patient_data.get("created_by", "Reception")
            ))

            voucher_id = cursor.lastrowid

            # Insert Line Items
            for item in items:
                unit_price = float(item["price"])
                qty = int(item.get("quantity", 1))
                item_total = round(unit_price * qty, 2)

                cursor.execute("""
                    INSERT INTO voucher_items (
                        voucher_id, test_id, test_code, test_name, unit_price, quantity, item_total
                    ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """, (
                    voucher_id,
                    item.get("test_id"),
                    item.get("test_code", ""),
                    item.get("test_name", ""),
                    unit_price,
                    qty,
                    item_total
                ))

            conn.commit()

            # Return full constructed voucher record
            return get_voucher_by_id(voucher_id, db_path=db_path)

        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Database error while saving voucher: {e}")
        finally:
            conn.close()


def get_voucher_by_id(voucher_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Fetch complete voucher record including all items by ID."""
    with _db_lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM vouchers WHERE id = ?;", (voucher_id,))
        v_row = cursor.fetchone()
        if not v_row:
            conn.close()
            return None

        voucher = dict(v_row)

        cursor.execute("SELECT * FROM voucher_items WHERE voucher_id = ? ORDER BY id ASC;", (voucher_id,))
        voucher["items"] = [dict(item) for item in cursor.fetchall()]
        conn.close()
        return voucher


def get_voucher_by_no(voucher_no: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Fetch complete voucher record including all items by voucher number."""
    with _db_lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM vouchers WHERE voucher_no = ?;", (voucher_no.strip(),))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return get_voucher_by_id(row["id"], db_path=db_path)


def increment_print_count(voucher_id: int, db_path: str = DB_PATH):
    """Increment printed count and timestamp for audit purposes."""
    with _db_lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE vouchers 
            SET printed_count = printed_count + 1, last_printed_at = CURRENT_TIMESTAMP
            WHERE id = ?;
        """, (voucher_id,))
        conn.commit()
        conn.close()


def get_recent_vouchers(limit: int = 50, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Fetch list of most recent vouchers for billing dashboard table."""
    with _db_lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, voucher_no, patient_name, patient_phone, total_amount, paid_amount,
                   due_amount, payment_status, printed_count, created_at
            FROM vouchers
            ORDER BY id DESC
            LIMIT ?;
        """, (limit,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows


def search_vouchers_advanced(
    query: str = "",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: str = "ALL",
    limit: int = 300,
    db_path: str = DB_PATH
) -> List[Dict[str, Any]]:
    """
    Search and filter vouchers with full search on voucher_no, patient_name,
    patient_phone, referred_by, date range and payment status.
    """
    with _db_lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()

        conditions = []
        params = []

        if query and query.strip():
            q_clean = f"%{query.strip()}%"
            conditions.append("(voucher_no LIKE ? OR patient_name LIKE ? OR patient_phone LIKE ? OR referred_by LIKE ?)")
            params.extend([q_clean, q_clean, q_clean, q_clean])

        if date_from and date_from.strip():
            conditions.append("DATE(created_at) >= DATE(?)")
            params.append(date_from.strip())

        if date_to and date_to.strip():
            conditions.append("DATE(created_at) <= DATE(?)")
            params.append(date_to.strip())

        if status and status.upper() != "ALL":
            conditions.append("payment_status = ?")
            params.append(status.upper())

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query_sql = f"""
            SELECT id, voucher_no, patient_name, patient_age, patient_gender,
                   patient_phone, referred_by, subtotal, discount_type, discount_val,
                   discount_amount, total_amount, paid_amount, due_amount,
                   payment_method, payment_status, printed_count, created_at
            FROM vouchers
            {where_clause}
            ORDER BY id DESC
            LIMIT ?;
        """
        params.append(limit)
        cursor.execute(query_sql, tuple(params))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows


def collect_voucher_due_payment(
    voucher_id: int,
    amount_paid: float,
    payment_method: str = "CASH",
    remarks: str = "",
    db_path: str = DB_PATH
) -> Optional[Dict[str, Any]]:
    """Record due collection on an existing voucher, update paid/due amounts and status."""
    with _db_lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        try:
            conn.execute("BEGIN IMMEDIATE TRANSACTION;")
            cursor.execute("SELECT total_amount, paid_amount, due_amount FROM vouchers WHERE id = ?;", (voucher_id,))
            row = cursor.fetchone()
            if not row:
                conn.rollback()
                conn.close()
                return None

            total = float(row["total_amount"])
            old_paid = float(row["paid_amount"])
            new_paid = round(old_paid + float(amount_paid), 2)
            new_due = max(0.0, round(total - new_paid, 2))

            if new_due == 0.0:
                new_status = "PAID"
            elif new_paid > 0.0:
                new_status = "PARTIAL"
            else:
                new_status = "DUE"

            rem_text = f"Due collected: Tk {amount_paid:.2f} ({payment_method})"
            if remarks.strip():
                rem_text += f" - {remarks.strip()}"

            cursor.execute("""
                UPDATE vouchers
                SET paid_amount = ?, due_amount = ?, payment_status = ?,
                    remarks = CASE 
                        WHEN remarks IS NULL OR remarks = '' THEN ?
                        ELSE remarks || ' | ' || ?
                    END
                WHERE id = ?;
            """, (new_paid, new_due, new_status, rem_text, rem_text, voucher_id))

            conn.commit()
            conn.close()
            return get_voucher_by_id(voucher_id, db_path=db_path)
        except Exception as e:
            conn.rollback()
            conn.close()
            raise RuntimeError(f"Error collecting voucher due: {e}")



# ==============================================================================
# DAILY SUMMARY & REPORTING
# ==============================================================================

def get_daily_summary(date_str: Optional[str] = None, db_path: str = DB_PATH) -> Dict[str, Any]:
    """
    Get aggregated totals for a given date (defaults to today).
    date_str format: 'YYYY-MM-DD'
    """
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    with _db_lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                COUNT(*) as total_vouchers,
                COALESCE(SUM(subtotal), 0.0) as total_subtotal,
                COALESCE(SUM(discount_amount), 0.0) as total_discount,
                COALESCE(SUM(total_amount), 0.0) as total_billed,
                COALESCE(SUM(paid_amount), 0.0) as total_collected,
                COALESCE(SUM(due_amount), 0.0) as total_due
            FROM vouchers
            WHERE DATE(created_at) = DATE(?);
        """, (date_str,))
        summary = dict(cursor.fetchone())

        cursor.execute("""
            SELECT COUNT(vi.id) as total_tests_conducted
            FROM voucher_items vi
            JOIN vouchers v ON vi.voucher_id = v.id
            WHERE DATE(v.created_at) = DATE(?);
        """, (date_str,))
        summary["total_tests"] = cursor.fetchone()["total_tests_conducted"]

        conn.close()
        return summary


# ==============================================================================
# TESTS & CATEGORIES CRUD (For Admin Panel)
# ==============================================================================

def get_all_categories(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Get all test categories."""
    with _db_lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM categories ORDER BY name ASC;")
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows


def add_category(name: str, code: str, description: str = "", db_path: str = DB_PATH) -> int:
    """Add a new category."""
    with _db_lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO categories (name, code, description) VALUES (?, ?, ?);",
            (name.strip(), code.strip().upper(), description.strip())
        )
        conn.commit()
        cat_id = cursor.lastrowid
        conn.close()
        return cat_id


def get_all_tests(active_only: bool = True, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Get all tests with category information."""
    with _db_lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        clause = "WHERE t.is_active = 1" if active_only else ""
        cursor.execute(f"""
            SELECT t.*, c.name as category_name
            FROM tests t
            LEFT JOIN categories c ON t.category_id = c.id
            {clause}
            ORDER BY t.code ASC;
        """)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows


def add_test(test_dict: Dict[str, Any], db_path: str = DB_PATH) -> int:
    """Add a new test."""
    with _db_lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tests (category_id, name, code, price, cost, sample_type, delivery_time)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (
            test_dict.get("category_id"),
            test_dict["name"].strip(),
            test_dict["code"].strip().upper(),
            float(test_dict.get("price", 0.0)),
            float(test_dict.get("cost", 0.0)),
            test_dict.get("sample_type", "Blood").strip(),
            test_dict.get("delivery_time", "Same Day").strip()
        ))
        conn.commit()
        test_id = cursor.lastrowid
        conn.close()
        return test_id


def update_test(test_id: int, test_dict: Dict[str, Any], db_path: str = DB_PATH):
    """Update an existing test."""
    with _db_lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tests SET
                category_id = ?,
                name = ?,
                code = ?,
                price = ?,
                cost = ?,
                sample_type = ?,
                delivery_time = ?,
                is_active = ?
            WHERE id = ?;
        """, (
            test_dict.get("category_id"),
            test_dict["name"].strip(),
            test_dict["code"].strip().upper(),
            float(test_dict.get("price", 0.0)),
            float(test_dict.get("cost", 0.0)),
            test_dict.get("sample_type", "Blood").strip(),
            test_dict.get("delivery_time", "Same Day").strip(),
            int(test_dict.get("is_active", 1)),
            test_id
        ))
        conn.commit()
        conn.close()


def delete_test(test_id: int, db_path: str = DB_PATH):
    """Soft delete test to preserve foreign keys on historic vouchers."""
    with _db_lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE tests SET is_active = 0 WHERE id = ?;", (test_id,))
        conn.commit()
        conn.close()


# ==============================================================================
# SETTINGS MANAGEMENT
# ==============================================================================

def get_setting(key: str, default: str = "", db_path: str = DB_PATH) -> str:
    """Retrieve application setting value."""
    with _db_lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM app_settings WHERE key = ?;", (key,))
        row = cursor.fetchone()
        conn.close()
        return row["value"] if row else default


def set_setting(key: str, value: str, db_path: str = DB_PATH):
    """Store or update application setting."""
    with _db_lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO app_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value;
        """, (key, str(value)))
        conn.commit()
        conn.close()


def get_all_settings(db_path: str = DB_PATH) -> Dict[str, str]:
    """Retrieve dictionary of all application settings."""
    with _db_lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM app_settings;")
        rows = cursor.fetchall()
        conn.close()
        return {r["key"]: r["value"] for r in rows}


# ==============================================================================
# RESTORE & CLOUD MIGRATION UTILITIES
# ==============================================================================

def restore_or_upsert_voucher(
    voucher_data: Dict[str, Any],
    overwrite_existing: bool = False,
    db_path: str = DB_PATH
) -> bool:
    """
    Safely restore or upsert a voucher record from JSON or MongoDB Atlas into SQLite.
    Preserves the original voucher_no, patient details, timestamps, and line items.
    Returns True if inserted/updated, False if skipped because it already exists.
    """
    voucher_no = voucher_data.get("voucher_no")
    if not voucher_no:
        return False

    # Support both flat and nested JSON structures
    p = voucher_data.get("patient", {})
    patient_name = voucher_data.get("patient_name") or p.get("name", "Unknown Patient")
    patient_age = voucher_data.get("patient_age") if "patient_age" in voucher_data else p.get("age", 0)
    try:
        patient_age = int(patient_age)
    except (ValueError, TypeError):
        patient_age = 0
    patient_gender = voucher_data.get("patient_gender") or p.get("gender", "Male")
    patient_phone = voucher_data.get("patient_phone") or p.get("phone", "")
    referred_by = voucher_data.get("referred_by") or p.get("referred_by", "Self / General")

    f = voucher_data.get("financials", {})
    subtotal = float(voucher_data.get("subtotal", f.get("subtotal", 0.0)))
    discount_type = voucher_data.get("discount_type", f.get("discount_type", "fixed"))
    discount_val = float(voucher_data.get("discount_val", f.get("discount_val", 0.0)))
    discount_amount = float(voucher_data.get("discount_amount", f.get("discount_amount", 0.0)))
    total_amount = float(voucher_data.get("total_amount", f.get("total_amount", 0.0)))
    paid_amount = float(voucher_data.get("paid_amount", f.get("paid_amount", 0.0)))
    due_amount = float(voucher_data.get("due_amount", f.get("due_amount", 0.0)))
    payment_method = voucher_data.get("payment_method", f.get("payment_method", "CASH"))
    payment_status = voucher_data.get("payment_status", f.get("payment_status", "PAID"))
    remarks = voucher_data.get("remarks", "")
    created_by = voucher_data.get("created_by", "Reception")
    created_at = voucher_data.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    items = voucher_data.get("items", [])

    with _db_lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        try:
            conn.execute("BEGIN IMMEDIATE TRANSACTION;")
            cursor.execute("SELECT id FROM vouchers WHERE voucher_no = ?;", (voucher_no,))
            existing = cursor.fetchone()

            if existing:
                if not overwrite_existing:
                    conn.rollback()
                    return False
                existing_id = existing["id"]
                cursor.execute("DELETE FROM voucher_items WHERE voucher_id = ?;", (existing_id,))
                cursor.execute("DELETE FROM vouchers WHERE id = ?;", (existing_id,))

            cursor.execute("""
                INSERT INTO vouchers (
                    voucher_no, patient_name, patient_age, patient_gender, patient_phone,
                    referred_by, subtotal, discount_type, discount_val, discount_amount,
                    total_amount, paid_amount, due_amount, payment_method, payment_status,
                    remarks, created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                voucher_no, str(patient_name).strip(), patient_age, str(patient_gender),
                str(patient_phone).strip(), str(referred_by).strip(),
                subtotal, discount_type, discount_val, discount_amount,
                total_amount, paid_amount, due_amount, payment_method, payment_status,
                remarks, created_by, created_at
            ))
            new_vid = cursor.lastrowid

            for it in items:
                cursor.execute("""
                    INSERT INTO voucher_items (
                        voucher_id, test_id, test_code, test_name, unit_price, quantity, item_total
                    ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """, (
                    new_vid,
                    it.get("test_id"),
                    str(it.get("test_code", "")),
                    str(it.get("test_name", "")),
                    float(it.get("unit_price", 0.0)),
                    int(it.get("quantity", 1)),
                    float(it.get("item_total", 0.0))
                ))

            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Failed to restore voucher {voucher_no}: {e}")
        finally:
            conn.close()


def get_all_vouchers_with_items(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Retrieve all vouchers with their complete line items for JSON export and cloud backup."""
    with _db_lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM vouchers ORDER BY id ASC;")
        v_ids = [r["id"] for r in cursor.fetchall()]
        conn.close()

    result = []
    for vid in v_ids:
        v = get_voucher_by_id(vid, db_path=db_path)
        if v:
            result.append(v)
    return result


def get_full_database_dump_data(db_path: str = DB_PATH) -> Dict[str, Any]:
    """Extract complete database as structured dictionaries ready for JSON text serialization."""
    with _db_lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM categories ORDER BY id ASC;")
        categories = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT * FROM tests ORDER BY id ASC;")
        tests = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT key, value FROM app_settings;")
        settings = {r["key"]: r["value"] for r in cursor.fetchall()}
        conn.close()

    vouchers = get_all_vouchers_with_items(db_path=db_path)

    return {
        "format": "HOSPITAL_POS_FULL_JSON_BACKUP",
        "version": "1.0.0",
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_vouchers": len(vouchers),
        "total_tests": len(tests),
        "settings": settings,
        "categories": categories,
        "tests": tests,
        "vouchers": vouchers
    }


# Auto-initialize database schema when database.py is imported or run
if __name__ == "__main__":
    print(f"Initializing database at: {DB_PATH}")
    init_db()
    print("Database schema created and baseline tests seeded successfully.")
    summary = get_daily_summary()
    print("Daily summary test output:", summary)
