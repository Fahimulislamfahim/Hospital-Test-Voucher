"""
Hospital POS & Billing System - Admin Panel & Management UI
Target Platform: Windows 7 (32-bit/64-bit) | Python 3.8.10 (32-bit)

Modules included:
1. PIN Authentication
2. Diagnostic Test Catalog Management (Add/Edit/Delete Tests & Shortcodes)
3. Daily Sales & Audit Reports
4. System & Printer Configuration
5. 3-Layer Backup Trigger & Hardware License Details
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from typing import Optional, Callable

import database
import printer_engine
import backup_manager
import hwid_license
import pdf_generator
import data_vault
from config import (
    APP_NAME,
    DEFAULT_STORAGE_ROOT,
    DEFAULT_BACKUP_DIR,
    DEFAULT_VOUCHER_PDF_DIR,
    DEFAULT_REPORTS_PDF_DIR,
    DEFAULT_VOUCHER_JSON_DIR,
    DEFAULT_MONGO_URI,
    DEFAULT_MONGO_DB
)


class AdminPanelWindow:
    def __init__(self, parent: tk.Tk, on_settings_updated: Optional[Callable] = None):
        self.parent = parent
        self.on_settings_updated = on_settings_updated

        self.win = tk.Toplevel(parent)
        self.win.title(f"{APP_NAME} - Administrative Console")
        self.win.geometry("900x640")
        self.win.minsize(800, 560)
        self.win.configure(bg="#f8fafc")

        # Check PIN authentication before revealing settings
        self.is_authenticated = False
        self._prompt_admin_pin()

    # ==========================================================================
    # PIN SECURITY PROMPT
    # ==========================================================================

    def _prompt_admin_pin(self):
        auth_frame = tk.Frame(self.win, bg="#f8fafc", padx=40, pady=60)
        auth_frame.pack(expand=True)

        tk.Label(
            auth_frame,
            text="🔒 Admin Authorization",
            font=("Segoe UI", 16, "bold"),
            bg="#f8fafc",
            fg="#1e293b"
        ).pack(pady=(0, 6))

        tk.Label(
            auth_frame,
            text="Please enter Admin Security PIN to access management:",
            font=("Segoe UI", 10),
            bg="#f8fafc",
            fg="#64748b"
        ).pack(pady=(0, 16))

        pin_box = tk.Frame(auth_frame, bg="#f8fafc")
        pin_box.pack(pady=(0, 16))

        self.pin_entry = tk.Entry(
            pin_box,
            show="*",
            font=("Segoe UI", 16, "bold"),
            width=10,
            justify=tk.CENTER,
            bd=1,
            relief=tk.SOLID
        )
        self.pin_entry.pack(ipady=4)
        self.pin_entry.focus_set()
        self.pin_entry.bind("<Return>", lambda e: self._verify_pin(auth_frame))

        btn = tk.Button(
            auth_frame,
            text="Unlock Console",
            font=("Segoe UI", 11, "bold"),
            bg="#0d9488",
            fg="#ffffff",
            activebackground="#0f766e",
            relief=tk.FLAT,
            padx=16,
            pady=6,
            command=lambda: self._verify_pin(auth_frame)
        )
        btn.pack()

        # Hint for default pin
        tk.Label(
            auth_frame,
            text="(Default Security PIN: 1234)",
            font=("Segoe UI", 8, "italic"),
            bg="#f8fafc",
            fg="#94a3b8"
        ).pack(pady=(12, 0))

    def _verify_pin(self, auth_frame: tk.Frame):
        entered_pin = self.pin_entry.get().strip()
        actual_pin = database.get_setting("admin_pin", "1234")

        if entered_pin == actual_pin:
            self.is_authenticated = True
            auth_frame.destroy()
            self._build_admin_interface()
        else:
            messagebox.showerror("Access Denied", "Incorrect Security PIN. Please try again.")
            self.pin_entry.delete(0, tk.END)

    # ==========================================================================
    # MAIN ADMIN TABS
    # ==========================================================================

    def _build_admin_interface(self):
        # Header banner
        header = tk.Frame(self.win, bg="#0f172a", height=48, padx=16)
        header.pack(fill=tk.X)

        tk.Label(
            header,
            text="🛡️ Administrative Console & Reports",
            font=("Segoe UI", 12, "bold"),
            fg="#38bdf8",
            bg="#0f172a"
        ).pack(side=tk.LEFT, pady=12)

        # Tabbed Notebook
        notebook = ttk.Notebook(self.win)
        notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        # Tab 1: Diagnostic Tests Catalog
        tests_tab = ttk.Frame(notebook)
        notebook.add(tests_tab, text=" 🧪 Diagnostic Tests ")
        self._build_tests_tab(tests_tab)

        # Tab 2: Daily Reports & Analytics
        reports_tab = ttk.Frame(notebook)
        notebook.add(reports_tab, text=" 📊 Daily Reports ")
        self._build_reports_tab(reports_tab)

        # Tab 3: System Settings & Printing
        settings_tab = ttk.Frame(notebook)
        notebook.add(settings_tab, text=" ⚙️ Settings & Printer ")
        self._build_settings_tab(settings_tab)

        # Tab 4: Backup & Disaster Recovery
        backup_tab = ttk.Frame(notebook)
        notebook.add(backup_tab, text=" 💾 3-Layer Backup ")
        self._build_backup_tab(backup_tab)

        # Tab 5: License & HWID
        license_tab = ttk.Frame(notebook)
        notebook.add(license_tab, text=" 🔒 License & HWID ")
        self._build_license_tab(license_tab)

    # ==========================================================================
    # TAB 1: DIAGNOSTIC TESTS MANAGEMENT
    # ==========================================================================

    def _build_tests_tab(self, parent):
        top_bar = tk.Frame(parent, bg="#f8fafc", pady=6)
        top_bar.pack(fill=tk.X)

        tk.Button(
            top_bar,
            text="➕ Add New Test",
            font=("Segoe UI", 9, "bold"),
            bg="#0d9488",
            fg="#ffffff",
            relief=tk.FLAT,
            padx=10,
            pady=4,
            command=self._show_add_test_dialog
        ).pack(side=tk.LEFT, padx=6)

        tk.Button(
            top_bar,
            text="✏️ Edit Selected",
            font=("Segoe UI", 9),
            bg="#e2e8f0",
            relief=tk.FLAT,
            padx=10,
            pady=4,
            command=self._show_edit_test_dialog
        ).pack(side=tk.LEFT, padx=6)

        tk.Button(
            top_bar,
            text="🗑️ Delete Selected",
            font=("Segoe UI", 9),
            bg="#fee2e2",
            fg="#dc2626",
            relief=tk.FLAT,
            padx=10,
            pady=4,
            command=self._delete_selected_test
        ).pack(side=tk.LEFT, padx=6)

        tk.Button(
            top_bar,
            text="🔄 Refresh",
            font=("Segoe UI", 9),
            bg="#f1f5f9",
            relief=tk.FLAT,
            padx=8,
            pady=4,
            command=self._refresh_tests_tree
        ).pack(side=tk.RIGHT, padx=6)

        # Live Search / Filter Bar
        search_bar = tk.Frame(parent, bg="#f8fafc", pady=4, padx=6)
        search_bar.pack(fill=tk.X)

        tk.Label(
            search_bar,
            text="🔍 Filter:",
            font=("Segoe UI", 9, "bold"),
            bg="#f8fafc",
            fg="#0f766e"
        ).pack(side=tk.LEFT)

        self.tests_search_var = tk.StringVar()
        self.tests_search_var.trace("w", lambda *a: self._filter_tests_tree())
        tests_search_e = tk.Entry(
            search_bar,
            textvariable=self.tests_search_var,
            font=("Segoe UI", 10),
            bd=1,
            relief=tk.SOLID
        )
        tests_search_e.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 8), ipady=3)

        tk.Label(
            search_bar,
            text="(type code, name, or category to filter)",
            font=("Segoe UI", 8),
            bg="#f8fafc",
            fg="#64748b"
        ).pack(side=tk.LEFT)

        self._all_tests_cache: list = []  # cache for filtering

        # Wrap tree+scrollbar so vertical pack layout of the tab is not broken
        tree_frame = tk.Frame(parent, bg="#f8fafc")
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=4)

        cols = ("id", "code", "name", "cat", "price", "cost", "sample", "delivery")
        self.tests_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")

        self.tests_tree.heading("id", text="ID")
        self.tests_tree.heading("code", text="Shortcode")
        self.tests_tree.heading("name", text="Test Description")
        self.tests_tree.heading("cat", text="Category")
        self.tests_tree.heading("price", text="Price (Tk)")
        self.tests_tree.heading("cost", text="Cost (Tk)")
        self.tests_tree.heading("sample", text="Sample")
        self.tests_tree.heading("delivery", text="Delivery Time")

        self.tests_tree.column("id", width=40, anchor=tk.CENTER)
        self.tests_tree.column("code", width=80, anchor=tk.CENTER)
        self.tests_tree.column("name", width=260, anchor=tk.W)
        self.tests_tree.column("cat", width=130, anchor=tk.W)
        self.tests_tree.column("price", width=80, anchor=tk.E)
        self.tests_tree.column("cost", width=70, anchor=tk.E)
        self.tests_tree.column("sample", width=100, anchor=tk.CENTER)
        self.tests_tree.column("delivery", width=100, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tests_tree.yview)
        self.tests_tree.configure(yscrollcommand=scrollbar.set)

        self.tests_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._refresh_tests_tree()

    def _refresh_tests_tree(self):
        self._all_tests_cache = database.get_all_tests(active_only=True)
        self._populate_tests_tree(self._all_tests_cache)

    def _filter_tests_tree(self):
        query = self.tests_search_var.get().strip().lower()
        if not query:
            self._populate_tests_tree(self._all_tests_cache)
            return
        filtered = [
            t for t in self._all_tests_cache
            if query in t["code"].lower()
            or query in t["name"].lower()
            or query in t.get("category_name", "").lower()
        ]
        self._populate_tests_tree(filtered)

    def _populate_tests_tree(self, tests: list):
        self.tests_tree.delete(*self.tests_tree.get_children())
        for t in tests:
            self.tests_tree.insert("", tk.END, values=(
                t["id"],
                t["code"],
                t["name"],
                t.get("category_name", "General"),
                f"{t['price']:.2f}",
                f"{t['cost']:.2f}",
                t.get("sample_type", "Blood"),
                t.get("delivery_time", "Same Day")
            ))

    def _show_add_test_dialog(self, test_to_edit: Optional[dict] = None):
        dialog = tk.Toplevel(self.win)
        dialog.title("Edit Test" if test_to_edit else "Add New Test")
        dialog.geometry("450x420")
        dialog.resizable(False, False)
        dialog.configure(bg="#f8fafc")

        categories = database.get_all_categories()
        cat_map = {c["name"]: c["id"] for c in categories}
        cat_names = list(cat_map.keys())

        # Form Fields
        f = tk.Frame(dialog, bg="#f8fafc", padx=20, pady=16)
        f.pack(fill=tk.BOTH, expand=True)

        # Shortcode
        tk.Label(f, text="Shortcode * (e.g. 101, cbc):", bg="#f8fafc", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        code_e = tk.Entry(f, font=("Segoe UI", 10), bd=1, relief=tk.SOLID)
        code_e.pack(fill=tk.X, pady=(2, 8), ipady=2)
        if test_to_edit:
            code_e.insert(0, test_to_edit["code"])

        # Test Name
        tk.Label(f, text="Test Name *:", bg="#f8fafc", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        name_e = tk.Entry(f, font=("Segoe UI", 10), bd=1, relief=tk.SOLID)
        name_e.pack(fill=tk.X, pady=(2, 8), ipady=2)
        if test_to_edit:
            name_e.insert(0, test_to_edit["name"])

        # Category
        tk.Label(f, text="Category:", bg="#f8fafc", font=("Segoe UI", 9)).pack(anchor="w")
        cat_cb = ttk.Combobox(f, values=cat_names, state="readonly")
        if cat_names:
            cat_cb.set(cat_names[0])
        cat_cb.pack(fill=tk.X, pady=(2, 8))

        # Price & Cost
        r_pc = tk.Frame(f, bg="#f8fafc")
        r_pc.pack(fill=tk.X, pady=(2, 8))

        tk.Label(r_pc, text="Patient Price (Tk) *:", bg="#f8fafc", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        price_e = tk.Entry(r_pc, font=("Segoe UI", 10), width=10, bd=1, relief=tk.SOLID)
        price_e.pack(side=tk.LEFT, padx=(4, 16), ipady=2)
        price_e.insert(0, str(test_to_edit["price"]) if test_to_edit else "0.0")

        tk.Label(r_pc, text="Lab Cost (Tk):", bg="#f8fafc", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        cost_e = tk.Entry(r_pc, font=("Segoe UI", 10), width=10, bd=1, relief=tk.SOLID)
        cost_e.pack(side=tk.LEFT, padx=(4, 0), ipady=2)
        cost_e.insert(0, str(test_to_edit["cost"]) if test_to_edit else "0.0")

        # Sample Type
        tk.Label(f, text="Sample Type:", bg="#f8fafc", font=("Segoe UI", 9)).pack(anchor="w")
        sample_e = tk.Entry(f, font=("Segoe UI", 10), bd=1, relief=tk.SOLID)
        sample_e.insert(0, test_to_edit.get("sample_type", "Blood") if test_to_edit else "Blood")
        sample_e.pack(fill=tk.X, pady=(2, 12), ipady=2)

        def _save():
            code = code_e.get().strip()
            name = name_e.get().strip()
            try:
                price = float(price_e.get().strip() or "0")
                cost = float(cost_e.get().strip() or "0")
            except ValueError:
                messagebox.showerror("Invalid Input", "Price and cost must be numerical values.", parent=dialog)
                return

            if not code or not name:
                messagebox.showwarning("Incomplete Input", "Code and Name are required.", parent=dialog)
                return

            cat_id = cat_map.get(cat_cb.get())
            test_data = {
                "category_id": cat_id,
                "code": code,
                "name": name,
                "price": price,
                "cost": cost,
                "sample_type": sample_e.get().strip() or "Blood",
                "delivery_time": "Same Day"
            }

            try:
                if test_to_edit:
                    database.update_test(test_to_edit["id"], test_data)
                else:
                    database.add_test(test_data)

                dialog.destroy()
                self._refresh_tests_tree()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save test: {e}", parent=dialog)

        tk.Button(
            f,
            text="💾 Save Test",
            font=("Segoe UI", 10, "bold"),
            bg="#0d9488",
            fg="#ffffff",
            relief=tk.FLAT,
            pady=6,
            command=_save
        ).pack(fill=tk.X, pady=(6, 0))

    def _show_edit_test_dialog(self):
        selected = self.tests_tree.selection()
        if not selected:
            messagebox.showinfo("Selection Required", "Please select a test from the table to edit.")
            return

        item_vals = self.tests_tree.item(selected[0])["values"]
        test_id = int(item_vals[0])
        # Find raw test
        all_t = database.get_all_tests(active_only=False)
        target = next((t for t in all_t if t["id"] == test_id), None)
        if target:
            self._show_add_test_dialog(test_to_edit=target)

    def _delete_selected_test(self):
        selected = self.tests_tree.selection()
        if not selected:
            return
        item_vals = self.tests_tree.item(selected[0])["values"]
        test_id = int(item_vals[0])
        test_name = item_vals[2]

        if messagebox.askyesno("Confirm Deletion", f"Are you sure you want to disable test '{test_name}'?"):
            database.delete_test(test_id)
            self._refresh_tests_tree()

    # ==========================================================================
    # TAB 2: DAILY AUDIT REPORTS & ANALYTICS
    # ==========================================================================

    def _build_reports_tab(self, parent):
        ctrl_frame = tk.Frame(parent, bg="#f8fafc", pady=8, padx=8)
        ctrl_frame.pack(fill=tk.X)

        tk.Label(ctrl_frame, text="Date (YYYY-MM-DD):", bg="#f8fafc", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        self.report_date_e = tk.Entry(ctrl_frame, font=("Segoe UI", 10), width=12, bd=1, relief=tk.SOLID)
        self.report_date_e.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.report_date_e.pack(side=tk.LEFT, padx=(6, 6), ipady=2)

        # Quick date navigation buttons
        tk.Button(
            ctrl_frame, text="◄",
            font=("Segoe UI", 9, "bold"),
            bg="#e2e8f0", relief=tk.FLAT, padx=6,
            command=self._date_prev_day
        ).pack(side=tk.LEFT, padx=1)

        tk.Button(
            ctrl_frame, text="Today",
            font=("Segoe UI", 9, "bold"),
            bg="#0d9488", fg="#ffffff", relief=tk.FLAT, padx=8,
            command=self._date_today
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            ctrl_frame, text="Yesterday",
            font=("Segoe UI", 9),
            bg="#e2e8f0", relief=tk.FLAT, padx=8,
            command=self._date_yesterday
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            ctrl_frame, text="►",
            font=("Segoe UI", 9, "bold"),
            bg="#e2e8f0", relief=tk.FLAT, padx=6,
            command=self._date_next_day
        ).pack(side=tk.LEFT, padx=1)

        tk.Button(
            ctrl_frame,
            text="🔍 Generate Report",
            font=("Segoe UI", 9, "bold"),
            bg="#0f172a",
            fg="#ffffff",
            relief=tk.FLAT,
            padx=10,
            command=self._load_daily_report
        ).pack(side=tk.LEFT, padx=(10, 2))

        tk.Button(
            ctrl_frame,
            text="📄 Export PDF",
            font=("Segoe UI", 9, "bold"),
            bg="#0f766e",
            fg="#ffffff",
            activebackground="#115e59",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=12,
            command=self._export_daily_audit_pdf
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            ctrl_frame,
            text="📂 Reports Folder",
            font=("Segoe UI", 9),
            bg="#e2e8f0",
            fg="#1e293b",
            relief=tk.FLAT,
            padx=10,
            command=lambda: self._open_directory(pdf_generator.get_reports_pdf_directory())
        ).pack(side=tk.LEFT)

        # Summary Metrics Cards
        metrics_frame = tk.Frame(parent, bg="#f8fafc", padx=8, pady=6)
        metrics_frame.pack(fill=tk.X)

        self.metric_cards = {}
        labels = [
            ("vouchers", "Total Vouchers", "0"),
            ("tests", "Tests Conducted", "0"),
            ("subtotal", "Gross Billed", "Tk 0.00"),
            ("discount", "Total Discount", "Tk 0.00"),
            ("collected", "Cash Collected", "Tk 0.00"),
            ("due", "Total Due Balance", "Tk 0.00")
        ]

        for idx, (key, title, default_val) in enumerate(labels):
            card = tk.Frame(metrics_frame, bg="#ffffff", bd=1, relief=tk.SOLID, padx=10, pady=8)
            card.grid(row=idx // 3, column=idx % 3, sticky="nsew", padx=4, pady=4)
            metrics_frame.grid_columnconfigure(idx % 3, weight=1)

            tk.Label(card, text=title, font=("Segoe UI", 8), bg="#ffffff", fg="#64748b").pack(anchor="w")
            lbl = tk.Label(card, text=default_val, font=("Segoe UI", 12, "bold"), bg="#ffffff", fg="#0f172a")
            lbl.pack(anchor="w", pady=(2, 0))
            self.metric_cards[key] = lbl

        # Vouchers Conducted On Selected Date Table
        tk.Label(
            parent,
            text=" Vouchers Conducted on Selected Date: ",
            font=("Segoe UI", 9, "bold"),
            bg="#f8fafc",
            anchor="w"
        ).pack(fill=tk.X, padx=8, pady=(8, 2))

        cols = ("vno", "time", "patient", "phone", "total", "paid", "due", "status")
        self.report_tree = ttk.Treeview(parent, columns=cols, show="headings", height=8, selectmode="browse")

        self.report_tree.heading("vno", text="Voucher No")
        self.report_tree.heading("time", text="Time")
        self.report_tree.heading("patient", text="Patient Name")
        self.report_tree.heading("phone", text="Phone")
        self.report_tree.heading("total", text="Total (Tk)")
        self.report_tree.heading("paid", text="Paid (Tk)")
        self.report_tree.heading("due", text="Due (Tk)")
        self.report_tree.heading("status", text="Status")

        self.report_tree.column("vno", width=120)
        self.report_tree.column("time", width=80, anchor=tk.CENTER)
        self.report_tree.column("patient", width=160)
        self.report_tree.column("phone", width=100)
        self.report_tree.column("total", width=80, anchor=tk.E)
        self.report_tree.column("paid", width=80, anchor=tk.E)
        self.report_tree.column("due", width=80, anchor=tk.E)
        self.report_tree.column("status", width=70, anchor=tk.CENTER)

        self.report_tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self._load_daily_report()

    def _load_daily_report(self):
        date_str = self.report_date_e.get().strip() or datetime.now().strftime("%Y-%m-%d")
        summary = database.get_daily_summary(date_str)
        curr = database.get_setting("currency_symbol", "Tk")

        self.metric_cards["vouchers"].configure(text=str(summary["total_vouchers"]))
        self.metric_cards["tests"].configure(text=str(summary["total_tests"]))
        self.metric_cards["subtotal"].configure(text=f"{curr} {summary['total_billed']:.2f}")
        self.metric_cards["discount"].configure(text=f"{curr} {summary['total_discount']:.2f}")
        self.metric_cards["collected"].configure(text=f"{curr} {summary['total_collected']:.2f}", fg="#059669")
        self.metric_cards["due"].configure(
            text=f"{curr} {summary['total_due']:.2f}",
            fg="#dc2626" if summary["total_due"] > 0 else "#059669"
        )

        # Populate Vouchers
        self.report_tree.delete(*self.report_tree.get_children())
        conn = database.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT voucher_no, created_at, patient_name, patient_phone,
                   total_amount, paid_amount, due_amount, payment_status
            FROM vouchers
            WHERE DATE(created_at) = DATE(?)
            ORDER BY id DESC;
        """, (date_str,))
        rows = cursor.fetchall()
        conn.close()

        for r in rows:
            created_time = str(r["created_at"])[11:16] if len(str(r["created_at"])) >= 16 else ""
            self.report_tree.insert("", tk.END, values=(
                r["voucher_no"],
                created_time,
                r["patient_name"],
                r["patient_phone"],
                f"{r['total_amount']:.2f}",
                f"{r['paid_amount']:.2f}",
                f"{r['due_amount']:.2f}",
                r["payment_status"]
            ))

    def _export_daily_audit_pdf(self):
        date_str = self.report_date_e.get().strip() or datetime.now().strftime("%Y-%m-%d")
        try:
            pdf_path = pdf_generator.generate_daily_audit_pdf(date_str)
            if pdf_path and os.path.exists(pdf_path):
                if messagebox.askyesno(
                    "PDF Generated Successfully",
                    f"Daily Audit PDF report generated!\n\nSaved at:\n{pdf_path}\n\nOpen now?",
                    parent=self.win
                ):
                    try:
                        os.startfile(pdf_path)
                    except Exception as e:
                        messagebox.showwarning("Open File", f"PDF created but could not be launched:\n{e}", parent=self.win)
            else:
                messagebox.showerror("Export Failed", "PDF generator could not produce the report file.", parent=self.win)
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to generate Daily Audit PDF:\n{e}", parent=self.win)

    def _date_today(self):
        """Set report date to today and reload."""
        self.report_date_e.delete(0, tk.END)
        self.report_date_e.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self._load_daily_report()

    def _date_yesterday(self):
        """Set report date to yesterday and reload."""
        from datetime import timedelta
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        self.report_date_e.delete(0, tk.END)
        self.report_date_e.insert(0, yesterday)
        self._load_daily_report()

    def _date_prev_day(self):
        """Move report date one day back."""
        from datetime import timedelta
        try:
            current = datetime.strptime(self.report_date_e.get().strip(), "%Y-%m-%d")
            prev_day = (current - timedelta(days=1)).strftime("%Y-%m-%d")
            self.report_date_e.delete(0, tk.END)
            self.report_date_e.insert(0, prev_day)
            self._load_daily_report()
        except ValueError:
            self._date_today()

    def _date_next_day(self):
        """Move report date one day forward."""
        from datetime import timedelta
        try:
            current = datetime.strptime(self.report_date_e.get().strip(), "%Y-%m-%d")
            next_day = (current + timedelta(days=1)).strftime("%Y-%m-%d")
            self.report_date_e.delete(0, tk.END)
            self.report_date_e.insert(0, next_day)
            self._load_daily_report()
        except ValueError:
            self._date_today()

    def _open_directory(self, path: str):
        if not path:
            messagebox.showwarning("Directory Empty", "No directory path specified.", parent=self.win)
            return
        try:
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
            os.startfile(path)
        except Exception as e:
            messagebox.showerror("Error Opening Folder", f"Could not open directory in Windows Explorer:\n{path}\n\nError: {e}", parent=self.win)

    def _browse_directory(self, target_entry: tk.Entry, title: str):
        current_val = target_entry.get().strip()
        initial_dir = current_val if os.path.exists(current_val) else DEFAULT_STORAGE_ROOT
        if not os.path.exists(initial_dir):
            initial_dir = os.path.expanduser("~")

        chosen = filedialog.askdirectory(parent=self.win, title=title, initialdir=initial_dir)
        if chosen:
            normalized = os.path.normpath(chosen)
            target_entry.delete(0, tk.END)
            target_entry.insert(0, normalized)

    def _auto_setup_subfolders(self):
        root_dir = self.setting_entries["storage_root_path"].get().strip()
        if not root_dir:
            root_dir = DEFAULT_STORAGE_ROOT
            self.setting_entries["storage_root_path"].delete(0, tk.END)
            self.setting_entries["storage_root_path"].insert(0, root_dir)

        backup_dir = os.path.join(root_dir, "Backups")
        voucher_dir = os.path.join(root_dir, "Vouchers_PDF")
        reports_dir = os.path.join(root_dir, "Daily_Reports")
        json_dir = os.path.join(root_dir, "Vouchers_JSON")

        try:
            for d in (root_dir, backup_dir, voucher_dir, reports_dir, json_dir):
                os.makedirs(d, exist_ok=True)

            self.setting_entries["backup_local_path"].delete(0, tk.END)
            self.setting_entries["backup_local_path"].insert(0, backup_dir)

            self.setting_entries["voucher_pdf_dir"].delete(0, tk.END)
            self.setting_entries["voucher_pdf_dir"].insert(0, voucher_dir)

            self.setting_entries["reports_pdf_dir"].delete(0, tk.END)
            self.setting_entries["reports_pdf_dir"].insert(0, reports_dir)

            if "voucher_json_dir" in self.setting_entries:
                self.setting_entries["voucher_json_dir"].delete(0, tk.END)
                self.setting_entries["voucher_json_dir"].insert(0, json_dir)

            messagebox.showinfo(
                "Subfolders Initialized",
                f"All 4 dedicated storage folders have been configured and verified on disk:\n\n"
                f"📁 Root: {root_dir}\n"
                f"├─ 🛡️ Backups: {backup_dir}\n"
                f"├─ 📄 Voucher PDFs: {voucher_dir}\n"
                f"├─ 📊 Daily Reports: {reports_dir}\n"
                f"└─ 📜 JSON Text Vault: {json_dir}\n\n"
                f"Click 'Save Application Settings' to apply these paths permanently.",
                parent=self.win
            )
        except Exception as e:
            messagebox.showerror("Folder Setup Error", f"Could not create storage folders:\n{e}", parent=self.win)

    def _add_directory_row(self, parent_frame: tk.Widget, key: str, label_text: str, description: str, default_val: str, is_root: bool = False):
        row_frame = tk.Frame(parent_frame, bg="#ffffff")
        row_frame.pack(fill=tk.X, pady=(4, 8))

        top_line = tk.Frame(row_frame, bg="#ffffff")
        top_line.pack(fill=tk.X)

        tk.Label(
            top_line,
            text=label_text,
            font=("Segoe UI", 9, "bold"),
            bg="#ffffff",
            fg="#1e293b"
        ).pack(side=tk.LEFT)

        tk.Label(
            top_line,
            text=f"  ({description})",
            font=("Segoe UI", 8),
            bg="#ffffff",
            fg="#64748b"
        ).pack(side=tk.LEFT)

        input_box = tk.Frame(row_frame, bg="#ffffff")
        input_box.pack(fill=tk.X, pady=(2, 0))

        entry = tk.Entry(input_box, font=("Segoe UI", 9), bd=1, relief=tk.SOLID)
        entry.insert(0, default_val)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        self.setting_entries[key] = entry

        tk.Button(
            input_box,
            text="📁 Browse...",
            font=("Segoe UI", 8, "bold"),
            bg="#e2e8f0",
            fg="#0f172a",
            relief=tk.FLAT,
            padx=8,
            command=lambda e=entry, k=key: self._browse_directory(e, f"Select {label_text}")
        ).pack(side=tk.LEFT, padx=(6, 4))

        if is_root:
            tk.Button(
                input_box,
                text="✨ Auto-Setup Subfolders",
                font=("Segoe UI", 8, "bold"),
                bg="#0d9488",
                fg="#ffffff",
                relief=tk.FLAT,
                padx=8,
                command=self._auto_setup_subfolders
            ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            input_box,
            text="📂 Open Folder",
            font=("Segoe UI", 8),
            bg="#f1f5f9",
            fg="#334155",
            relief=tk.FLAT,
            padx=8,
            command=lambda e=entry: self._open_directory(e.get().strip())
        ).pack(side=tk.LEFT, padx=4)

    # ==========================================================================
    # TAB 3: SYSTEM CONFIGURATION, STORAGE DIRECTORIES & PRINTER SELECTION
    # ==========================================================================

    def _build_settings_tab(self, parent):
        scroll_canvas = tk.Canvas(parent, bg="#f8fafc", highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=scroll_canvas.yview)
        form_frame = tk.Frame(scroll_canvas, bg="#f8fafc", padx=16, pady=12)

        scroll_canvas.create_window((0, 0), window=form_frame, anchor="nw")
        scroll_canvas.configure(yscrollcommand=scrollbar.set)

        scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        form_frame.bind("<Configure>", lambda e: scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all")))

        settings = database.get_all_settings()

        # Fields Dictionary
        self.setting_entries = {}

        # ----------------------------------------------------------------------
        # Card 1: Storage & Archival Directories (PDFs, Backups, Reports)
        # ----------------------------------------------------------------------
        storage_frame = tk.LabelFrame(
            form_frame,
            text=" 📂 Storage & Archival Directories (PDFs & Backups) ",
            font=("Segoe UI", 10, "bold"),
            bg="#ffffff",
            fg="#0f766e",
            padx=14,
            pady=12,
            bd=1,
            relief=tk.SOLID
        )
        storage_frame.pack(fill=tk.X, pady=(0, 14))

        tk.Label(
            storage_frame,
            text="Configure dedicated paths for automated backups, archived voucher PDFs, and daily financial audit reports:",
            font=("Segoe UI", 9),
            bg="#ffffff",
            fg="#475569"
        ).pack(anchor="w", pady=(0, 10))

        # Root Storage Directory
        root_val = settings.get("storage_root_path", DEFAULT_STORAGE_ROOT)
        self._add_directory_row(
            parent_frame=storage_frame,
            key="storage_root_path",
            label_text="Main Storage Root Folder:",
            description="Base folder under which POS data and subfolders reside.",
            default_val=root_val,
            is_root=True
        )

        ttk.Separator(storage_frame, orient="horizontal").pack(fill=tk.X, pady=8)

        # 1. Automated Backups Subfolder
        backup_val = settings.get("backup_local_path", DEFAULT_BACKUP_DIR)
        self._add_directory_row(
            parent_frame=storage_frame,
            key="backup_local_path",
            label_text="1. Automated Backups Folder (Layer 1):",
            description="Stores atomic SQLite compressed ZIP backups on app close and manual triggers.",
            default_val=backup_val
        )

        # 2. Printed Voucher PDFs Subfolder
        voucher_pdf_val = settings.get("voucher_pdf_dir", DEFAULT_VOUCHER_PDF_DIR)
        self._add_directory_row(
            parent_frame=storage_frame,
            key="voucher_pdf_dir",
            label_text="2. Printed Voucher PDFs Archive Folder:",
            description="Every printed voucher automatically saves a printable PDF copy here.",
            default_val=voucher_pdf_val
        )

        # 3. Daily Reports Subfolder
        reports_pdf_val = settings.get("reports_pdf_dir", DEFAULT_REPORTS_PDF_DIR)
        self._add_directory_row(
            parent_frame=storage_frame,
            key="reports_pdf_dir",
            label_text="3. Daily Calculations & Audit Reports Folder:",
            description="Daily conduct summaries, revenue calculations, and audit PDF exports are saved here.",
            default_val=reports_pdf_val
        )

        # 4. Structured JSON Text Subfolder
        voucher_json_val = settings.get("voucher_json_dir", DEFAULT_VOUCHER_JSON_DIR)
        self._add_directory_row(
            parent_frame=storage_frame,
            key="voucher_json_dir",
            label_text="4. Structured JSON / Text Data Folder:",
            description="Replicates every voucher as human-readable, lossless JSON text files for backup and restore.",
            default_val=voucher_json_val
        )

        # ----------------------------------------------------------------------
        # Card 2: Hospital Identity & Branding
        # ----------------------------------------------------------------------
        hosp_frame = tk.LabelFrame(
            form_frame,
            text=" 🏥 Hospital Identity & Receipt Branding ",
            font=("Segoe UI", 10, "bold"),
            bg="#ffffff",
            fg="#0f766e",
            padx=14,
            pady=12,
            bd=1,
            relief=tk.SOLID
        )
        hosp_frame.pack(fill=tk.X, pady=(0, 14))

        fields = [
            ("hospital_name", "Hospital / Diagnostic Center Name:", settings.get("hospital_name", "")),
            ("hospital_tagline", "Tagline / Specialty Line:", settings.get("hospital_tagline", "")),
            ("hospital_address", "Hospital Address:", settings.get("hospital_address", "")),
            ("hospital_phone", "Contact Phone:", settings.get("hospital_phone", "")),
            ("voucher_footer", "Receipt Footer Notice:", settings.get("voucher_footer", "")),
            ("currency_symbol", "Currency Symbol (e.g. Tk, $, ৳):", settings.get("currency_symbol", "Tk")),
            ("admin_pin", "Admin Security PIN:", settings.get("admin_pin", "1234")),
        ]

        for key, label, val in fields:
            tk.Label(hosp_frame, text=label, font=("Segoe UI", 9, "bold"), bg="#ffffff").pack(anchor="w", pady=(4, 1))
            entry = tk.Entry(hosp_frame, font=("Segoe UI", 10), width=50, bd=1, relief=tk.SOLID)
            entry.insert(0, val)
            entry.pack(fill=tk.X, pady=(0, 4), ipady=2)
            self.setting_entries[key] = entry

        # ----------------------------------------------------------------------
        # Card 3: Printer & Paper Format
        # ----------------------------------------------------------------------
        printer_frame = tk.LabelFrame(
            form_frame,
            text=" 🖨️ Printer & Paper Configuration ",
            font=("Segoe UI", 10, "bold"),
            bg="#ffffff",
            fg="#0f766e",
            padx=14,
            pady=12,
            bd=1,
            relief=tk.SOLID
        )
        printer_frame.pack(fill=tk.X, pady=(0, 14))

        tk.Label(printer_frame, text="Silent Print Target Printer:", font=("Segoe UI", 9, "bold"), bg="#ffffff").pack(anchor="w", pady=(4, 1))
        available_printers = ["DEFAULT"] + printer_engine.get_available_printers()
        self.printer_cb = ttk.Combobox(printer_frame, values=available_printers, state="readonly")
        current_p = settings.get("printer_name", "DEFAULT")
        self.printer_cb.set(current_p if current_p in available_printers else "DEFAULT")
        self.printer_cb.pack(fill=tk.X, pady=(0, 8))

        # Paper Size (80mm Thermal vs A5)
        tk.Label(printer_frame, text="Voucher Paper Format:", font=("Segoe UI", 9, "bold"), bg="#ffffff").pack(anchor="w", pady=(4, 1))
        self.paper_cb = ttk.Combobox(printer_frame, values=["80mm (Thermal POS)", "A5 (Laser / Slip)"], state="readonly")
        self.paper_cb.set("80mm (Thermal POS)" if settings.get("paper_size", "80mm") == "80mm" else "A5 (Laser / Slip)")
        self.paper_cb.pack(fill=tk.X, pady=(0, 8))

        # ----------------------------------------------------------------------
        # Card 4: MongoDB Atlas Cloud Synchronization
        # ----------------------------------------------------------------------
        mongo_frame = tk.LabelFrame(
            form_frame,
            text=" ☁️ MongoDB Atlas Cloud Synchronization ",
            font=("Segoe UI", 10, "bold"),
            bg="#ffffff",
            fg="#0f766e",
            padx=14,
            pady=12,
            bd=1,
            relief=tk.SOLID
        )
        mongo_frame.pack(fill=tk.X, pady=(0, 14))

        tk.Label(
            mongo_frame,
            text="Connect directly to MongoDB Atlas cluster for real-time cloud data replication & two-way restore:",
            font=("Segoe UI", 9),
            bg="#ffffff",
            fg="#475569"
        ).pack(anchor="w", pady=(0, 8))

        # URI
        tk.Label(mongo_frame, text="MongoDB Atlas Connection URI (mongodb+srv://...):", font=("Segoe UI", 9, "bold"), bg="#ffffff").pack(anchor="w")
        self.mongo_uri_e = tk.Entry(mongo_frame, font=("Segoe UI", 9), bd=1, relief=tk.SOLID)
        self.mongo_uri_e.insert(0, settings.get("mongo_atlas_uri", DEFAULT_MONGO_URI))
        self.mongo_uri_e.pack(fill=tk.X, pady=(2, 4), ipady=3)
        self.setting_entries["mongo_atlas_uri"] = self.mongo_uri_e

        tk.Label(
            mongo_frame,
            text="Format: mongodb+srv://<username>:<password>@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority",
            font=("Segoe UI", 8, "italic"),
            bg="#ffffff",
            fg="#64748b"
        ).pack(anchor="w", pady=(0, 8))

        # DB Name & Auto-sync row
        db_box = tk.Frame(mongo_frame, bg="#ffffff")
        db_box.pack(fill=tk.X, pady=(0, 8))

        tk.Label(db_box, text="Database Name: ", font=("Segoe UI", 9, "bold"), bg="#ffffff").pack(side=tk.LEFT)
        self.mongo_db_e = tk.Entry(db_box, font=("Segoe UI", 9), width=24, bd=1, relief=tk.SOLID)
        self.mongo_db_e.insert(0, settings.get("mongo_db_name", DEFAULT_MONGO_DB))
        self.mongo_db_e.pack(side=tk.LEFT, padx=(4, 16), ipady=2)
        self.setting_entries["mongo_db_name"] = self.mongo_db_e

        # Auto sync checkbox
        self.mongo_auto_var = tk.IntVar(value=1 if settings.get("mongo_auto_sync", "1") == "1" else 0)
        chk = tk.Checkbutton(
            db_box,
            text="Auto-sync new vouchers to MongoDB in background",
            variable=self.mongo_auto_var,
            font=("Segoe UI", 9),
            bg="#ffffff",
            activebackground="#ffffff"
        )
        chk.pack(side=tk.LEFT)

        # Test Connection Button
        tk.Button(
            mongo_frame,
            text="⚡ Test MongoDB Connection",
            font=("Segoe UI", 9, "bold"),
            bg="#e2e8f0",
            fg="#0f172a",
            relief=tk.FLAT,
            padx=12,
            pady=4,
            command=self._test_mongo_connection
        ).pack(anchor="w", pady=(4, 2))

        # Save Button
        save_btn = tk.Button(
            form_frame,
            text="💾 Save Application Settings & Verify Folders",
            font=("Segoe UI", 11, "bold"),
            bg="#0d9488",
            fg="#ffffff",
            activebackground="#0f766e",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            pady=10,
            command=self._save_settings
        )
        save_btn.pack(fill=tk.X, pady=(10, 4))

        # Inline save confirmation label
        self.settings_saved_lbl = tk.Label(
            form_frame,
            text="",
            font=("Segoe UI", 9, "italic"),
            bg="#f8fafc",
            fg="#059669"
        )
        self.settings_saved_lbl.pack(anchor="w", pady=(0, 16))

    def _save_settings(self):
        for key, entry in self.setting_entries.items():
            val = entry.get().strip()
            database.set_setting(key, val)
            # Ensure directories exist
            if key in ("storage_root_path", "backup_local_path", "voucher_pdf_dir", "reports_pdf_dir", "voucher_json_dir") and val:
                try:
                    os.makedirs(val, exist_ok=True)
                except Exception as e:
                    print(f"[AdminPanel] Warning: Could not create folder '{val}': {e}")

        database.set_setting("printer_name", self.printer_cb.get())
        paper = "80mm" if "80mm" in self.paper_cb.get() else "A5"
        database.set_setting("paper_size", paper)
        database.set_setting("mongo_auto_sync", str(self.mongo_auto_var.get()))

        # Show inline confirmation instead of modal popup
        if hasattr(self, "settings_saved_lbl"):
            self.settings_saved_lbl.configure(
                text=f"✅ All settings saved successfully at {datetime.now().strftime('%H:%M:%S')}"
            )
            self.win.after(5000, lambda: self.settings_saved_lbl.configure(text=""))
        else:
            messagebox.showinfo("Settings Saved", "System settings updated successfully!", parent=self.win)

        if self.on_settings_updated:
            self.on_settings_updated()

    # ==========================================================================
    # TAB 4: BACKUP SUITE, TEXT VAULT & MONGODB CLOUD SYNC
    # ==========================================================================

    def _build_backup_tab(self, parent):
        scroll_canvas = tk.Canvas(parent, bg="#f8fafc", highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=scroll_canvas.yview)
        f = tk.Frame(scroll_canvas, bg="#f8fafc", padx=16, pady=16)

        scroll_canvas.create_window((0, 0), window=f, anchor="nw")
        scroll_canvas.configure(yscrollcommand=scrollbar.set)

        scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        f.bind("<Configure>", lambda e: scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all")))

        # ----------------------------------------------------------------------
        # Section 1: Structured JSON Text Vault & MongoDB Atlas (User requested)
        # ----------------------------------------------------------------------
        json_card = tk.LabelFrame(
            f,
            text=" 📜 Structured JSON Text Vault & ☁️ MongoDB Atlas Cloud Sync ",
            font=("Segoe UI", 10, "bold"),
            bg="#ffffff",
            fg="#0f766e",
            padx=14,
            pady=12,
            bd=1,
            relief=tk.SOLID
        )
        json_card.pack(fill=tk.X, pady=(0, 16))

        tk.Label(
            json_card,
            text=(
                "All vouchers are replicated as structured JSON text documents for 100% lossless cold storage.\n"
                "You can export full text backups, restore from JSON files/folders, and synchronize with MongoDB Atlas."
            ),
            font=("Segoe UI", 9),
            bg="#ffffff",
            fg="#475569",
            justify=tk.LEFT
        ).pack(anchor="w", pady=(0, 10))

        # JSON Action Buttons Bar
        json_btn_box = tk.Frame(json_card, bg="#ffffff")
        json_btn_box.pack(fill=tk.X, pady=(0, 8))

        tk.Button(
            json_btn_box,
            text="📤 Export Full Database to JSON",
            font=("Segoe UI", 9, "bold"),
            bg="#0d9488",
            fg="#ffffff",
            activebackground="#0f766e",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=10,
            pady=5,
            command=self._export_full_database_json
        ).pack(side=tk.LEFT, padx=(0, 6))

        tk.Button(
            json_btn_box,
            text="📥 Restore from JSON File",
            font=("Segoe UI", 9, "bold"),
            bg="#2563eb",
            fg="#ffffff",
            activebackground="#1d4ed8",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=10,
            pady=5,
            command=self._restore_from_json_file
        ).pack(side=tk.LEFT, padx=6)

        tk.Button(
            json_btn_box,
            text="📂 Bulk Restore from JSON Folder",
            font=("Segoe UI", 9),
            bg="#e2e8f0",
            fg="#0f172a",
            relief=tk.FLAT,
            padx=10,
            pady=5,
            command=self._restore_from_json_folder
        ).pack(side=tk.LEFT, padx=6)

        tk.Button(
            json_btn_box,
            text="📂 Open JSON Folder",
            font=("Segoe UI", 9),
            bg="#f1f5f9",
            fg="#334155",
            relief=tk.FLAT,
            padx=8,
            pady=5,
            command=lambda: self._open_directory(data_vault.get_voucher_json_directory())
        ).pack(side=tk.LEFT, padx=6)

        ttk.Separator(json_card, orient="horizontal").pack(fill=tk.X, pady=10)

        # MongoDB Cloud Actions Bar
        mongo_btn_box = tk.Frame(json_card, bg="#ffffff")
        mongo_btn_box.pack(fill=tk.X, pady=(0, 4))

        tk.Label(mongo_btn_box, text="MongoDB Atlas Operations:", font=("Segoe UI", 9, "bold"), bg="#ffffff").pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            mongo_btn_box,
            text="☁️ Push Local Vouchers to MongoDB",
            font=("Segoe UI", 9, "bold"),
            bg="#0f766e",
            fg="#ffffff",
            activebackground="#115e59",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=10,
            pady=4,
            command=self._push_vouchers_to_mongo
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            mongo_btn_box,
            text="📥 Pull & Restore from MongoDB Atlas",
            font=("Segoe UI", 9, "bold"),
            bg="#3b82f6",
            fg="#ffffff",
            activebackground="#2563eb",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=10,
            pady=4,
            command=self._pull_vouchers_from_mongo
        ).pack(side=tk.LEFT, padx=4)

        self.mongo_sync_lbl = tk.Label(
            json_card,
            text=f"Last Cloud Sync: {database.get_setting('last_mongo_sync_timestamp', 'Never')}",
            font=("Segoe UI", 8, "italic"),
            bg="#ffffff",
            fg="#64748b"
        )
        self.mongo_sync_lbl.pack(anchor="w", pady=(6, 0))

        # ----------------------------------------------------------------------
        # Section 2: Automated 3-Layer Disaster Recovery (ZIP, USB, Telegram)
        # ----------------------------------------------------------------------
        tk.Label(
            f,
            text="🛡️ Automated 3-Layer Disaster Recovery (Compressed ZIP Archives)",
            font=("Segoe UI", 11, "bold"),
            bg="#f8fafc",
            fg="#0f766e"
        ).pack(anchor="w", pady=(8, 4))

        desc = (
            "• Layer 1: Atomic SQLite snapshot compressed into D:\\Hospital_POS_Data\\Backups\\ on exit.\n"
            "• Layer 2: Auto-detects connected USB Flash Drive and mirrors backup archive.\n"
            "• Layer 3: Telegram Cloud Vault sends encrypted database directly to your Telegram chat."
        )
        tk.Label(f, text=desc, font=("Segoe UI", 9), bg="#f8fafc", fg="#475569", justify=tk.LEFT).pack(anchor="w", pady=(0, 10))

        # Telegram Configuration Card
        tg_card = tk.LabelFrame(f, text=" Telegram Cloud Vault Configuration ", font=("Segoe UI", 9, "bold"), bg="#ffffff", padx=12, pady=10)
        tg_card.pack(fill=tk.X, pady=(0, 10))

        tk.Label(tg_card, text="Telegram Bot Token:", bg="#ffffff", font=("Segoe UI", 9)).pack(anchor="w")
        self.tg_token_e = tk.Entry(tg_card, font=("Segoe UI", 10), bd=1, relief=tk.SOLID)
        self.tg_token_e.insert(0, database.get_setting("telegram_bot_token", ""))
        self.tg_token_e.pack(fill=tk.X, pady=(2, 6), ipady=2)

        tk.Label(tg_card, text="Telegram Chat ID:", bg="#ffffff", font=("Segoe UI", 9)).pack(anchor="w")
        self.tg_chat_e = tk.Entry(tg_card, font=("Segoe UI", 10), bd=1, relief=tk.SOLID)
        self.tg_chat_e.insert(0, database.get_setting("telegram_chat_id", ""))
        self.tg_chat_e.pack(fill=tk.X, pady=(2, 6), ipady=2)

        save_tg_btn = tk.Button(
            tg_card,
            text="Save Telegram Credentials",
            font=("Segoe UI", 9),
            bg="#e2e8f0",
            relief=tk.FLAT,
            command=self._save_telegram_settings
        )
        save_tg_btn.pack(anchor="w")

        # Action Buttons
        btn_box = tk.Frame(f, bg="#f8fafc")
        btn_box.pack(fill=tk.X, pady=8)

        run_btn = tk.Button(
            btn_box,
            text="🚀 Execute Full 3-Layer Backup Now",
            font=("Segoe UI", 11, "bold"),
            bg="#0d9488",
            fg="#ffffff",
            relief=tk.FLAT,
            padx=16,
            pady=8,
            command=self._run_manual_backup
        )
        run_btn.pack(side=tk.LEFT)

        # Status output
        self.backup_status_lbl = tk.Label(
            f,
            text=f"Last Backup: {database.get_setting('last_backup_timestamp', 'Never')}",
            font=("Segoe UI", 9, "italic"),
            bg="#f8fafc",
            fg="#64748b"
        )
        self.backup_status_lbl.pack(anchor="w", pady=(8, 0))

    def _test_mongo_connection(self):
        uri = self.setting_entries["mongo_atlas_uri"].get().strip() if "mongo_atlas_uri" in self.setting_entries else database.get_setting("mongo_atlas_uri", "")
        if not uri:
            messagebox.showwarning("Missing URI", "Please enter your MongoDB Atlas connection string (mongodb+srv://...) first.", parent=self.win)
            return

        res = data_vault.test_mongo_connection(uri=uri)
        if res["success"]:
            messagebox.showinfo("MongoDB Connected", f"✅ {res['message']}", parent=self.win)
        else:
            messagebox.showerror("MongoDB Error", f"❌ {res['message']}", parent=self.win)

    def _export_full_database_json(self):
        try:
            out_file = data_vault.export_full_database_to_json()
            if messagebox.askyesno(
                "Export Complete",
                f"Full SQLite database successfully exported as structured JSON text!\n\n"
                f"Saved at:\n{out_file}\n\n"
                f"Do you want to open the JSON folder now?",
                parent=self.win
            ):
                self._open_directory(os.path.dirname(out_file))
        except Exception as e:
            messagebox.showerror("Export Failed", f"Failed to export database to JSON:\n{e}", parent=self.win)

    def _restore_from_json_file(self):
        init_dir = data_vault.get_voucher_json_directory()
        chosen = filedialog.askopenfilename(
            parent=self.win,
            title="Select JSON Backup or Voucher File to Restore",
            initialdir=init_dir,
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if not chosen:
            return

        overwrite = messagebox.askyesno(
            "Restore Overwrite Mode",
            "Do you want to OVERWRITE existing vouchers if duplicate voucher numbers are found?\n\n"
            "• Click YES to replace/update existing records.\n"
            "• Click NO to safely skip existing records.",
            parent=self.win
        )

        try:
            res = data_vault.restore_from_json_file(chosen, overwrite_existing=overwrite)
            if res.get("type") == "full_dump":
                msg = (
                    f"Full Database Backup Restored!\n\n"
                    f"• Vouchers Added: {res['restored_vouchers']}\n"
                    f"• Vouchers Skipped: {res['skipped_vouchers']}\n"
                    f"• Diagnostic Tests Restored: {res['restored_tests']}\n"
                    f"• Total Records in File: {res['total_records']}"
                )
            else:
                status = "Restored / Updated" if res.get("restored") else "Skipped (already exists)"
                msg = f"Voucher {res.get('voucher_no')} {status} successfully!"

            messagebox.showinfo("Restore Finished", msg, parent=self.win)
            self._refresh_tests_tree()
            self._load_daily_report()
            if self.on_settings_updated:
                self.on_settings_updated()
        except Exception as e:
            messagebox.showerror("Restore Error", f"Failed to restore from JSON file:\n{e}", parent=self.win)

    def _restore_from_json_folder(self):
        init_dir = data_vault.get_voucher_json_directory()
        chosen_dir = filedialog.askdirectory(
            parent=self.win,
            title="Select Folder Containing JSON Vouchers to Restore",
            initialdir=init_dir
        )
        if not chosen_dir:
            return

        overwrite = messagebox.askyesno(
            "Bulk Restore Overwrite Mode",
            "Do you want to OVERWRITE existing vouchers if duplicate voucher numbers are found in this folder?\n\n"
            "• Click YES to overwrite.\n"
            "• Click NO to safely skip duplicates.",
            parent=self.win
        )

        try:
            res = data_vault.restore_from_json_folder(chosen_dir, overwrite_existing=overwrite)
            msg = (
                f"Bulk JSON Folder Restore Complete!\n\n"
                f"• Total Files Scanned: {res['total_files']}\n"
                f"• Successfully Restored: {res['restored']}\n"
                f"• Skipped (Already Existing): {res['skipped']}\n"
                f"• Format Errors / Ignored: {res['errors']}"
            )
            messagebox.showinfo("Bulk Restore Finished", msg, parent=self.win)
            self._load_daily_report()
            if self.on_settings_updated:
                self.on_settings_updated()
        except Exception as e:
            messagebox.showerror("Bulk Restore Error", f"Failed to restore from JSON directory:\n{e}", parent=self.win)

    def _push_vouchers_to_mongo(self):
        uri = database.get_setting("mongo_atlas_uri", "").strip()
        if not uri:
            messagebox.showwarning(
                "MongoDB Atlas Not Configured",
                "Please configure your MongoDB Atlas Connection URI in System Settings first.",
                parent=self.win
            )
            return

        res = data_vault.push_to_mongodb()
        if res["success"]:
            messagebox.showinfo("MongoDB Cloud Sync", f"✅ {res['message']}", parent=self.win)
            self.mongo_sync_lbl.configure(text=f"Last Cloud Sync: {database.get_setting('last_mongo_sync_timestamp', 'Just Now')}")
        else:
            messagebox.showerror("MongoDB Sync Error", f"❌ {res['message']}", parent=self.win)

    def _pull_vouchers_from_mongo(self):
        uri = database.get_setting("mongo_atlas_uri", "").strip()
        if not uri:
            messagebox.showwarning(
                "MongoDB Atlas Not Configured",
                "Please configure your MongoDB Atlas Connection URI in System Settings first.",
                parent=self.win
            )
            return

        overwrite = messagebox.askyesno(
            "Cloud Restore Overwrite",
            "Do you want to OVERWRITE local vouchers if duplicate numbers are found in MongoDB Atlas?\n\n"
            "• Click YES to update local records from cloud.\n"
            "• Click NO to keep local copies and only import missing vouchers.",
            parent=self.win
        )

        res = data_vault.pull_and_restore_from_mongodb(overwrite_existing=overwrite)
        if res["success"]:
            messagebox.showinfo("MongoDB Cloud Restore", f"✅ {res['message']}", parent=self.win)
            self._load_daily_report()
            self.mongo_sync_lbl.configure(text=f"Last Cloud Sync: {database.get_setting('last_mongo_sync_timestamp', 'Just Now')}")
            if self.on_settings_updated:
                self.on_settings_updated()
        else:
            messagebox.showerror("MongoDB Cloud Restore Error", f"❌ {res['message']}", parent=self.win)

    def _save_telegram_settings(self):
        database.set_setting("telegram_bot_token", self.tg_token_e.get().strip())
        database.set_setting("telegram_chat_id", self.tg_chat_e.get().strip())
        messagebox.showinfo("Saved", "Telegram bot settings stored.", parent=self.win)

    def _run_manual_backup(self):
        self.backup_status_lbl.configure(text="Executing backup suite... Please wait.")
        self.win.update_idletasks()

        res = backup_manager.perform_full_backup(async_mode=False)
        l1 = f"✅ Local: {res['layer1_local']}" if res['layer1_local'] else "❌ Local ZIP: Failed"
        l2 = f"✅ USB: {res['layer2_usb']}" if res['layer2_usb'] else "⚠️ USB: Not connected"
        l3 = "✅ Telegram: Uploaded" if res['layer3_telegram'] else "⚠️ Telegram: Skipped/Offline"

        summary_msg = f"{l1}\n{l2}\n{l3}"
        self.backup_status_lbl.configure(text=f"Last Backup: {res['timestamp']}")
        messagebox.showinfo("Backup Finished", summary_msg, parent=self.win)

    # ==========================================================================
    # TAB 5: HARDWARE ID & LICENSE DETAILS
    # ==========================================================================

    def _build_license_tab(self, parent):
        f = tk.Frame(parent, bg="#f8fafc", padx=16, pady=16)
        f.pack(fill=tk.BOTH, expand=True)

        hwid = hwid_license.get_hardware_id()
        is_valid, status_msg, lic_info = hwid_license.verify_license()

        card = tk.LabelFrame(f, text=" Hardware Lock & License Details ", font=("Segoe UI", 10, "bold"), bg="#ffffff", padx=16, pady=14)
        card.pack(fill=tk.X, pady=(0, 16))

        tk.Label(card, text="Machine Hardware Fingerprint (HWID):", font=("Segoe UI", 9, "bold"), bg="#ffffff").pack(anchor="w")
        hwid_box = tk.Entry(card, font=("Consolas", 11, "bold"), fg="#0f766e", bg="#f0fdfa", bd=1, relief=tk.SOLID)
        hwid_box.insert(0, hwid)
        hwid_box.configure(state="readonly")
        hwid_box.pack(fill=tk.X, pady=(2, 10), ipady=3)

        status_color = "#059669" if is_valid else "#dc2626"
        tk.Label(card, text=f"License Status: {status_msg}", font=("Segoe UI", 10, "bold"), bg="#ffffff", fg=status_color).pack(anchor="w", pady=4)

        if lic_info:
            tk.Label(card, text=f"Registered To: {lic_info.get('client_name', 'N/A')}", font=("Segoe UI", 9), bg="#ffffff").pack(anchor="w")
            tk.Label(card, text=f"License Key: {lic_info.get('license_key', 'N/A')}", font=("Segoe UI", 9), bg="#ffffff").pack(anchor="w")
            tk.Label(card, text=f"Activated At: {lic_info.get('activated_at', 'N/A')}", font=("Segoe UI", 9), bg="#ffffff").pack(anchor="w")
            tk.Label(card, text=f"Expiry Date: {lic_info.get('expiry_date', 'PERPETUAL')}", font=("Segoe UI", 9), bg="#ffffff").pack(anchor="w")


if __name__ == "__main__":
    database.init_db()
    root = tk.Tk()
    root.withdraw()
    panel = AdminPanelWindow(root)
    root.mainloop()
