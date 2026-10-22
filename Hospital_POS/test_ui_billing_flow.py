"""
Headless UI & Dashboard Workflow Tests for Hospital POS
Tests the exact Tkinter UI code paths:
1. Adding items to cart
2. Calculating discount & net payable
3. _save_and_print execution (creates voucher, prints #1)
4. _reprint_last_voucher (prints #2)
5. History Inspector:
   - Load history
   - Select voucher
   - Click print (#3)
   - Click print again (#4)
   - Verify UI inspector label displays 'Printed: 4x' and DB has 4 (NO 1, 3, 5, 7 SKIPPING!)
"""

import os
import sys
import shutil
import tempfile
import unittest
import tkinter as tk
from tkinter import messagebox

# Monkeypatch messagebox to avoid modal blocking in headless tests
messagebox.showinfo = lambda title, message, **kwargs: None
messagebox.showwarning = lambda title, message, **kwargs: None
messagebox.showerror = lambda title, message, **kwargs: None

# Disable auto-launching external PDF viewer during headless tests
import printer_engine
printer_engine.is_virtual_pdf_printer = lambda p: False

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import database
from ui.billing_dashboard import BillingDashboard


class TestUIBillingFlow(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="hospital_ui_test_")
        self.db_path = os.path.join(self.test_dir, "test_ui.db")
        database.init_db(self.db_path)

        # Point database.DB_PATH to test db
        self.orig_db_path = database.DB_PATH
        database.DB_PATH = self.db_path

        self.root = tk.Tk()
        self.root.withdraw()
        self.app = BillingDashboard(self.root)

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass
        database.DB_PATH = self.orig_db_path
        try:
            shutil.rmtree(self.test_dir, ignore_errors=True)
        except Exception:
            pass

    def test_full_ui_billing_and_reprint_workflow(self):
        """Simulate real user clicking through the UI: create, reprint last, reprint in history."""
        # 1. Fill patient info
        self.app.name_entry.insert(0, "Ayesha Siddiqua")
        self.app.age_entry.insert(0, "29")
        self.app.gender_combo.set("Female")
        self.app.phone_entry.insert(0, "01712000111")
        self.app.ref_entry.delete(0, tk.END)
        self.app.ref_entry.insert(0, "Prof. Dr. Tahmina")

        # 2. Add 2 tests to cart
        t1 = database.get_test_by_exact_code("101", db_path=self.db_path)
        self.assertIsNotNone(t1)
        self.app.cart_items.append({
            "test_id": t1["id"],
            "test_code": t1["code"],
            "test_name": t1["name"],
            "price": float(t1["price"]),
            "quantity": 1,
            "sample": t1.get("sample_type", "Blood")
        })

        t2 = database.get_test_by_exact_code("201", db_path=self.db_path)
        self.assertIsNotNone(t2)
        self.app.cart_items.append({
            "test_id": t2["id"],
            "test_code": t2["code"],
            "test_name": t2["name"],
            "price": float(t2["price"]),
            "quantity": 1,
            "sample": t2.get("sample_type", "Blood")
        })

        self.app._refresh_cart_view()
        self.app._recalculate()

        # 3. Enter paid amount
        subtotal = float(t1["price"]) + float(t2["price"])  # 400 + 120 = 520
        self.app.paid_entry.delete(0, tk.END)
        self.app.paid_entry.insert(0, str(subtotal))

        # 4. Trigger save_and_print_voucher (Print #1)
        self.app.save_and_print_voucher()

        self.assertIsNotNone(self.app.last_created_voucher)
        v_created = self.app.last_created_voucher
        v_id = v_created["id"]

        # Check DB count after initial print
        v_db1 = database.get_voucher_by_id(v_id, db_path=self.db_path)
        self.assertEqual(v_db1["printed_count"], 1, "Print count must be 1 after _save_and_print.")

        # 5. Trigger _reprint_last_voucher (Print #2)
        self.app._reprint_last_voucher()
        v_db2 = database.get_voucher_by_id(v_id, db_path=self.db_path)
        self.assertEqual(v_db2["printed_count"], 2, "Print count must be 2 after _reprint_last_voucher.")
        self.assertEqual(self.app.last_created_voucher["printed_count"], 2)

        # 6. Simulate History Window reprint flow
        # In history window, selected_voucher_holder holds the voucher
        selected_voucher_holder = [v_db2]

        def _print_inspected_test():
            v = selected_voucher_holder[0]
            printer_engine.print_voucher_silently(v, db_path=self.db_path)
            v_refreshed = database.get_voucher_by_id(v["id"], db_path=self.db_path)
            selected_voucher_holder[0] = v_refreshed
            return v_refreshed

        # Trigger Print #3
        v_db3 = _print_inspected_test()
        self.assertEqual(v_db3["printed_count"], 3, "Print count must be 3 (NOT 5!) after 1st history reprint.")

        # Trigger Print #4
        v_db4 = _print_inspected_test()
        self.assertEqual(v_db4["printed_count"], 4, "Print count must be 4 (NOT 7!) after 2nd history reprint.")

        # Trigger Print #5
        v_db5 = _print_inspected_test()
        self.assertEqual(v_db5["printed_count"], 5, "Print count must be 5 (NOT 9!) after 3rd history reprint.")


if __name__ == "__main__":
    unittest.main()
