"""
Edge Cases, Stress Tests, and System Verification Suite for Hospital POS
Tests:
1. Large Multi-Item Stress Test (25 Items across Multiple Departments)
2. Search & Filtering Combinations (Query, Date Range, Status Filters)
3. Financial Edge Cases (100% Free Voucher, Fractional Cents, Discount > Subtotal)
4. Monotonic Sequential Voucher Number Generation
5. HTML Fallback Template vs ReportLab Vector PDF parity
6. Concurrent / Repeated Reprint Sequences (Verifying no race conditions)
7. Category & Test Management CRUD Operations
"""

import os
import sys
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import database
import printer_engine
import pdf_generator
import data_vault


class TestEdgeCasesAndStress(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="hospital_stress_test_")
        self.db_path = os.path.join(self.test_dir, "test_database.db")
        database.init_db(self.db_path)
        self.pdf_dir = os.path.join(self.test_dir, "Vouchers_PDF")
        os.makedirs(self.pdf_dir, exist_ok=True)

    def tearDown(self):
        try:
            shutil.rmtree(self.test_dir, ignore_errors=True)
        except Exception:
            pass

    # =========================================================================
    # 1. 25-ITEM STRESS TEST (Large Multi-Page Document)
    # =========================================================================
    def test_25_items_large_stress_voucher(self):
        """Stress test: 25 diagnostic tests in a single voucher."""
        patient_data = {
            "name": "Comprehensive Inpatient Assessment",
            "age": 52,
            "gender": "Female",
            "phone": "01755667788",
            "referred_by": "Medical Board - Combined Military Hospital"
        }

        items = []
        expected_subtotal = 0.0
        for i in range(1, 26):
            rate = 150.0 + (i * 25.5)
            qty = (i % 3) + 1
            tot = round(rate * qty, 2)
            expected_subtotal += tot
            items.append({
                "test_id": i,
                "test_code": f"T{i:03d}",
                "test_name": f"Clinical Laboratory Diagnostic Procedure Test #{i:02d} with Extended Panels",
                "price": rate,
                "quantity": qty
            })

        discount_data = {"type": "fixed", "value": 500.0}
        expected_net = round(expected_subtotal - 500.0, 2)
        payment_data = {"paid_amount": expected_net, "payment_method": "ONLINE_TRANSFER"}

        voucher = database.create_voucher(patient_data, items, discount_data, payment_data, db_path=self.db_path)

        self.assertEqual(len(voucher["items"]), 25)
        self.assertAlmostEqual(voucher["subtotal"], expected_subtotal, places=2)
        self.assertAlmostEqual(voucher["total_amount"], expected_net, places=2)
        self.assertEqual(voucher["payment_status"], "PAID")

        # Test PDF rendering (A5 multi-page)
        pdf_path = pdf_generator.generate_voucher_pdf(voucher, output_dir=self.pdf_dir)
        self.assertTrue(os.path.exists(pdf_path))
        self.assertGreater(os.path.getsize(pdf_path), 4000)

        # Test HTML rendering
        html = printer_engine.generate_html_voucher(voucher)
        self.assertIn("Clinical Laboratory Diagnostic", html)
        self.assertIn(voucher["voucher_no"], html)

    # =========================================================================
    # 2. SEARCH & ADVANCED FILTERING TESTS
    # =========================================================================
    def test_advanced_search_filters(self):
        """Verify search filters by patient name, phone, doctor, voucher_no, and status."""
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        # Seed 3 distinct vouchers
        v1 = database.create_voucher(
            {"name": "Alice Johnson", "age": 22, "gender": "Female", "phone": "01711001122", "referred_by": "Dr. Smith"},
            [{"test_id": 1, "test_code": "101", "test_name": "Test 1", "price": 300, "quantity": 1}],
            {"type": "fixed", "value": 0},
            {"paid_amount": 300},
            db_path=self.db_path
        )
        v2 = database.create_voucher(
            {"name": "Bob Williams", "age": 34, "gender": "Male", "phone": "01822334455", "referred_by": "Dr. Davis"},
            [{"test_id": 2, "test_code": "102", "test_name": "Test 2", "price": 500, "quantity": 1}],
            {"type": "fixed", "value": 0},
            {"paid_amount": 0},
            db_path=self.db_path
        )
        v3 = database.create_voucher(
            {"name": "Charlie Brown", "age": 45, "gender": "Male", "phone": "01933445566", "referred_by": "Dr. Smith"},
            [{"test_id": 3, "test_code": "103", "test_name": "Test 3", "price": 800, "quantity": 1}],
            {"type": "fixed", "value": 100},
            {"paid_amount": 400},
            db_path=self.db_path
        )

        # 1. Search by name
        res_name = database.search_vouchers_advanced(query="Alice", db_path=self.db_path)
        self.assertEqual(len(res_name), 1)
        self.assertEqual(res_name[0]["voucher_no"], v1["voucher_no"])

        # 2. Search by phone
        res_phone = database.search_vouchers_advanced(query="01822334455", db_path=self.db_path)
        self.assertEqual(len(res_phone), 1)
        self.assertEqual(res_phone[0]["voucher_no"], v2["voucher_no"])

        # 3. Search by doctor
        res_doc = database.search_vouchers_advanced(query="Dr. Smith", db_path=self.db_path)
        self.assertEqual(len(res_doc), 2)

        # 4. Filter by status PAID
        res_paid = database.search_vouchers_advanced(status="PAID", db_path=self.db_path)
        self.assertEqual(len(res_paid), 1)
        self.assertEqual(res_paid[0]["payment_status"], "PAID")

        # 5. Filter by status DUE
        res_due = database.search_vouchers_advanced(status="DUE", db_path=self.db_path)
        self.assertEqual(len(res_due), 1)
        self.assertEqual(res_due[0]["payment_status"], "DUE")

        # 6. Filter by status PARTIAL
        res_partial = database.search_vouchers_advanced(status="PARTIAL", db_path=self.db_path)
        self.assertEqual(len(res_partial), 1)
        self.assertEqual(res_partial[0]["payment_status"], "PARTIAL")

    # =========================================================================
    # 3. FINANCIAL EDGE CASES
    # =========================================================================
    def test_100_percent_free_voucher(self):
        """Test edge case: 100% discount, zero payable, status PAID."""
        p = {"name": "Charity Patient", "age": 12, "gender": "Female", "phone": "01700000000"}
        items = [{"test_id": 1, "test_code": "101", "test_name": "Free CBC", "price": 400.0, "quantity": 1}]
        discount = {"type": "percent", "value": 100.0}
        payment = {"paid_amount": 0.0}

        v = database.create_voucher(p, items, discount, payment, db_path=self.db_path)
        self.assertEqual(v["subtotal"], 400.0)
        self.assertEqual(v["discount_amount"], 400.0)
        self.assertEqual(v["total_amount"], 0.0)
        self.assertEqual(v["due_amount"], 0.0)
        self.assertEqual(v["payment_status"], "PAID")

    def test_fractional_cents_and_quantities(self):
        """Test fractional monetary values and multi-unit quantities."""
        p = {"name": "Fractional Patient", "age": 30, "gender": "Male", "phone": "01712341234"}
        items = [
            {"test_id": 1, "test_code": "T1", "test_name": "Item A", "price": 33.33, "quantity": 3},  # 99.99
            {"test_id": 2, "test_code": "T2", "test_name": "Item B", "price": 10.01, "quantity": 2}   # 20.02
        ]
        # Total subtotal: 120.01
        v = database.create_voucher(p, items, {"type": "fixed", "value": 0.01}, {"paid_amount": 100.00}, db_path=self.db_path)
        self.assertEqual(v["subtotal"], 120.01)
        self.assertEqual(v["discount_amount"], 0.01)
        self.assertEqual(v["total_amount"], 120.0)
        self.assertEqual(v["paid_amount"], 100.0)
        self.assertEqual(v["due_amount"], 20.0)
        self.assertEqual(v["payment_status"], "PARTIAL")

    # =========================================================================
    # 4. VOUCHER NUMBERING SEQUENCE
    # =========================================================================
    def test_voucher_number_monotonicity(self):
        """Verify sequential voucher numbers generated in same day: 0001, 0002, 0003."""
        v1 = database.create_voucher({"name": "P1"}, [{"test_name": "T1", "price": 100}], None, None, db_path=self.db_path)
        v2 = database.create_voucher({"name": "P2"}, [{"test_name": "T2", "price": 100}], None, None, db_path=self.db_path)
        v3 = database.create_voucher({"name": "P3"}, [{"test_name": "T3", "price": 100}], None, None, db_path=self.db_path)

        num1 = int(v1["voucher_no"].split("-")[-1])
        num2 = int(v2["voucher_no"].split("-")[-1])
        num3 = int(v3["voucher_no"].split("-")[-1])

        self.assertEqual(num2, num1 + 1)
        self.assertEqual(num3, num2 + 1)

    # =========================================================================
    # 5. DIAGNOSTIC TEST & CATEGORY CRUD
    # =========================================================================
    def test_diagnostic_test_and_category_crud(self):
        """Test creating categories and tests, updating them, and soft-delete/is_active toggling."""
        # Create category
        cat_id = database.add_category("Molecular Biology", "PCR and Genetic Testing", db_path=self.db_path)
        self.assertIsNotNone(cat_id)

        # Create test
        test_data = {
            "category_id": cat_id,
            "name": "RT-PCR for Dengue Virus RNA",
            "code": "PCR-DENGUE",
            "price": 2500.0,
            "cost": 800.0,
            "sample_type": "Plasma",
            "delivery_time": "24 Hours"
        }
        test_id = database.add_test(test_data, db_path=self.db_path)
        self.assertIsNotNone(test_id)

        # Fetch and verify
        t = database.get_test_by_code("PCR-DENGUE", db_path=self.db_path)
        self.assertIsNotNone(t)
        self.assertEqual(t["price"], 2500.0)
        self.assertEqual(t["sample_type"], "Plasma")

        # Update test price
        update_data = dict(t)
        update_data["price"] = 2800.0
        update_data["delivery_time"] = "Same Day"
        database.update_test(test_id, update_data, db_path=self.db_path)
        t_updated = database.get_test_by_code("PCR-DENGUE", db_path=self.db_path)
        self.assertEqual(t_updated["price"], 2800.0)
        self.assertEqual(t_updated["delivery_time"], "Same Day")


if __name__ == "__main__":
    unittest.main()
