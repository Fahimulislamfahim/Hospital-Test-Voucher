"""
Comprehensive Automated Test Suite for Hospital POS & Billing System
Full system testing covering:
1. Core Database CRUD & Seed Data
2. Short Vouchers (Single Test, Exact Discounts, Payment Statuses: Paid in Full, Partial, Due)
3. Long Vouchers (16 Diagnostic Tests, Long Medical Descriptions, Multi-Page Layouts)
4. Print Count Lifecycle & Anti-Skipping Audit (1 -> 2 -> 3 -> 4 -> 5 verification)
5. Thermal ESC/POS Text Formatting, Alignment & Multi-line Word-Wrapping
6. PDF Generation (ReportLab Vector PDF & HTML Fallback)
7. Due Payment Collection & Financial Re-balancing
8. Daily Audit Aggregations & Executive Audit PDF Generation
9. Local JSON Vault Archiving
10. Layer-1 Backup Engine & HWID Cryptographic Licensing
"""

import os
import sys
import shutil
import zipfile
import tempfile
import unittest
from datetime import datetime

# Ensure proper utf-8 output in Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add Hospital_POS directory to python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import database
import printer_engine
import pdf_generator
import data_vault
import backup_manager
import hwid_license


class TestHospitalPOSSystem(unittest.TestCase):

    def setUp(self):
        """Create an isolated temporary environment for each test run."""
        self.test_dir = tempfile.mkdtemp(prefix="hospital_pos_test_")
        self.db_path = os.path.join(self.test_dir, "test_database.db")
        database.init_db(self.db_path)

        # Temporary output directories
        self.voucher_pdf_dir = os.path.join(self.test_dir, "Vouchers_PDF")
        self.reports_pdf_dir = os.path.join(self.test_dir, "Daily_Reports")
        self.voucher_json_dir = os.path.join(self.test_dir, "Vouchers_JSON")
        self.backup_dir = os.path.join(self.test_dir, "Hospital_Backup")
        os.makedirs(self.voucher_pdf_dir, exist_ok=True)
        os.makedirs(self.reports_pdf_dir, exist_ok=True)
        os.makedirs(self.voucher_json_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)

    def tearDown(self):
        """Clean up temporary test artifacts."""
        try:
            shutil.rmtree(self.test_dir, ignore_errors=True)
        except Exception:
            pass

    # =========================================================================
    # 1. DATABASE & INITIAL CONFIGURATION TESTS
    # =========================================================================
    def test_database_initialization_and_seed_data(self):
        """Verify DB initializes with categories, tests, and default settings."""
        cats = database.get_all_categories(db_path=self.db_path)
        self.assertGreater(len(cats), 0, "Default diagnostic categories should be seeded.")

        tests = database.get_all_tests(db_path=self.db_path)
        self.assertGreater(len(tests), 0, "Default diagnostic tests should be seeded.")

        settings = database.get_all_settings(db_path=self.db_path)
        self.assertIn("hospital_name", settings)
        self.assertEqual(settings.get("currency_symbol"), "Tk")

    def test_settings_get_and_set(self):
        """Verify settings key-value persistence."""
        database.set_setting("hospital_name", "Test Specialized Hospital", db_path=self.db_path)
        h_name = database.get_setting("hospital_name", db_path=self.db_path)
        self.assertEqual(h_name, "Test Specialized Hospital")

        # Test fallback default
        val = database.get_setting("non_existent_key", "default_val", db_path=self.db_path)
        self.assertEqual(val, "default_val")

    # =========================================================================
    # 2. SHORT TESTS SUITE (Single Test, Exact Calculations)
    # =========================================================================
    def test_short_voucher_paid_in_full(self):
        """Short test: 1 item, no discount, full cash payment."""
        patient_data = {
            "name": "Rahim Ahmed",
            "age": 28,
            "gender": "Male",
            "phone": "01711223344",
            "referred_by": "Dr. Shamsul Huda"
        }
        items = [
            {"test_id": 1, "test_code": "101", "test_name": "Complete Blood Count (CBC)", "price": 400.0, "quantity": 1}
        ]
        discount_data = {"type": "fixed", "value": 0.0}
        payment_data = {"paid_amount": 400.0, "payment_method": "CASH", "remarks": "Normal"}

        voucher = database.create_voucher(patient_data, items, discount_data, payment_data, db_path=self.db_path)

        self.assertIsNotNone(voucher)
        self.assertEqual(voucher["subtotal"], 400.0)
        self.assertEqual(voucher["discount_amount"], 0.0)
        self.assertEqual(voucher["total_amount"], 400.0)
        self.assertEqual(voucher["paid_amount"], 400.0)
        self.assertEqual(voucher["due_amount"], 0.0)
        self.assertEqual(voucher["payment_status"], "PAID")
        self.assertEqual(voucher["printed_count"], 0)  # Created in DB, not yet printed

    def test_short_voucher_fixed_discount_partial_due(self):
        """Short test: 1 item, fixed Tk 50 discount, partial payment with balance due."""
        patient_data = {
            "name": "Fatima Begum",
            "age": 45,
            "gender": "Female",
            "phone": "01812345678",
            "referred_by": "Self / General"
        }
        items = [
            {"test_id": 2, "test_code": "102", "test_name": "Blood Glucose (RBS)", "price": 150.0, "quantity": 1}
        ]
        discount_data = {"type": "fixed", "value": 50.0}
        payment_data = {"paid_amount": 50.0, "payment_method": "CASH", "remarks": "Will pay rest tomorrow"}

        voucher = database.create_voucher(patient_data, items, discount_data, payment_data, db_path=self.db_path)

        self.assertEqual(voucher["subtotal"], 150.0)
        self.assertEqual(voucher["discount_amount"], 50.0)
        self.assertEqual(voucher["total_amount"], 100.0)
        self.assertEqual(voucher["paid_amount"], 50.0)
        self.assertEqual(voucher["due_amount"], 50.0)
        self.assertEqual(voucher["payment_status"], "PARTIAL")

    def test_short_voucher_percentage_discount_full_due(self):
        """Short test: 1 item, 20% discount, zero paid amount (full DUE)."""
        patient_data = {
            "name": "Kamal Hossain",
            "age": 35,
            "gender": "Male",
            "phone": "01999887766",
            "referred_by": "Prof. Dr. Anwar"
        }
        items = [
            {"test_id": 3, "test_code": "201", "test_name": "Lipid Profile", "price": 1000.0, "quantity": 1}
        ]
        discount_data = {"type": "percent", "value": 20.0}
        payment_data = {"paid_amount": 0.0, "payment_method": "CASH", "remarks": "Pay on delivery"}

        voucher = database.create_voucher(patient_data, items, discount_data, payment_data, db_path=self.db_path)

        self.assertEqual(voucher["subtotal"], 1000.0)
        self.assertEqual(voucher["discount_amount"], 200.0)  # 20% of 1000
        self.assertEqual(voucher["total_amount"], 800.0)
        self.assertEqual(voucher["paid_amount"], 0.0)
        self.assertEqual(voucher["due_amount"], 800.0)
        self.assertEqual(voucher["payment_status"], "DUE")

    # =========================================================================
    # 3. PRINT COUNT & REPRINT BUG VERIFICATION (THE CORE BUG FIX!)
    # =========================================================================
    def test_print_count_strictly_sequential_no_skipping(self):
        """
        CRITICAL TEST FOR REPORTED BUG:
        User reported reprint count jumped 1, 3, 5, 7.
        Verify that original print is 1, and subsequent reprints are strictly 2, 3, 4, 5, 6...
        """
        patient_data = {
            "name": "Audit Test Patient",
            "age": 30,
            "gender": "Male",
            "phone": "01700000000",
            "referred_by": "Self"
        }
        items = [
            {"test_id": 1, "test_code": "101", "test_name": "Complete Blood Count", "price": 400.0, "quantity": 1}
        ]
        voucher = database.create_voucher(patient_data, items, {"type": "fixed", "value": 0}, {"paid_amount": 400.0}, db_path=self.db_path)
        v_id = voucher["id"]

        # Initial state before printing
        self.assertEqual(voucher["printed_count"], 0)

        # --- 1ST PRINT (Creation / Original Print) ---
        res1 = printer_engine.print_voucher_silently(voucher, db_path=self.db_path)
        self.assertTrue(res1["success"])
        self.assertEqual(res1["printed_count"], 1)
        self.assertEqual(voucher["printed_count"], 1)

        v_db1 = database.get_voucher_by_id(v_id, db_path=self.db_path)
        self.assertEqual(v_db1["printed_count"], 1, "First print must set printed_count to 1 in DB.")

        # --- 2ND PRINT (1st Reprint from History) ---
        res2 = printer_engine.print_voucher_silently(v_db1, db_path=self.db_path)
        self.assertTrue(res2["success"])
        self.assertEqual(res2["printed_count"], 2, "1st reprint MUST be 2, not 3!")
        self.assertEqual(v_db1["printed_count"], 2)

        v_db2 = database.get_voucher_by_id(v_id, db_path=self.db_path)
        self.assertEqual(v_db2["printed_count"], 2, "DB count must be exactly 2 after 1st reprint.")

        # --- 3RD PRINT (2nd Reprint from History) ---
        res3 = printer_engine.print_voucher_silently(v_db2, db_path=self.db_path)
        self.assertTrue(res3["success"])
        self.assertEqual(res3["printed_count"], 3, "2nd reprint MUST be 3, not 5!")

        v_db3 = database.get_voucher_by_id(v_id, db_path=self.db_path)
        self.assertEqual(v_db3["printed_count"], 3, "DB count must be exactly 3 after 2nd reprint.")

        # --- 4TH PRINT (3rd Reprint from History) ---
        res4 = printer_engine.print_voucher_silently(v_db3, db_path=self.db_path)
        self.assertTrue(res4["success"])
        self.assertEqual(res4["printed_count"], 4, "3rd reprint MUST be 4, not 7!")

        v_db4 = database.get_voucher_by_id(v_id, db_path=self.db_path)
        self.assertEqual(v_db4["printed_count"], 4, "DB count must be exactly 4 after 3rd reprint.")

        # --- 5TH PRINT (4th Reprint from History) ---
        res5 = printer_engine.print_voucher_silently(v_db4, db_path=self.db_path)
        self.assertTrue(res5["success"])
        self.assertEqual(res5["printed_count"], 5, "4th reprint MUST be 5, not 9!")

        v_db5 = database.get_voucher_by_id(v_id, db_path=self.db_path)
        self.assertEqual(v_db5["printed_count"], 5, "DB count must be exactly 5 after 4th reprint.")

    def test_thermal_receipt_text_print_count_labels(self):
        """Verify that thermal ESC/POS receipt text includes (Original) and (Re-print #N)."""
        voucher = {
            "voucher_no": "V-20261023-0001",
            "created_at": "2026-10-23 10:00:00",
            "patient_name": "Test Patient",
            "patient_age": 40,
            "patient_gender": "Male",
            "patient_phone": "01712345678",
            "referred_by": "Dr. Kamal",
            "subtotal": 500.0,
            "discount_val": 0,
            "discount_type": "fixed",
            "discount_amount": 0,
            "total_amount": 500.0,
            "paid_amount": 500.0,
            "due_amount": 0.0,
            "payment_method": "CASH",
            "payment_status": "PAID",
            "printed_count": 1,
            "items": [{"test_name": "Serum Creatinine", "quantity": 1, "item_total": 500.0}]
        }

        # Original print text
        txt_orig = printer_engine.format_voucher_text(voucher)
        self.assertIn("Print Count: 1 (Original)", txt_orig)

        # Reprint 2
        voucher["printed_count"] = 2
        txt_rep2 = printer_engine.format_voucher_text(voucher)
        self.assertIn("Print Count: 2 (Re-print #2)", txt_rep2)

        # Reprint 3
        voucher["printed_count"] = 3
        txt_rep3 = printer_engine.format_voucher_text(voucher)
        self.assertIn("Print Count: 3 (Re-print #3)", txt_rep3)

    # =========================================================================
    # 4. LONG TESTS SUITE (Many Items, Long Names, Complex Financials)
    # =========================================================================
    def test_long_voucher_with_16_tests_and_ultra_long_names(self):
        """
        Long test: 16 diagnostic tests covering multiple medical departments,
        including very long descriptive test names that require multi-line wrapping.
        """
        patient_data = {
            "name": "Haji Mohammad Shamsuddin Khandaker Chowdhury",
            "age": 67,
            "gender": "Male",
            "phone": "+880 1819-998877",
            "referred_by": "Associate Prof. Dr. M. A. Wahab (FCPS, FRCP, FACC, Cardiology)"
        }

        long_test_names = [
            ("101", "Complete Blood Count (CBC) with ESR & Peripheral Blood Film (PBF)", 500.0),
            ("102", "High Resolution Computed Tomography (HRCT) of Chest with 3D Reconstruction", 4500.0),
            ("103", "Fasting Blood Sugar (FBS) & 2 Hours Post-Prandial (2HPP) Blood Glucose", 300.0),
            ("104", "Glycated Hemoglobin (HbA1c) by High-Performance Liquid Chromatography", 950.0),
            ("105", "Comprehensive Lipid Profile (Cholesterol, Triglycerides, HDL, LDL, VLDL)", 1100.0),
            ("106", "Liver Function Test (Bilirubin Total/Direct, SGPT/ALT, SGOT/AST, Alk Phos)", 1200.0),
            ("107", "Renal Function Panel (Serum Creatinine, Blood Urea Nitrogen, Serum Electrolytes)", 1400.0),
            ("108", "Thyroid Stimulating Hormone (TSH) with Free T3 and Free T4 by ECLIA", 1600.0),
            ("109", "Urine Routine and Microscopic Examination (R/M/E) with Specific Gravity", 250.0),
            ("110", "Digital 12-Lead Electrocardiogram (ECG) with Computerized Rhythm Analysis", 400.0),
            ("111", "2D Transthoracic Echocardiogram with Color Doppler and Tissue Doppler Imaging", 2200.0),
            ("112", "Ultrasonography of Whole Abdomen with Post-Void Residual (PVR) Urine", 1500.0),
            ("113", "Serum Uric Acid by Enzymatic Photometric Method", 450.0),
            ("114", "Serum Calcium (Total & Ionized) and Inorganic Phosphorus", 700.0),
            ("115", "Vitamin D (25-Hydroxyvitamin D Total) Immunoassay", 2200.0),
            ("116", "Serum Ferritin and Total Iron Binding Capacity (TIBC) Panel", 1350.0)
        ]

        items = []
        expected_subtotal = 0.0
        for idx, (code, name, price) in enumerate(long_test_names, 1):
            qty = 1 if idx % 4 != 0 else 2
            item_tot = price * qty
            expected_subtotal += item_tot
            items.append({
                "test_id": idx,
                "test_code": code,
                "test_name": name,
                "price": price,
                "quantity": qty
            })

        discount_data = {"type": "percent", "value": 15.0}  # 15% VIP discount
        expected_discount = round((expected_subtotal * 15.0) / 100.0, 2)
        expected_net = round(expected_subtotal - expected_discount, 2)
        paid_amt = 15000.0
        expected_due = round(expected_net - paid_amt, 2)

        payment_data = {
            "paid_amount": paid_amt,
            "payment_method": "VISA_CARD",
            "remarks": "Executive Health Checkup Package - Ref. Card #9928"
        }

        voucher = database.create_voucher(patient_data, items, discount_data, payment_data, db_path=self.db_path)

        self.assertEqual(len(voucher["items"]), 16)
        self.assertEqual(voucher["subtotal"], expected_subtotal)
        self.assertEqual(voucher["discount_amount"], expected_discount)
        self.assertEqual(voucher["total_amount"], expected_net)
        self.assertEqual(voucher["paid_amount"], paid_amt)
        self.assertEqual(voucher["due_amount"], expected_due)
        self.assertEqual(voucher["payment_status"], "PARTIAL")

        # Test Thermal Text formatting for long items with wrapping
        receipt_text = printer_engine.format_voucher_text(voucher)
        self.assertIn("Haji Mohammad Shamsuddin", receipt_text)
        self.assertIn("High Resolution Computed", receipt_text)
        self.assertIn("NET PAYABLE TOTAL:", receipt_text)
        self.assertIn("BALANCE DUE:", receipt_text)

        # Test ReportLab PDF generation for 16 items (tests multi-page flow & table pagination)
        pdf_path = pdf_generator.generate_voucher_pdf(voucher, output_dir=self.voucher_pdf_dir)
        self.assertTrue(os.path.exists(pdf_path), "Generated PDF file must exist.")
        self.assertGreater(os.path.getsize(pdf_path), 5000, "Multi-item PDF file should have substantial bytes.")

        # Test Local JSON text vault generation
        json_path = data_vault.save_voucher_to_json(voucher, output_dir=self.voucher_json_dir)
        self.assertTrue(os.path.exists(json_path), "JSON text archive must exist.")
        self.assertGreater(os.path.getsize(json_path), 1000)

    # =========================================================================
    # 5. DUE COLLECTION & PAYMENT RE-BALANCING
    # =========================================================================
    def test_due_collection_workflow(self):
        """Test recording due payment, ensuring status flips PARTIAL -> PAID."""
        patient_data = {"name": "Due Patient", "age": 25, "gender": "Male", "phone": "01711111111"}
        items = [{"test_id": 1, "test_code": "101", "test_name": "Test Item", "price": 1000.0, "quantity": 1}]
        voucher = database.create_voucher(patient_data, items, {"type": "fixed", "value": 0}, {"paid_amount": 400.0}, db_path=self.db_path)

        v_id = voucher["id"]
        self.assertEqual(voucher["due_amount"], 600.0)
        self.assertEqual(voucher["payment_status"], "PARTIAL")

        # Collect partial Tk 200
        v_updated1 = database.collect_voucher_due_payment(v_id, 200.0, payment_method="bKash", remarks="Partial due", db_path=self.db_path)
        self.assertEqual(v_updated1["paid_amount"], 600.0)
        self.assertEqual(v_updated1["due_amount"], 400.0)
        self.assertEqual(v_updated1["payment_status"], "PARTIAL")

        # Collect remaining Tk 400
        v_updated2 = database.collect_voucher_due_payment(v_id, 400.0, payment_method="CASH", remarks="Final due paid", db_path=self.db_path)
        self.assertEqual(v_updated2["paid_amount"], 1000.0)
        self.assertEqual(v_updated2["due_amount"], 0.0)
        self.assertEqual(v_updated2["payment_status"], "PAID")

    # =========================================================================
    # 6. DAILY FINANCIAL AUDIT & REVENUE RECONCILIATION
    # =========================================================================
    def test_daily_summary_and_audit_pdf_generation(self):
        """Test daily summary calculations and A4 Executive Audit Report PDF generation."""
        today_str = datetime.now().strftime("%Y-%m-%d")

        # Create 2 diverse vouchers today
        p1 = {"name": "Patient One", "age": 20, "gender": "Male", "phone": "0171"}
        i1 = [{"test_id": 1, "test_code": "101", "test_name": "Test A", "price": 500.0, "quantity": 1}]
        database.create_voucher(p1, i1, {"type": "fixed", "value": 50}, {"paid_amount": 450.0}, db_path=self.db_path)

        p2 = {"name": "Patient Two", "age": 30, "gender": "Female", "phone": "0172"}
        i2 = [{"test_id": 2, "test_code": "102", "test_name": "Test B", "price": 1000.0, "quantity": 1}]
        database.create_voucher(p2, i2, {"type": "percent", "value": 10}, {"paid_amount": 500.0}, db_path=self.db_path)

        summary = database.get_daily_summary(today_str, db_path=self.db_path)
        self.assertEqual(summary["total_vouchers"], 2)
        self.assertEqual(summary["total_tests"], 2)
        self.assertEqual(summary["total_subtotal"], 1500.0)
        self.assertEqual(summary["total_discount"], 150.0)
        self.assertEqual(summary["total_billed"], 1350.0)
        self.assertEqual(summary["total_collected"], 950.0)
        self.assertEqual(summary["total_due"], 400.0)

        # Generate Daily Audit PDF
        audit_pdf = pdf_generator.generate_daily_audit_pdf(today_str, output_dir=self.reports_pdf_dir, db_path=self.db_path)
        self.assertTrue(os.path.exists(audit_pdf))
        self.assertGreater(os.path.getsize(audit_pdf), 3000)

    # =========================================================================
    # 7. BACKUP MANAGER & HARDWARE LICENSE INTEGRITY
    # =========================================================================
    def test_backup_zip_creation_and_integrity(self):
        """Test creating an atomic ZIP backup and verifying its zip contents."""
        backup_zip = backup_manager.execute_layer1_local_backup(target_dir=self.backup_dir, source_db_path=self.db_path)
        self.assertIsNotNone(backup_zip)
        self.assertTrue(os.path.exists(backup_zip))
        self.assertTrue(backup_zip.endswith(".zip"))

        # Verify ZIP archive structure
        with zipfile.ZipFile(backup_zip, "r") as zf:
            namelist = zf.namelist()
            self.assertIn("database.db", namelist)
            self.assertIn("backup_info.txt", namelist)
            db_bytes = zf.read("database.db")
            self.assertGreater(len(db_bytes), 0)

    def test_hwid_license_cryptographic_engine(self):
        """Verify Hardware ID extraction and pure-Python encryption/decryption round-trip."""
        hwid = hwid_license.get_hardware_id()
        self.assertIsInstance(hwid, str)
        self.assertTrue(hwid.startswith("HOSP-"))

        # Roundtrip payload encryption/decryption
        payload = {
            "hwid": hwid,
            "license_type": "LIFETIME_COMMERCIAL",
            "activated_at": datetime.now().isoformat(),
            "hospital_name": "City Care Diagnostic Center"
        }
        enc_bytes = hwid_license._encrypt_payload(payload)
        self.assertTrue(enc_bytes.startswith(b"HOSP_SEC::"))

        dec_payload = hwid_license._decrypt_payload(enc_bytes)
        self.assertEqual(dec_payload["hwid"], hwid)
        self.assertEqual(dec_payload["license_type"], "LIFETIME_COMMERCIAL")


if __name__ == "__main__":
    unittest.main()
