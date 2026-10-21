"""
Hospital POS & Billing System - Keyboard-Driven Billing Dashboard
Target Platform: Windows 7 (32-bit/64-bit) | Python 3.8.10 (32-bit)

Zero-Mouse Keyboard Workflow:
- Receptionists can issue a voucher within 10 seconds without lifting their hands from the keyboard.
- Enter jumps between fields: Name -> Age -> Gender -> Phone -> Doctor -> Test Search.
- Typing test shortcode (e.g., '101', 'cbc') and pressing Enter adds item to cart and refocuses search.
- Global Hotkeys:
  * F1: New Patient / Clear Form
  * F2: Jump to Test Search
  * F3: Focus Patient Name field
  * F4: Focus Discount Field
  * F5: Focus Paid Amount Field
  * F6: Cycle Payment Method (Cash→Card→bKash→Due)
  * F8: Open Admin Panel
  * F12 or Ctrl+P: Save Voucher & Silent Direct Print
  * Delete or Ctrl+D: Remove selected test from cart
  * Escape: Close suggestion dropdown
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import database
import printer_engine
import backup_manager
import pdf_generator
import data_vault
from config import APP_NAME, APP_VERSION


class BillingDashboard:
    def __init__(self, root: tk.Tk, on_open_admin: Optional[Any] = None):
        self.root = root
        self.on_open_admin = on_open_admin

        self.root.title(f"{APP_NAME} - Reception Billing Dashboard")
        try:
            self.root.state("zoomed")
        except Exception:
            self.root.geometry("1200x750")
        self.root.minsize(1024, 680)
        self.root.deiconify()

        # State Variables
        self.cart_items: List[Dict[str, Any]] = []
        self.last_created_voucher: Optional[Dict[str, Any]] = None
        self.autocomplete_tests: List[Dict[str, Any]] = []
        self._status_clear_after_id: Optional[str] = None

        self._setup_styles()
        self._build_ui()
        self._bind_global_shortcuts()

        # Load initial data
        self.refresh_recent_vouchers()
        self.reset_form()

        # Start live clock updater
        self._update_clock()
        # Auto-refresh recent vouchers list every 60 seconds
        self._schedule_recent_refresh()

    # ==========================================================================
    # STYLES & THEME
    # ==========================================================================

    def _setup_styles(self):
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        self.root.configure(bg="#eef2f6")

        # Color palette
        self.c_bg = "#eef2f6"
        self.c_card = "#ffffff"
        self.c_primary = "#0d9488"      # Medical Teal
        self.c_primary_dark = "#0f766e"
        self.c_accent = "#2563eb"       # Blue
        self.c_danger = "#dc2626"       # Red
        self.c_text = "#1e293b"
        self.c_border = "#cbd5e1"

        self.style.configure("TFrame", background=self.c_bg)
        self.style.configure("Card.TFrame", background=self.c_card, relief="solid", borderwidth=1)
        self.style.configure("TLabel", background=self.c_bg, foreground=self.c_text, font=("Segoe UI", 10))
        self.style.configure("Card.TLabel", background=self.c_card, foreground=self.c_text, font=("Segoe UI", 10))

        # Treeview styling
        self.style.configure(
            "Treeview",
            background="#ffffff",
            foreground="#1e293b",
            rowheight=28,
            fieldbackground="#ffffff",
            font=("Segoe UI", 10)
        )
        self.style.configure(
            "Treeview.Heading",
            background="#f1f5f9",
            foreground="#0f172a",
            font=("Segoe UI", 10, "bold"),
            relief="flat"
        )
        self.style.map("Treeview", background=[("selected", "#0d9488")], foreground=[("selected", "#ffffff")])

    # ==========================================================================
    # UI CONSTRUCTION
    # ==========================================================================

    def _build_ui(self):
        # Top Header Bar
        self._build_header()

        # Main Layout: Two Columns (Left: 65% Cart & Patient, Right: 35% Billing Totals)
        body_frame = tk.Frame(self.root, bg=self.c_bg, padx=12, pady=8)
        body_frame.pack(fill=tk.BOTH, expand=True)

        left_col = tk.Frame(body_frame, bg=self.c_bg)
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        right_col = tk.Frame(body_frame, bg=self.c_bg, width=460)
        right_col.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False)
        right_col.pack_propagate(False)

        # Left Column Cards
        self._build_patient_card(left_col)
        self._build_search_and_cart_card(left_col)

        # Right Column Cards
        self._build_summary_card(right_col)
        self._build_recent_vouchers_card(right_col)

        # Bottom Shortcut Footer Bar
        self._build_shortcut_bar()

    def _build_header(self):
        header_frame = tk.Frame(self.root, bg="#0f172a", height=54, padx=16)
        header_frame.pack(fill=tk.X, side=tk.TOP)

        # Hospital Name & Tagline
        h_info = tk.Frame(header_frame, bg="#0f172a")
        h_info.pack(side=tk.LEFT, pady=8)

        self.h_name_lbl = tk.Label(
            h_info,
            text=database.get_setting("hospital_name", "City Care Diagnostic & Hospital"),
            font=("Segoe UI", 14, "bold"),
            fg="#38bdf8",
            bg="#0f172a"
        )
        self.h_name_lbl.pack(anchor="w")

        # Right info panel
        right_info = tk.Frame(header_frame, bg="#0f172a")
        right_info.pack(side=tk.RIGHT, pady=6)

        # Today's patient counter badge
        self.today_counter_lbl = tk.Label(
            right_info,
            text="Today: 0 patients",
            font=("Segoe UI", 9, "bold"),
            fg="#4ade80",
            bg="#1e3a2f",
            padx=8,
            pady=2,
            relief=tk.FLAT,
            bd=0
        )
        self.today_counter_lbl.pack(side=tk.LEFT, padx=8)

        # Live Clock
        self.clock_lbl = tk.Label(
            right_info,
            text="--:-- --",
            font=("Segoe UI", 10, "bold"),
            fg="#e2e8f0",
            bg="#0f172a"
        )
        self.clock_lbl.pack(side=tk.LEFT, padx=6)

        self.printer_status_lbl = tk.Label(
            right_info,
            text=f"🖨️ {printer_engine.get_target_printer()}",
            font=("Segoe UI", 9),
            fg="#94a3b8",
            bg="#0f172a"
        )
        self.printer_status_lbl.pack(side=tk.LEFT, padx=8)

        history_btn = tk.Button(
            right_info,
            text="📋 History (F7)",
            font=("Segoe UI", 9, "bold"),
            bg="#0d9488",
            fg="#ffffff",
            activebackground="#0f766e",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=10,
            command=self.open_history_window
        )
        history_btn.pack(side=tk.LEFT, padx=6)

        admin_btn = tk.Button(
            right_info,
            text="⚙️ Admin (F8)",
            font=("Segoe UI", 9, "bold"),
            bg="#334155",
            fg="#ffffff",
            activebackground="#475569",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=10,
            command=self._open_admin
        )
        admin_btn.pack(side=tk.LEFT, padx=6)

    def _build_patient_card(self, parent):
        card = tk.LabelFrame(
            parent,
            text=" 1. Patient Details [Enter ➔ Jump Next] ",
            font=("Segoe UI", 10, "bold"),
            bg=self.c_card,
            fg="#0f766e",
            padx=12,
            pady=8,
            relief=tk.SOLID,
            bd=1
        )
        card.pack(fill=tk.X, pady=(0, 8))

        # Row 1: Name (50%), Age (15%), Gender (15%), Phone (20%)
        row1 = tk.Frame(card, bg=self.c_card)
        row1.pack(fill=tk.X, pady=2)

        # Patient Name
        tk.Label(row1, text="Patient Name *", bg=self.c_card, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        self.name_entry = tk.Entry(row1, font=("Segoe UI", 10), bd=1, relief=tk.SOLID)
        self.name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 12), ipady=3)
        self.name_entry.bind("<Return>", lambda e: self.age_entry.focus_set())

        # Age
        tk.Label(row1, text="Age", bg=self.c_card, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        self.age_entry = tk.Entry(row1, font=("Segoe UI", 10), width=6, bd=1, relief=tk.SOLID)
        self.age_entry.pack(side=tk.LEFT, padx=(4, 12), ipady=3)
        self.age_entry.bind("<Return>", lambda e: self.gender_combo.focus_set())

        # Gender
        tk.Label(row1, text="Sex", bg=self.c_card, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        self.gender_combo = ttk.Combobox(row1, values=["Male", "Female", "Other"], width=8, state="readonly")
        self.gender_combo.set("Male")
        self.gender_combo.pack(side=tk.LEFT, padx=(4, 12), ipady=1)
        self.gender_combo.bind("<Return>", lambda e: self.phone_entry.focus_set())

        # Phone
        tk.Label(row1, text="Phone", bg=self.c_card, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        self.phone_entry = tk.Entry(row1, font=("Segoe UI", 10), width=16, bd=1, relief=tk.SOLID)
        self.phone_entry.pack(side=tk.LEFT, padx=(4, 0), ipady=3)
        self.phone_entry.bind("<Return>", lambda e: self.ref_entry.focus_set())

        # Row 2: Referred By
        row2 = tk.Frame(card, bg=self.c_card)
        row2.pack(fill=tk.X, pady=(6, 2))

        tk.Label(row2, text="Referred By (Doctor / Hospital):", bg=self.c_card, font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.ref_entry = tk.Entry(row2, font=("Segoe UI", 10), bd=1, relief=tk.SOLID)
        self.ref_entry.insert(0, "Self / General")
        self.ref_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0), ipady=3)
        self.ref_entry.bind("<Return>", lambda e: self.search_entry.focus_set())

    def _build_search_and_cart_card(self, parent):
        card = tk.LabelFrame(
            parent,
            text=" 2. Diagnostic Tests Cart [Shortcode + Enter ➔ Add to Cart] ",
            font=("Segoe UI", 10, "bold"),
            bg=self.c_card,
            fg="#0f766e",
            padx=12,
            pady=8,
            relief=tk.SOLID,
            bd=1
        )
        card.pack(fill=tk.BOTH, expand=True)

        # Autocomplete Search Bar
        search_bar = tk.Frame(card, bg=self.c_card)
        search_bar.pack(fill=tk.X, pady=(0, 6))

        tk.Label(
            search_bar,
            text="🔍 Fast Test Search:",
            font=("Segoe UI", 10, "bold"),
            bg=self.c_card,
            fg="#0f766e"
        ).pack(side=tk.LEFT, padx=(0, 6))

        self.search_entry = tk.Entry(
            search_bar,
            font=("Segoe UI", 11, "bold"),
            bg="#f0fdfa",
            fg="#0f172a",
            bd=1,
            relief=tk.SOLID
        )
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)

        # Key bindings for fast test entry
        self.search_entry.bind("<KeyRelease>", self._on_search_keyrelease)
        self.search_entry.bind("<Return>", self._on_search_enter)
        self.search_entry.bind("<Down>", self._on_search_down_arrow)
        self.search_entry.bind("<Up>", self._on_search_up_arrow)

        # Helper chips / quick keys indicator
        quick_hint = tk.Label(
            search_bar,
            text="💡 e.g. 101=CBC, 201=RBS, 204=Creatinine, 501=ECG",
            font=("Segoe UI", 8),
            bg=self.c_card,
            fg="#64748b"
        )
        quick_hint.pack(side=tk.LEFT, padx=(8, 0))

        # Floating Autocomplete Listbox Frame
        self.suggest_box = tk.Listbox(
            card,
            font=("Segoe UI", 10),
            height=6,
            bd=1,
            relief=tk.SOLID,
            selectbackground="#0d9488",
            selectforeground="#ffffff"
        )
        self.suggest_box.bind("<Double-Button-1>", lambda e: self._add_selected_suggest())
        self.suggest_box.bind("<Return>", lambda e: self._add_selected_suggest())
        # Initially hidden
        self.suggest_box_visible = False

        # Cart Table (Treeview)
        table_frame = tk.Frame(card, bg=self.c_card)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=4)

        columns = ("sl", "code", "name", "sample", "qty", "price", "total")
        self.cart_tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.cart_tree.heading("sl", text="#", anchor=tk.CENTER)
        self.cart_tree.heading("code", text="Code", anchor=tk.CENTER)
        self.cart_tree.heading("name", text="Test Description", anchor=tk.W)
        self.cart_tree.heading("sample", text="Sample Type", anchor=tk.CENTER)
        self.cart_tree.heading("qty", text="Qty", anchor=tk.CENTER)
        self.cart_tree.heading("price", text="Price (Tk)", anchor=tk.E)
        self.cart_tree.heading("total", text="Total (Tk)", anchor=tk.E)

        self.cart_tree.column("sl", width=40, anchor=tk.CENTER)
        self.cart_tree.column("code", width=70, anchor=tk.CENTER)
        self.cart_tree.column("name", width=260, anchor=tk.W)
        self.cart_tree.column("sample", width=100, anchor=tk.CENTER)
        self.cart_tree.column("qty", width=50, anchor=tk.CENTER)
        self.cart_tree.column("price", width=90, anchor=tk.E)
        self.cart_tree.column("total", width=100, anchor=tk.E)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.cart_tree.yview)
        self.cart_tree.configure(yscrollcommand=scrollbar.set)

        self.cart_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Cart Action Bar
        cart_actions = tk.Frame(card, bg=self.c_card)
        cart_actions.pack(fill=tk.X, pady=(4, 0))

        remove_btn = tk.Button(
            cart_actions,
            text="❌ Remove Item (Del)",
            font=("Segoe UI", 9),
            bg="#fee2e2",
            fg="#b91c1c",
            activebackground="#fecaca",
            relief=tk.FLAT,
            padx=8,
            command=self._remove_selected_cart_item
        )
        remove_btn.pack(side=tk.LEFT)

        clear_cart_btn = tk.Button(
            cart_actions,
            text="🗑️ Clear Cart",
            font=("Segoe UI", 9),
            bg="#f1f5f9",
            fg="#475569",
            relief=tk.FLAT,
            padx=8,
            command=self._clear_cart
        )
        clear_cart_btn.pack(side=tk.LEFT, padx=6)

        self.item_count_lbl = tk.Label(
            cart_actions,
            text="Total Tests: 0",
            font=("Segoe UI", 9, "bold"),
            bg=self.c_card,
            fg="#0f766e"
        )
        self.item_count_lbl.pack(side=tk.RIGHT)

    def _build_summary_card(self, parent):
        card = tk.LabelFrame(
            parent,
            text=" 3. Billing & Payment ",
            font=("Segoe UI", 10, "bold"),
            bg=self.c_card,
            fg="#0f766e",
            padx=14,
            pady=10,
            relief=tk.SOLID,
            bd=1
        )
        card.pack(fill=tk.X, pady=(0, 8))

        curr = database.get_setting("currency_symbol", "Tk")

        # Subtotal
        r1 = tk.Frame(card, bg=self.c_card)
        r1.pack(fill=tk.X, pady=3)
        tk.Label(r1, text="Subtotal:", font=("Segoe UI", 11), bg=self.c_card).pack(side=tk.LEFT)
        self.subtotal_lbl = tk.Label(r1, text=f"{curr} 0.00", font=("Segoe UI", 12, "bold"), bg=self.c_card)
        self.subtotal_lbl.pack(side=tk.RIGHT)

        # Discount Row (Entry + % / Fixed Toggle)
        r2 = tk.Frame(card, bg=self.c_card)
        r2.pack(fill=tk.X, pady=3)
        tk.Label(r2, text="Discount (F4):", font=("Segoe UI", 10), bg=self.c_card).pack(side=tk.LEFT)

        self.disc_type_var = tk.StringVar(value="fixed")
        disc_toggle = tk.Button(
            r2,
            textvariable=self.disc_type_var,
            font=("Segoe UI", 8, "bold"),
            bg="#e2e8f0",
            relief=tk.FLAT,
            padx=4,
            command=self._toggle_discount_type
        )
        disc_toggle.pack(side=tk.LEFT, padx=(4, 6))

        self.discount_entry = tk.Entry(r2, font=("Segoe UI", 10, "bold"), width=10, bd=1, relief=tk.SOLID, justify=tk.RIGHT)
        self.discount_entry.insert(0, "0")
        self.discount_entry.pack(side=tk.RIGHT, ipady=2)
        self.discount_entry.bind("<KeyRelease>", lambda e: self._recalculate())
        self.discount_entry.bind("<Return>", lambda e: self.paid_entry.focus_set())

        # Net Total Payable (Highlighted Big Box)
        total_box = tk.Frame(card, bg="#f0fdfa", bd=1, relief=tk.SOLID, padx=8, pady=6)
        total_box.pack(fill=tk.X, pady=6)

        tk.Label(
            total_box,
            text="NET TOTAL:",
            font=("Segoe UI", 11, "bold"),
            bg="#f0fdfa",
            fg="#0f766e"
        ).pack(side=tk.LEFT)

        self.net_total_lbl = tk.Label(
            total_box,
            text=f"{curr} 0.00",
            font=("Segoe UI", 16, "bold"),
            bg="#f0fdfa",
            fg="#0f766e"
        )
        self.net_total_lbl.pack(side=tk.RIGHT)

        # Paid Amount (F5)
        r3 = tk.Frame(card, bg=self.c_card)
        r3.pack(fill=tk.X, pady=4)
        tk.Label(r3, text="Paid Amount (F5):", font=("Segoe UI", 10, "bold"), bg=self.c_card).pack(side=tk.LEFT)
        self.paid_entry = tk.Entry(r3, font=("Segoe UI", 11, "bold"), width=12, bd=1, relief=tk.SOLID, justify=tk.RIGHT)
        self.paid_entry.insert(0, "0")
        self.paid_entry.pack(side=tk.RIGHT, ipady=2)
        self.paid_entry.bind("<KeyRelease>", lambda e: self._recalculate(update_due_only=True))
        self.paid_entry.bind("<Return>", lambda e: self.save_and_print_voucher())

        # Balance Due
        r4 = tk.Frame(card, bg=self.c_card)
        r4.pack(fill=tk.X, pady=3)
        tk.Label(r4, text="Balance Due:", font=("Segoe UI", 10, "bold"), bg=self.c_card).pack(side=tk.LEFT)
        self.due_lbl = tk.Label(r4, text=f"{curr} 0.00", font=("Segoe UI", 12, "bold"), bg=self.c_card, fg="#059669")
        self.due_lbl.pack(side=tk.RIGHT)

        # Payment Method & Remarks
        r5 = tk.Frame(card, bg=self.c_card)
        r5.pack(fill=tk.X, pady=4)
        tk.Label(r5, text="Method (F6):", font=("Segoe UI", 10), bg=self.c_card).pack(side=tk.LEFT)
        self.method_combo = ttk.Combobox(r5, values=["CASH", "CARD", "bKash / MFS", "DUE"], width=14, state="readonly")
        self.method_combo.set("CASH")
        self.method_combo.pack(side=tk.LEFT, padx=(6, 0))

        # Main Big Action Button: SAVE & PRINT (F12)
        self.save_btn = tk.Button(
            card,
            text="🖨️ SAVE & PRINT (F12)",
            font=("Segoe UI", 13, "bold"),
            bg="#0d9488",
            fg="#ffffff",
            activebackground="#0f766e",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            pady=10,
            command=self.save_and_print_voucher
        )
        self.save_btn.pack(fill=tk.X, pady=(10, 4))

        # Secondary Button: Reprint Last Voucher
        self.reprint_btn = tk.Button(
            card,
            text="🔁 Reprint Last Voucher (F11)",
            font=("Segoe UI", 9),
            bg="#f1f5f9",
            fg="#334155",
            activebackground="#e2e8f0",
            relief=tk.FLAT,
            command=self._reprint_last_voucher
        )
        self.reprint_btn.pack(fill=tk.X)

    def _build_recent_vouchers_card(self, parent):
        card = tk.LabelFrame(
            parent,
            text=" Recent Vouchers & History ",
            font=("Segoe UI", 9, "bold"),
            bg=self.c_card,
            fg="#334155",
            padx=8,
            pady=6,
            relief=tk.SOLID,
            bd=1
        )
        card.pack(fill=tk.BOTH, expand=True)

        # Quick Search & History Button Toolbar
        top_bar = tk.Frame(card, bg=self.c_card)
        top_bar.pack(fill=tk.X, pady=(0, 6))

        tk.Label(top_bar, text="🔍", font=("Segoe UI", 9), bg=self.c_card).pack(side=tk.LEFT)
        self.recent_search_var = tk.StringVar(master=self.root)
        self.recent_search_entry = tk.Entry(
            top_bar,
            textvariable=self.recent_search_var,
            font=("Segoe UI", 9),
            bd=1,
            relief=tk.SOLID
        )
        self.recent_search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, ipady=2)
        self.recent_search_var.trace_add("write", lambda *args: self._filter_recent_vouchers())

        # Full History button
        tk.Button(
            top_bar,
            text="📋 All History (F7)",
            font=("Segoe UI", 8, "bold"),
            bg="#0d9488",
            fg="#ffffff",
            activebackground="#0f766e",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=8,
            pady=2,
            command=self.open_history_window
        ).pack(side=tk.RIGHT)

        cols = ("vno", "time", "patient", "phone", "total", "status")

        tree_frame = tk.Frame(card, bg=self.c_card)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        rec_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        self.recent_tree = ttk.Treeview(
            tree_frame,
            columns=cols,
            show="headings",
            height=6,
            selectmode="browse",
            yscrollcommand=rec_scroll.set
        )
        rec_scroll.config(command=self.recent_tree.yview)
        rec_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.recent_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.recent_tree.heading("vno", text="Voucher No")
        self.recent_tree.heading("time", text="Time")
        self.recent_tree.heading("patient", text="Patient")
        self.recent_tree.heading("phone", text="Phone")
        self.recent_tree.heading("total", text="Total")
        self.recent_tree.heading("status", text="Status")

        self.recent_tree.column("vno", width=110, anchor=tk.W)
        self.recent_tree.column("time", width=48, anchor=tk.CENTER)
        self.recent_tree.column("patient", width=105, anchor=tk.W)
        self.recent_tree.column("phone", width=92, anchor=tk.W)
        self.recent_tree.column("total", width=52, anchor=tk.E)
        self.recent_tree.column("status", width=55, anchor=tk.CENTER)

        self.recent_tree.tag_configure("paid_tag", foreground="#059669")
        self.recent_tree.tag_configure("due_tag", foreground="#dc2626")
        self.recent_tree.tag_configure("partial_tag", foreground="#d97706")

        self.recent_tree.bind("<Double-Button-1>", lambda e: self._on_double_click_recent())

        # Action Toolbar below recent tree
        rec_actions = tk.Frame(card, bg=self.c_card)
        rec_actions.pack(fill=tk.X, pady=(6, 2))

        tk.Button(
            rec_actions,
            text="👁️ Full Info",
            font=("Segoe UI", 8, "bold"),
            bg="#f1f5f9",
            fg="#0f766e",
            activebackground="#e2e8f0",
            relief=tk.FLAT,
            padx=7,
            command=self._inspect_selected_voucher
        ).pack(side=tk.LEFT, padx=(0, 2))

        tk.Button(
            rec_actions,
            text="🖨️ Re-Print",
            font=("Segoe UI", 8),
            bg="#f1f5f9",
            fg="#1e293b",
            activebackground="#e2e8f0",
            relief=tk.FLAT,
            padx=7,
            command=self._reprint_selected_recent
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            rec_actions,
            text="📄 PDF",
            font=("Segoe UI", 8),
            bg="#f1f5f9",
            fg="#0f766e",
            activebackground="#e2e8f0",
            relief=tk.FLAT,
            padx=7,
            command=self._view_selected_voucher_pdf
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            rec_actions,
            text="📜 JSON",
            font=("Segoe UI", 8),
            bg="#f1f5f9",
            fg="#2563eb",
            activebackground="#e2e8f0",
            relief=tk.FLAT,
            padx=7,
            command=self._view_selected_voucher_json
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            rec_actions,
            text="📂 PDF Folder",
            font=("Segoe UI", 8),
            bg="#f1f5f9",
            fg="#334155",
            activebackground="#e2e8f0",
            relief=tk.FLAT,
            padx=7,
            command=self._open_vouchers_pdf_folder
        ).pack(side=tk.RIGHT)

    def _build_shortcut_bar(self):
        bar = tk.Frame(self.root, bg="#1e293b", height=32, padx=12)
        bar.pack(fill=tk.X, side=tk.BOTTOM)

        shortcuts = [
            ("F1", "New"),
            ("F2", "Search"),
            ("F3", "Name"),
            ("F4", "Discount"),
            ("F5", "Paid"),
            ("F6", "Method"),
            ("F7", "History"),
            ("F8", "Admin"),
            ("F9", "Backup"),
            ("F11", "Reprint"),
            ("F12", "SAVE & PRINT"),
            ("Del", "Remove"),
            ("Esc", "Close Suggestions"),
        ]

        for key, desc in shortcuts:
            pill = tk.Frame(bar, bg="#334155", padx=5, pady=2)
            pill.pack(side=tk.LEFT, padx=2, pady=4)
            tk.Label(pill, text=key, font=("Segoe UI", 8, "bold"), bg="#334155", fg="#38bdf8").pack(side=tk.LEFT)
            tk.Label(pill, text=f":{desc}", font=("Segoe UI", 8), bg="#334155", fg="#cbd5e1").pack(side=tk.LEFT)

        # Status note — persistent, colour-coded
        self.footer_status = tk.Label(bar, text="✔ System Ready", font=("Segoe UI", 8, "italic"), bg="#1e293b", fg="#4ade80")
        self.footer_status.pack(side=tk.RIGHT, padx=6)

    # ==========================================================================
    # KEYBOARD NAVIGATION & ZERO-MOUSE SHORTCUTS
    # ==========================================================================

    def _bind_global_shortcuts(self):
        self.root.bind("<F1>", lambda e: self.reset_form())
        self.root.bind("<F2>", lambda e: self.search_entry.focus_set())
        self.root.bind("<F3>", lambda e: self.name_entry.focus_set())
        self.root.bind("<F4>", lambda e: self.discount_entry.focus_set())
        self.root.bind("<F5>", lambda e: self.paid_entry.focus_set())
        self.root.bind("<F6>", lambda e: self._cycle_payment_method())
        self.root.bind("<F7>", lambda e: self.open_history_window())
        self.root.bind("<F8>", lambda e: self._open_admin())
        self.root.bind("<F9>", lambda e: self._trigger_backup())
        self.root.bind("<F11>", lambda e: self._reprint_last_voucher())
        self.root.bind("<F12>", lambda e: self.save_and_print_voucher())
        self.root.bind("<Control-p>", lambda e: self.save_and_print_voucher())
        self.root.bind("<Control-P>", lambda e: self.save_and_print_voucher())
        self.root.bind("<Delete>", lambda e: self._remove_selected_cart_item())
        self.root.bind("<Control-d>", lambda e: self._remove_selected_cart_item())
        self.root.bind("<Escape>", lambda e: self._hide_suggest())

    # ==========================================================================
    # AUTOCOMPLETE LOGIC (ZERO-MOUSE OPTIMIZATION)
    # ==========================================================================

    def _on_search_keyrelease(self, event):
        # Ignore navigation keys
        if event.keysym in ("Up", "Down", "Return", "Escape"):
            return

        query = self.search_entry.get().strip()
        if not query:
            self._hide_suggest()
            return

        matches = database.search_tests(query, limit=10)
        self.autocomplete_tests = matches

        if matches:
            self.suggest_box.delete(0, tk.END)
            for m in matches:
                # Format: [Code] Name (Price Tk)
                display_str = f"[{m['code']}] {m['name']}  --  Tk {m['price']:.2f}"
                self.suggest_box.insert(tk.END, display_str)
            self._show_suggest()
            self.suggest_box.selection_clear(0, tk.END)
            self.suggest_box.selection_set(0)
            self.suggest_box.activate(0)
        else:
            self._hide_suggest()

    def _show_suggest(self):
        if not self.suggest_box_visible:
            # Place suggest box right under the search entry
            self.suggest_box.pack(fill=tk.X, pady=(0, 6), before=self.cart_tree.master)
            self.suggest_box_visible = True

    def _hide_suggest(self):
        if self.suggest_box_visible:
            self.suggest_box.pack_forget()
            self.suggest_box_visible = False

    def _on_search_down_arrow(self, event):
        if self.suggest_box_visible and self.suggest_box.size() > 0:
            cur = self.suggest_box.curselection()
            next_idx = (cur[0] + 1) if cur else 0
            if next_idx < self.suggest_box.size():
                self.suggest_box.selection_clear(0, tk.END)
                self.suggest_box.selection_set(next_idx)
                self.suggest_box.activate(next_idx)
            return "break"

    def _on_search_up_arrow(self, event):
        if self.suggest_box_visible and self.suggest_box.size() > 0:
            cur = self.suggest_box.curselection()
            prev_idx = (cur[0] - 1) if cur else 0
            if prev_idx >= 0:
                self.suggest_box.selection_clear(0, tk.END)
                self.suggest_box.selection_set(prev_idx)
                self.suggest_box.activate(prev_idx)
            return "break"

    def _on_search_enter(self, event):
        query = self.search_entry.get().strip()
        if not query:
            return

        # Check for exact code match first (fastest path for trained receptionists)
        exact_test = database.get_test_by_exact_code(query)
        if exact_test:
            self._add_test_to_cart(exact_test)
            self.search_entry.delete(0, tk.END)
            self._hide_suggest()
            return

        # If suggest box is visible and has selection
        if self.suggest_box_visible and self.autocomplete_tests:
            cur = self.suggest_box.curselection()
            selected_idx = cur[0] if cur else 0
            if selected_idx < len(self.autocomplete_tests):
                self._add_test_to_cart(self.autocomplete_tests[selected_idx])
                self.search_entry.delete(0, tk.END)
                self._hide_suggest()
                return

    def _add_selected_suggest(self):
        if self.autocomplete_tests:
            cur = self.suggest_box.curselection()
            selected_idx = cur[0] if cur else 0
            if selected_idx < len(self.autocomplete_tests):
                self._add_test_to_cart(self.autocomplete_tests[selected_idx])
                self.search_entry.delete(0, tk.END)
                self._hide_suggest()
                self.search_entry.focus_set()

    # ==========================================================================
    # CART & BILLING CALCULATIONS
    # ==========================================================================

    def _add_test_to_cart(self, test: Dict[str, Any]):
        # Check if already in cart -> increment quantity with user notice
        for item in self.cart_items:
            if item["test_id"] == test["id"]:
                item["quantity"] += 1
                item["item_total"] = round(item["price"] * item["quantity"], 2)
                self._refresh_cart_view()
                self._recalculate()
                self._set_status(f"⟳  Qty updated: [{test['code']}] {test['name']} — Qty {item['quantity']}", color="#f59e0b")
                self._flash_cart()
                return

        # Add new line item
        self.cart_items.append({
            "test_id": test["id"],
            "test_code": test["code"],
            "test_name": test["name"],
            "sample_type": test.get("sample_type", "Blood"),
            "price": float(test["price"]),
            "quantity": 1,
            "item_total": float(test["price"])
        })
        self._refresh_cart_view()
        self._recalculate()
        self._set_status(f"✔ Added: [{test['code']}] {test['name']}  —  Tk {test['price']:.2f}", color="#4ade80")
        self._flash_cart()

    def _remove_selected_cart_item(self):
        selected = self.cart_tree.selection()
        if not selected:
            return
        idx = self.cart_tree.index(selected[0])
        if 0 <= idx < len(self.cart_items):
            del self.cart_items[idx]
            self._refresh_cart_view()
            self._recalculate()

    def _clear_cart(self):
        self.cart_items.clear()
        self._refresh_cart_view()
        self._recalculate()

    def _refresh_cart_view(self):
        self.cart_tree.delete(*self.cart_tree.get_children())
        for idx, item in enumerate(self.cart_items, 1):
            self.cart_tree.insert("", tk.END, values=(
                idx,
                item["test_code"],
                item["test_name"],
                item["sample_type"],
                item["quantity"],
                f"{item['price']:.2f}",
                f"{item['item_total']:.2f}"
            ))
        self.item_count_lbl.configure(text=f"Total Tests: {len(self.cart_items)}")

    def _toggle_discount_type(self):
        new_type = "%" if self.disc_type_var.get() == "fixed" else "fixed"
        self.disc_type_var.set(new_type)
        self._recalculate()

    def _recalculate(self, update_due_only: bool = False):
        curr = database.get_setting("currency_symbol", "Tk")
        subtotal = sum(item["item_total"] for item in self.cart_items)
        self.subtotal_lbl.configure(text=f"{curr} {subtotal:.2f}")

        # Discount
        disc_val_str = self.discount_entry.get().strip() or "0"
        try:
            disc_val = float(disc_val_str)
        except ValueError:
            disc_val = 0.0

        if self.disc_type_var.get() == "%":
            disc_amount = round((subtotal * disc_val) / 100.0, 2)
        else:
            disc_amount = round(disc_val, 2)

        net_total = max(0.0, round(subtotal - disc_amount, 2))
        self.net_total_lbl.configure(text=f"{curr} {net_total:.2f}")

        # Paid & Due
        if not update_due_only:
            # Default paid amount is full payable
            self.paid_entry.delete(0, tk.END)
            self.paid_entry.insert(0, f"{net_total:.0f}")

        paid_str = self.paid_entry.get().strip() or "0"
        try:
            paid_amount = float(paid_str)
        except ValueError:
            paid_amount = 0.0

        due_amount = max(0.0, round(net_total - paid_amount, 2))
        self.due_lbl.configure(text=f"{curr} {due_amount:.2f}")

        if due_amount > 0:
            self.due_lbl.configure(fg="#dc2626")  # Alert red
        else:
            self.due_lbl.configure(fg="#059669")  # Green

    # ==========================================================================
    # LIVE CLOCK & COUNTER HELPERS
    # ==========================================================================

    def _update_clock(self):
        """Refresh live clock label and today's patient counter every second."""
        now = datetime.now()
        self.clock_lbl.configure(text=now.strftime("%I:%M:%S %p"))
        # Update today's patient count every minute (on the :00 second)
        if now.second == 0 or not hasattr(self, "_last_counter_minute") or self._last_counter_minute != now.minute:
            self._last_counter_minute = now.minute
            self._refresh_today_counter()
        self.root.after(1000, self._update_clock)

    def _refresh_today_counter(self):
        """Query today's voucher count and update the header badge."""
        try:
            summary = database.get_daily_summary(datetime.now().strftime("%Y-%m-%d"))
            count = summary.get("total_vouchers", 0)
            self.today_counter_lbl.configure(text=f"Today: {count} patient{'s' if count != 1 else ''}")
        except Exception:
            pass

    def _schedule_recent_refresh(self):
        """Auto-refresh recent vouchers list every 60 seconds."""
        self.refresh_recent_vouchers()
        self.root.after(60000, self._schedule_recent_refresh)

    def _set_status(self, msg: str, color: str = "#4ade80", auto_clear_ms: int = 4000):
        """Set footer status bar with auto-clear after timeout."""
        self.footer_status.configure(text=msg, fg=color)
        if self._status_clear_after_id:
            try:
                self.root.after_cancel(self._status_clear_after_id)
            except Exception:
                pass
        self._status_clear_after_id = self.root.after(
            auto_clear_ms, lambda: self.footer_status.configure(text="✔ System Ready", fg="#4ade80")
        )

    def _flash_cart(self):
        """Briefly highlight the cart item count label to confirm an add."""
        orig_fg = "#0f766e"
        self.item_count_lbl.configure(fg="#f59e0b")
        self.root.after(350, lambda: self.item_count_lbl.configure(fg=orig_fg))

    def _cycle_payment_method(self):
        """F6: Cycle through payment methods sequentially."""
        methods = ["CASH", "CARD", "bKash / MFS", "DUE"]
        current = self.method_combo.get()
        try:
            next_idx = (methods.index(current) + 1) % len(methods)
        except ValueError:
            next_idx = 0
        self.method_combo.set(methods[next_idx])
        self._set_status(f"💳 Payment Method: {methods[next_idx]}", color="#38bdf8", auto_clear_ms=2000)

    # ==========================================================================
    # SAVE & SILENT PRINT ACTION
    # ==========================================================================

    def save_and_print_voucher(self):
        patient_name = self.name_entry.get().strip()
        if not patient_name:
            messagebox.showwarning("Incomplete Form", "Please enter Patient Name before printing.")
            self.name_entry.focus_set()
            return

        if not self.cart_items:
            messagebox.showwarning("Empty Cart", "Please add at least one diagnostic test to the voucher.")
            self.search_entry.focus_set()
            return

        # Prepare payload
        age_val = self.age_entry.get().strip()
        age = int(age_val) if age_val.isdigit() else 0

        patient_data = {
            "name": patient_name,
            "age": age,
            "gender": self.gender_combo.get(),
            "phone": self.phone_entry.get().strip(),
            "referred_by": self.ref_entry.get().strip() or "Self / General",
            "created_by": "Reception"
        }

        disc_val_str = self.discount_entry.get().strip() or "0"
        try:
            disc_val = float(disc_val_str)
        except ValueError:
            disc_val = 0.0

        discount_data = {
            "type": "percent" if self.disc_type_var.get() == "%" else "fixed",
            "value": disc_val
        }

        paid_str = self.paid_entry.get().strip() or "0"
        try:
            paid = float(paid_str)
        except ValueError:
            paid = 0.0

        payment_data = {
            "paid_amount": paid,
            "payment_method": self.method_combo.get(),
            "remarks": ""
        }

        try:
            # 1. Save atomically to SQLite database
            voucher = database.create_voucher(
                patient_data=patient_data,
                items=self.cart_items,
                discount_data=discount_data,
                payment_data=payment_data
            )
            self.last_created_voucher = voucher

            # 2. Automatically generate and archive PDF & JSON text copies
            pdf_path = None
            try:
                pdf_path = pdf_generator.generate_voucher_pdf(voucher)
            except Exception as pdf_err:
                print(f"[Dashboard] Warning: PDF archiving failed: {pdf_err}")

            json_path = None
            try:
                json_path = data_vault.save_voucher_to_json(voucher)
                # Background async sync to MongoDB Atlas if configured
                data_vault.trigger_async_mongo_sync(voucher)
            except Exception as json_err:
                print(f"[Dashboard] Warning: JSON archiving failed: {json_err}")

            # 3. Trigger Silent Print (No Dialogs!)
            print_res = printer_engine.print_voucher_silently(voucher)
            
            # Show toast / footer update
            v_no = voucher["voucher_no"]
            sync_notes = []
            if pdf_path: sync_notes.append("PDF")
            if json_path: sync_notes.append("JSON")
            note_str = f" + {' & '.join(sync_notes)} Saved" if sync_notes else ""
            self._set_status(
                f"✅ Saved & Printed: {v_no}{note_str}  |  {print_res['message']}",
                color="#4ade80",
                auto_clear_ms=8000
            )
            self._refresh_today_counter()

            # 4. Refresh Recent List & Reset for Next Patient
            self.refresh_recent_vouchers()
            self.reset_form()

        except Exception as e:
            messagebox.showerror("Printing / Database Error", f"Failed to save and print voucher:\n{e}")

    def _reprint_last_voucher(self):
        if not self.last_created_voucher:
            messagebox.showinfo("No Previous Voucher", "No voucher has been created in this session yet.")
            return

        res = printer_engine.print_voucher_silently(self.last_created_voucher)
        self.footer_status.configure(text=f"🔁 Re-printed: {self.last_created_voucher['voucher_no']}")
        messagebox.showinfo("Reprint Sent", f"Reprint job sent silently to printer:\n{res['message']}")

    # ==========================================================================
    # FORM RESET & STATE MANAGEMENT
    # ==========================================================================

    def reset_form(self):
        """Reset form fields and autofocus Patient Name (F1 workflow)."""
        self.name_entry.delete(0, tk.END)
        self.age_entry.delete(0, tk.END)
        self.gender_combo.set("Male")
        self.phone_entry.delete(0, tk.END)
        self.ref_entry.delete(0, tk.END)
        self.ref_entry.insert(0, "Self / General")

        self.search_entry.delete(0, tk.END)
        self._hide_suggest()

        self.cart_items.clear()
        self._refresh_cart_view()

        self.discount_entry.delete(0, tk.END)
        self.discount_entry.insert(0, "0")
        self.disc_type_var.set("fixed")

        self.paid_entry.delete(0, tk.END)
        self.paid_entry.insert(0, "0")
        self.method_combo.set("CASH")

        self._recalculate()
        self.name_entry.focus_set()

    def refresh_recent_vouchers(self):
        """Fetch latest vouchers and populate recent table (with search filtering)."""
        self._recent_vouchers_cache = database.get_recent_vouchers(limit=40)
        self._filter_recent_vouchers()

    def _filter_recent_vouchers(self):
        """Filter recent table locally using quick search bar."""
        query_var = getattr(self, "recent_search_var", None)
        q = query_var.get().strip().lower() if query_var else ""
        cache = getattr(self, "_recent_vouchers_cache", [])

        if not q:
            self._populate_recent_tree(cache)
            return

        filtered = []
        for v in cache:
            v_no = str(v.get("voucher_no", "")).lower()
            p_name = str(v.get("patient_name", "")).lower()
            p_phone = str(v.get("patient_phone", "")).lower()
            if q in v_no or q in p_name or q in p_phone:
                filtered.append(v)
        self._populate_recent_tree(filtered)

    def _populate_recent_tree(self, vouchers: List[Dict[str, Any]]):
        self.recent_tree.delete(*self.recent_tree.get_children())
        for v in vouchers:
            raw_time = str(v.get("created_at", ""))
            disp_time = raw_time[11:16] if len(raw_time) >= 16 else ""  # HH:MM
            status = v.get("payment_status", "PAID")
            tag = "paid_tag" if status == "PAID" else ("due_tag" if status == "DUE" else "partial_tag")
            self.recent_tree.insert("", tk.END, values=(
                v["voucher_no"],
                disp_time,
                v["patient_name"],
                v.get("patient_phone", ""),
                f"{v['total_amount']:.0f}",
                status
            ), tags=(tag,))

    def _on_double_click_recent(self):
        selected = self.recent_tree.selection()
        if not selected:
            return
        item_vals = self.recent_tree.item(selected[0])["values"]
        v_no = item_vals[0]
        self.open_history_window(default_selected_vno=v_no)

    def _inspect_selected_voucher(self):
        selected = self.recent_tree.selection()
        if not selected:
            self.open_history_window()
            return
        item_vals = self.recent_tree.item(selected[0])["values"]
        v_no = item_vals[0]
        self.open_history_window(default_selected_vno=v_no)

    def _reprint_selected_recent(self):
        selected = self.recent_tree.selection()
        if not selected:
            messagebox.showinfo("Select Voucher", "Please select a voucher from the list first.", parent=self.root)
            return
        item_vals = self.recent_tree.item(selected[0])["values"]
        v_no = item_vals[0]
        v = database.get_voucher_by_no(v_no)
        if v:
            res = printer_engine.print_voucher_silently(v)
            self._set_status(f"🔁 Re-printed: {v_no}", color="#38bdf8", auto_clear_ms=6000)
            messagebox.showinfo("Reprint Sent", f"Reprinting voucher {v_no}:\n{res['message']}", parent=self.root)

    def _view_selected_voucher_pdf(self):
        selected = self.recent_tree.selection()
        if not selected:
            messagebox.showinfo("Select Voucher", "Please select a voucher from the list first.", parent=self.root)
            return
        item_vals = self.recent_tree.item(selected[0])["values"]
        v_no = item_vals[0]
        v = database.get_voucher_by_no(v_no)
        if not v:
            messagebox.showerror("Error", f"Voucher {v_no} not found.", parent=self.root)
            return

        pdf_path = pdf_generator.generate_voucher_pdf(v)
        if pdf_path and os.path.exists(pdf_path):
            try:
                os.startfile(pdf_path)
            except Exception as e:
                messagebox.showerror("Error", f"Could not launch PDF viewer:\n{e}", parent=self.root)
        else:
            messagebox.showerror("Error", f"Could not generate PDF for voucher {v_no}.", parent=self.root)

    def _open_vouchers_pdf_folder(self):
        pdf_dir = pdf_generator.get_voucher_pdf_directory()
        try:
            if not os.path.exists(pdf_dir):
                os.makedirs(pdf_dir, exist_ok=True)
            os.startfile(pdf_dir)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open Vouchers PDF folder:\n{e}", parent=self.root)

    def _view_selected_voucher_json(self):
        selected = self.recent_tree.selection()
        if not selected:
            messagebox.showinfo("Select Voucher", "Please select a voucher from the list first.", parent=self.root)
            return
        item_vals = self.recent_tree.item(selected[0])["values"]
        v_no = item_vals[0]
        v = database.get_voucher_by_no(v_no)
        if not v:
            messagebox.showerror("Error", f"Voucher {v_no} not found.", parent=self.root)
            return

        json_path = data_vault.save_voucher_to_json(v)
        if json_path and os.path.exists(json_path):
            try:
                os.startfile(json_path)
            except Exception as e:
                messagebox.showerror("Error", f"Could not launch text/JSON viewer:\n{e}", parent=self.root)
        else:
            messagebox.showerror("Error", f"Could not generate or find JSON for voucher {v_no}.", parent=self.root)

    def _open_vouchers_json_folder(self):
        json_dir = data_vault.get_voucher_json_directory()
        try:
            if not os.path.exists(json_dir):
                os.makedirs(json_dir, exist_ok=True)
            os.startfile(json_dir)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open JSON text folder:\n{e}", parent=self.root)

    # ==========================================================================
    # FULL HISTORY & PATIENT RECORDS SUITE (F7)
    # ==========================================================================

    def open_history_window(self, default_selected_vno: Optional[str] = None):
        """
        Open the full Hospital Voucher Records & Patient History Suite.
        Provides multi-criteria search, date filters, itemized test breakdown,
        financial inspector, re-printing, and due collection.
        """
        win = tk.Toplevel(self.root)
        win.title("📋 Hospital Voucher Records & Patient History Suite")
        win.geometry("1220x760")
        win.minsize(1050, 650)
        win.configure(bg="#eef2f6")
        win.transient(self.root)

        # Center on root
        try:
            rx = self.root.winfo_rootx()
            ry = self.root.winfo_rooty()
            rw = self.root.winfo_width()
            rh = self.root.winfo_height()
            win.geometry(f"1220x760+{max(10, rx + (rw - 1220) // 2)}+{max(10, ry + (rh - 760) // 2)}")
        except Exception:
            pass

        # ----------------------------------------------------------------------
        # 1. HEADER WITH LIVE SUMMARY METRICS
        # ----------------------------------------------------------------------
        hdr_frame = tk.Frame(win, bg="#0f172a", height=60, padx=16)
        hdr_frame.pack(fill=tk.X, side=tk.TOP)

        hdr_left = tk.Frame(hdr_frame, bg="#0f172a")
        hdr_left.pack(side=tk.LEFT, pady=8)

        tk.Label(
            hdr_left,
            text="📋 Hospital Voucher Records & Patient History",
            font=("Segoe UI", 13, "bold"),
            fg="#38bdf8",
            bg="#0f172a"
        ).pack(anchor="w")

        tk.Label(
            hdr_left,
            text="Search all historical patient records, view itemized tests, silent reprint, and collect dues",
            font=("Segoe UI", 8),
            fg="#94a3b8",
            bg="#0f172a"
        ).pack(anchor="w")

        # Summary Metrics on the Right
        hdr_right = tk.Frame(hdr_frame, bg="#0f172a")
        hdr_right.pack(side=tk.RIGHT, pady=6)

        stat_cards = {}
        for key, title, fg_color in [
            ("count", "VOUCHERS", "#e2e8f0"),
            ("billed", "TOTAL BILLED", "#38bdf8"),
            ("collected", "COLLECTED", "#4ade80"),
            ("due", "DUE BALANCE", "#f87171"),
        ]:
            pill = tk.Frame(hdr_right, bg="#1e293b", padx=10, pady=3, relief=tk.FLAT)
            pill.pack(side=tk.LEFT, padx=4)
            tk.Label(pill, text=title, font=("Segoe UI", 7, "bold"), fg="#94a3b8", bg="#1e293b").pack(anchor="w")
            lbl = tk.Label(pill, text="--", font=("Segoe UI", 10, "bold"), fg=fg_color, bg="#1e293b")
            lbl.pack(anchor="w")
            stat_cards[key] = lbl

        # ----------------------------------------------------------------------
        # 2. FILTER & SEARCH TOOLBAR CARD
        # ----------------------------------------------------------------------
        filter_card = tk.Frame(win, bg="#ffffff", padx=12, pady=8, bd=1, relief=tk.SOLID)
        filter_card.pack(fill=tk.X, padx=12, pady=(10, 6))

        # Row 1: Search Query + Quick Date Presets + Status Filter
        r1 = tk.Frame(filter_card, bg="#ffffff")
        r1.pack(fill=tk.X, pady=2)

        tk.Label(r1, text="🔍 Search:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#0f172a").pack(side=tk.LEFT, padx=(0, 4))
        search_var = tk.StringVar(master=win)
        search_entry = tk.Entry(r1, textvariable=search_var, font=("Segoe UI", 10), width=26, bd=1, relief=tk.SOLID)
        search_entry.pack(side=tk.LEFT, padx=(0, 10), ipady=3)

        tk.Label(r1, text="Presets:", font=("Segoe UI", 9), bg="#ffffff", fg="#475569").pack(side=tk.LEFT, padx=(0, 4))

        date_from_var = tk.StringVar(master=win)
        date_to_var = tk.StringVar(master=win)
        active_preset = tk.StringVar(master=win, value="All")

        def _apply_preset(name: str):
            active_preset.set(name)
            today_str = datetime.now().strftime("%Y-%m-%d")
            if name == "Today":
                date_from_var.set(today_str)
                date_to_var.set(today_str)
            elif name == "Yesterday":
                yest_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                date_from_var.set(yest_str)
                date_to_var.set(yest_str)
            elif name == "Last 7 Days":
                d7_str = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
                date_from_var.set(d7_str)
                date_to_var.set(today_str)
            elif name == "This Month":
                m_str = datetime.now().strftime("%Y-%m-01")
                date_from_var.set(m_str)
                date_to_var.set(today_str)
            elif name == "All":
                date_from_var.set("")
                date_to_var.set("")
            _load_history()

        for pname in ("All", "Today", "Yesterday", "Last 7 Days", "This Month"):
            btn = tk.Button(
                r1,
                text=pname,
                font=("Segoe UI", 8),
                bg="#f1f5f9",
                fg="#334155",
                activebackground="#e2e8f0",
                relief=tk.FLAT,
                padx=6,
                pady=1,
                command=lambda p=pname: _apply_preset(p)
            )
            btn.pack(side=tk.LEFT, padx=2)

        # Status Combobox
        tk.Label(r1, text="Status:", font=("Segoe UI", 9), bg="#ffffff", fg="#475569").pack(side=tk.LEFT, padx=(10, 4))
        status_combo = ttk.Combobox(r1, values=["ALL", "PAID", "DUE", "PARTIAL"], width=10, state="readonly")
        status_combo.set("ALL")
        status_combo.pack(side=tk.LEFT, padx=2)

        # Refresh & Reset Buttons
        tk.Button(
            r1,
            text="🔄 Refresh",
            font=("Segoe UI", 9, "bold"),
            bg="#0d9488",
            fg="#ffffff",
            activebackground="#0f766e",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=10,
            command=lambda: _load_history()
        ).pack(side=tk.RIGHT, padx=4)

        def _clear_all_filters():
            search_var.set("")
            date_from_var.set("")
            date_to_var.set("")
            status_combo.set("ALL")
            active_preset.set("All")
            _load_history()

        tk.Button(
            r1,
            text="✖ Clear",
            font=("Segoe UI", 9),
            bg="#f1f5f9",
            fg="#475569",
            relief=tk.FLAT,
            padx=8,
            command=_clear_all_filters
        ).pack(side=tk.RIGHT, padx=2)

        # Row 2: Date From - To manual inputs
        r2 = tk.Frame(filter_card, bg="#ffffff")
        r2.pack(fill=tk.X, pady=(4, 0))

        tk.Label(r2, text="From Date (YYYY-MM-DD):", font=("Segoe UI", 8), bg="#ffffff", fg="#64748b").pack(side=tk.LEFT, padx=(0, 4))
        df_entry = tk.Entry(r2, textvariable=date_from_var, font=("Segoe UI", 8), width=12, bd=1, relief=tk.SOLID)
        df_entry.pack(side=tk.LEFT, padx=(0, 10))

        tk.Label(r2, text="To Date (YYYY-MM-DD):", font=("Segoe UI", 8), bg="#ffffff", fg="#64748b").pack(side=tk.LEFT, padx=(0, 4))
        dt_entry = tk.Entry(r2, textvariable=date_to_var, font=("Segoe UI", 8), width=12, bd=1, relief=tk.SOLID)
        dt_entry.pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(
            r2,
            text="Apply Date Range",
            font=("Segoe UI", 8),
            bg="#f1f5f9",
            fg="#0f766e",
            relief=tk.FLAT,
            padx=6,
            command=lambda: _load_history()
        ).pack(side=tk.LEFT)

        # ----------------------------------------------------------------------
        # 3. MAIN SPLIT BODY (LEFT: TABLE, RIGHT: INSPECTOR)
        # ----------------------------------------------------------------------
        body_paned = tk.Frame(win, bg="#eef2f6")
        body_paned.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))

        # Left Column: Vouchers Table (~65% width)
        left_box = tk.LabelFrame(
            body_paned,
            text=" Matching Vouchers (Click: Full Details | Double-Click: Print) ",
            font=("Segoe UI", 9, "bold"),
            bg="#ffffff",
            fg="#0f766e",
            padx=8,
            pady=6,
            relief=tk.SOLID,
            bd=1
        )
        left_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        cols = ("vno", "date", "time", "patient", "phone", "doctor", "total", "paid", "due", "status")
        tree_scroll_y = ttk.Scrollbar(left_box, orient=tk.VERTICAL)
        tree_scroll_x = ttk.Scrollbar(left_box, orient=tk.HORIZONTAL)

        hist_tree = ttk.Treeview(
            left_box,
            columns=cols,
            show="headings",
            selectmode="browse",
            yscrollcommand=tree_scroll_y.set,
            xscrollcommand=tree_scroll_x.set
        )
        tree_scroll_y.config(command=hist_tree.yview)
        tree_scroll_x.config(command=hist_tree.xview)

        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        hist_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        headings = [
            ("vno", "Voucher No", 115, tk.W),
            ("date", "Date", 75, tk.CENTER),
            ("time", "Time", 48, tk.CENTER),
            ("patient", "Patient Name", 130, tk.W),
            ("phone", "Phone", 95, tk.W),
            ("doctor", "Ref. Doctor", 110, tk.W),
            ("total", "Total", 65, tk.E),
            ("paid", "Paid", 65, tk.E),
            ("due", "Due", 65, tk.E),
            ("status", "Status", 65, tk.CENTER),
        ]
        for col_id, heading_text, w, align in headings:
            hist_tree.heading(col_id, text=heading_text)
            hist_tree.column(col_id, width=w, anchor=align)

        hist_tree.tag_configure("paid_tag", foreground="#059669")
        hist_tree.tag_configure("due_tag", foreground="#dc2626")
        hist_tree.tag_configure("partial_tag", foreground="#d97706")

        # Right Column: Full Info Dossier Inspector (~35% width, fixed ~460px)
        right_box = tk.LabelFrame(
            body_paned,
            text=" Full Voucher Dossier & Test Breakdown ",
            font=("Segoe UI", 9, "bold"),
            bg="#ffffff",
            fg="#0f766e",
            padx=10,
            pady=8,
            relief=tk.SOLID,
            bd=1,
            width=460
        )
        right_box.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False)
        right_box.pack_propagate(False)

        # ----------------------------------------------------------------------
        # RIGHT INSPECTOR COMPONENTS
        # ----------------------------------------------------------------------
        # Top Voucher Identification Banner
        v_banner = tk.Frame(right_box, bg="#f0fdfa", bd=1, relief=tk.SOLID, padx=10, pady=8)
        v_banner.pack(fill=tk.X, pady=(0, 6))

        v_no_lbl = tk.Label(v_banner, text="-- SELECT A VOUCHER --", font=("Segoe UI", 12, "bold"), fg="#0f766e", bg="#f0fdfa")
        v_no_lbl.pack(anchor="w")

        v_meta_row = tk.Frame(v_banner, bg="#f0fdfa")
        v_meta_row.pack(fill=tk.X, pady=(2, 0))

        v_status_badge = tk.Label(v_meta_row, text="STATUS", font=("Segoe UI", 9, "bold"), fg="#ffffff", bg="#64748b", padx=6, pady=1)
        v_status_badge.pack(side=tk.LEFT)

        v_time_lbl = tk.Label(v_meta_row, text="Date: --", font=("Segoe UI", 8), fg="#475569", bg="#f0fdfa")
        v_time_lbl.pack(side=tk.LEFT, padx=8)

        v_printed_lbl = tk.Label(v_meta_row, text="", font=("Segoe UI", 8, "italic"), fg="#0f766e", bg="#f0fdfa")
        v_printed_lbl.pack(side=tk.RIGHT)

        # Patient Info Card
        p_card = tk.LabelFrame(right_box, text=" Patient Details ", font=("Segoe UI", 8, "bold"), bg="#ffffff", fg="#475569", padx=8, pady=4)
        p_card.pack(fill=tk.X, pady=3)

        p_name_lbl = tk.Label(p_card, text="Patient: --", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#0f172a")
        p_name_lbl.pack(anchor="w")

        p_demog_lbl = tk.Label(p_card, text="Age/Sex: --  |  Phone: --", font=("Segoe UI", 8), bg="#ffffff", fg="#475569")
        p_demog_lbl.pack(anchor="w")

        p_doctor_lbl = tk.Label(p_card, text="Referred By: --", font=("Segoe UI", 8), bg="#ffffff", fg="#475569")
        p_doctor_lbl.pack(anchor="w")

        # Tests Conducted Treeview (Full item breakdown)
        t_card = tk.LabelFrame(right_box, text=" Diagnostic Tests Conducted ", font=("Segoe UI", 8, "bold"), bg="#ffffff", fg="#475569", padx=4, pady=4)
        t_card.pack(fill=tk.BOTH, expand=True, pady=4)

        t_cols = ("code", "name", "qty", "rate", "total")
        t_scroll = ttk.Scrollbar(t_card, orient=tk.VERTICAL)
        tests_tree = ttk.Treeview(t_card, columns=t_cols, show="headings", height=5, selectmode="browse", yscrollcommand=t_scroll.set)
        t_scroll.config(command=tests_tree.yview)
        t_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        tests_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tests_tree.heading("code", text="Code")
        tests_tree.heading("name", text="Test Name")
        tests_tree.heading("qty", text="Qty")
        tests_tree.heading("rate", text="Rate")
        tests_tree.heading("total", text="Total")

        tests_tree.column("code", width=45, anchor=tk.CENTER)
        tests_tree.column("name", width=175, anchor=tk.W)
        tests_tree.column("qty", width=35, anchor=tk.CENTER)
        tests_tree.column("rate", width=55, anchor=tk.E)
        tests_tree.column("total", width=60, anchor=tk.E)

        # Financial Breakdown Summary Card
        f_card = tk.LabelFrame(right_box, text=" Financial Breakdown ", font=("Segoe UI", 8, "bold"), bg="#ffffff", fg="#475569", padx=8, pady=4)
        f_card.pack(fill=tk.X, pady=3)

        fin_grid = tk.Frame(f_card, bg="#ffffff")
        fin_grid.pack(fill=tk.X)

        curr = database.get_setting("currency_symbol", "Tk")
        f_subtotal_lbl = tk.Label(fin_grid, text="Subtotal: Tk 0.00", font=("Segoe UI", 8), bg="#ffffff", fg="#475569")
        f_subtotal_lbl.grid(row=0, column=0, sticky="w", padx=2, pady=1)

        f_discount_lbl = tk.Label(fin_grid, text="Discount: Tk 0.00", font=("Segoe UI", 8), bg="#ffffff", fg="#475569")
        f_discount_lbl.grid(row=0, column=1, sticky="w", padx=10, pady=1)

        f_net_lbl = tk.Label(fin_grid, text="Net: Tk 0.00", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#0f766e")
        f_net_lbl.grid(row=1, column=0, sticky="w", padx=2, pady=1)

        f_paid_lbl = tk.Label(fin_grid, text="Paid: Tk 0.00 (CASH)", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#059669")
        f_paid_lbl.grid(row=1, column=1, sticky="w", padx=10, pady=1)

        f_due_lbl = tk.Label(f_card, text="Balance Due: Tk 0.00", font=("Segoe UI", 10, "bold"), bg="#ffffff", fg="#059669")
        f_due_lbl.pack(anchor="w", pady=(2, 0))

        # Action Buttons Toolbar
        act_box = tk.Frame(right_box, bg="#ffffff")
        act_box.pack(fill=tk.X, pady=(6, 2))

        selected_voucher_holder = [None]

        def _print_inspected():
            v = selected_voucher_holder[0]
            if not v:
                return
            res = printer_engine.print_voucher_silently(v)
            messagebox.showinfo("Reprint Sent", f"Voucher {v['voucher_no']} sent to printer:\n{res['message']}", parent=win)
            database.increment_print_count(v["id"])
            v_refreshed = database.get_voucher_by_id(v["id"])
            if v_refreshed:
                _display_voucher_in_inspector(v_refreshed)

        def _open_pdf_inspected():
            v = selected_voucher_holder[0]
            if not v:
                return
            pdf_path = pdf_generator.generate_voucher_pdf(v)
            if pdf_path and os.path.exists(pdf_path):
                os.startfile(pdf_path)
            else:
                messagebox.showerror("Error", f"Could not open PDF for voucher {v['voucher_no']}.", parent=win)

        def _open_json_inspected():
            v = selected_voucher_holder[0]
            if not v:
                return
            json_path = data_vault.save_voucher_to_json(v)
            if json_path and os.path.exists(json_path):
                os.startfile(json_path)
            else:
                messagebox.showerror("Error", f"Could not open JSON for voucher {v['voucher_no']}.", parent=win)

        def _collect_due_inspected():
            v = selected_voucher_holder[0]
            if not v:
                return
            self._open_due_collection_dialog(v, on_success=lambda uv: _load_history(maintain_selection_vno=uv["voucher_no"]))

        def _copy_summary_inspected():
            v = selected_voucher_holder[0]
            if not v:
                return
            items_str = "\n".join([f"- {it.get('test_name')} (Tk {it.get('item_total', 0):.2f})" for it in v.get("items", [])])
            clip_text = (
                f"--- Hospital Voucher ---\n"
                f"Voucher No: {v['voucher_no']}\n"
                f"Date: {v.get('created_at', '')}\n"
                f"Patient: {v.get('patient_name')} ({v.get('patient_age')} Y, {v.get('patient_gender')})\n"
                f"Phone: {v.get('patient_phone')}\n"
                f"Referred By: {v.get('referred_by')}\n"
                f"Tests:\n{items_str}\n"
                f"Total: Tk {v.get('total_amount', 0):.2f}\n"
                f"Paid: Tk {v.get('paid_amount', 0):.2f}\n"
                f"Due: Tk {v.get('due_amount', 0):.2f}\n"
                f"Status: {v.get('payment_status')}\n"
            )
            win.clipboard_clear()
            win.clipboard_append(clip_text)
            messagebox.showinfo("Copied", f"Voucher {v['voucher_no']} summary copied to clipboard!", parent=win)

        btn_reprint = tk.Button(act_box, text="🖨️ Print", font=("Segoe UI", 9, "bold"), bg="#0d9488", fg="#ffffff", activebackground="#0f766e", relief=tk.FLAT, padx=8, pady=4, command=_print_inspected)
        btn_reprint.pack(side=tk.LEFT, padx=(0, 4))

        btn_pdf = tk.Button(act_box, text="📄 PDF", font=("Segoe UI", 9), bg="#f1f5f9", fg="#0f766e", relief=tk.FLAT, padx=8, pady=4, command=_open_pdf_inspected)
        btn_pdf.pack(side=tk.LEFT, padx=2)

        btn_json = tk.Button(act_box, text="📜 JSON", font=("Segoe UI", 9), bg="#f1f5f9", fg="#2563eb", relief=tk.FLAT, padx=8, pady=4, command=_open_json_inspected)
        btn_json.pack(side=tk.LEFT, padx=2)

        btn_collect = tk.Button(act_box, text="💰 Collect Due", font=("Segoe UI", 9, "bold"), bg="#fee2e2", fg="#dc2626", activebackground="#fca5a5", relief=tk.FLAT, padx=8, pady=4, command=_collect_due_inspected)
        btn_collect.pack(side=tk.LEFT, padx=2)

        btn_copy = tk.Button(act_box, text="📋 Copy", font=("Segoe UI", 9), bg="#f1f5f9", fg="#334155", relief=tk.FLAT, padx=8, pady=4, command=_copy_summary_inspected)
        btn_copy.pack(side=tk.RIGHT)

        # ----------------------------------------------------------------------
        # DATA POPULATION & EVENT HANDLERS
        # ----------------------------------------------------------------------
        def _display_voucher_in_inspector(v: Dict[str, Any]):
            selected_voucher_holder[0] = v
            v_no_lbl.configure(text=v["voucher_no"])
            status = v.get("payment_status", "PAID")
            status_colors = {"PAID": "#059669", "DUE": "#dc2626", "PARTIAL": "#d97706"}
            v_status_badge.configure(text=f" {status} ", bg=status_colors.get(status, "#64748b"))

            raw_time = str(v.get("created_at", ""))
            v_time_lbl.configure(text=f"Time: {raw_time}")
            p_cnt = v.get("printed_count", 0)
            v_printed_lbl.configure(text=f"Printed: {p_cnt}x" if p_cnt else "")

            p_name_lbl.configure(text=f"Patient: {v.get('patient_name', '')}")
            p_demog_lbl.configure(text=f"Age/Sex: {v.get('patient_age', '')} Y / {v.get('patient_gender', '')}  |  Phone: {v.get('patient_phone', 'N/A')}")
            p_doctor_lbl.configure(text=f"Referred By: {v.get('referred_by', 'Self / General')}")

            # Populate tests tree
            tests_tree.delete(*tests_tree.get_children())
            items = v.get("items", [])
            for it in items:
                tests_tree.insert("", tk.END, values=(
                    it.get("test_code", ""),
                    it.get("test_name", ""),
                    str(it.get("quantity", 1)),
                    f"{float(it.get('unit_price', 0)):.2f}",
                    f"{float(it.get('item_total', 0)):.2f}"
                ))

            # Populate financial info
            subtotal = float(v.get("subtotal", 0.0))
            disc_amt = float(v.get("discount_amount", 0.0))
            disc_type = v.get("discount_type", "fixed")
            disc_val = float(v.get("discount_val", 0.0))
            disc_note = f"({disc_val:.0f}%)" if disc_type == "percent" else "(Fixed)"
            net = float(v.get("total_amount", 0.0))
            paid = float(v.get("paid_amount", 0.0))
            due = float(v.get("due_amount", 0.0))
            method = v.get("payment_method", "CASH")

            f_subtotal_lbl.configure(text=f"Subtotal: {curr} {subtotal:.2f}")
            f_discount_lbl.configure(text=f"Discount: {curr} {disc_amt:.2f} {disc_note if disc_amt > 0 else ''}")
            f_net_lbl.configure(text=f"Net Total: {curr} {net:.2f}")
            f_paid_lbl.configure(text=f"Paid: {curr} {paid:.2f} ({method})")

            if due > 0:
                f_due_lbl.configure(text=f"Balance Due: {curr} {due:.2f}", fg="#dc2626")
                btn_collect.configure(state=tk.NORMAL)
            else:
                f_due_lbl.configure(text=f"Balance Due: {curr} 0.00 (Cleared)", fg="#059669")
                btn_collect.configure(state=tk.DISABLED)

        def _on_hist_tree_select(event):
            selected = hist_tree.selection()
            if not selected:
                return
            item_vals = hist_tree.item(selected[0])["values"]
            v_no = item_vals[0]
            full_v = database.get_voucher_by_no(v_no)
            if full_v:
                _display_voucher_in_inspector(full_v)

        def _on_hist_tree_double_click(event):
            _print_inspected()

        hist_tree.bind("<<TreeviewSelect>>", _on_hist_tree_select)
        hist_tree.bind("<Double-Button-1>", _on_hist_tree_double_click)

        def _load_history(maintain_selection_vno=None):
            q = search_var.get().strip()
            df = date_from_var.get().strip()
            dt = date_to_var.get().strip()
            st = status_combo.get().strip()

            vouchers = database.search_vouchers_advanced(
                query=q,
                date_from=df,
                date_to=dt,
                status=st,
                limit=350
            )

            hist_tree.delete(*hist_tree.get_children())

            tot_billed = 0.0
            tot_paid = 0.0
            tot_due = 0.0

            select_item_id = None

            for v in vouchers:
                tot_billed += float(v.get("total_amount", 0.0))
                tot_paid += float(v.get("paid_amount", 0.0))
                tot_due += float(v.get("due_amount", 0.0))

                raw_created = str(v.get("created_at", ""))
                v_date = raw_created[:10] if len(raw_created) >= 10 else ""
                v_time = raw_created[11:16] if len(raw_created) >= 16 else ""

                status = v.get("payment_status", "PAID")
                tag = "paid_tag" if status == "PAID" else ("due_tag" if status == "DUE" else "partial_tag")

                iid = hist_tree.insert("", tk.END, values=(
                    v["voucher_no"],
                    v_date,
                    v_time,
                    v.get("patient_name", ""),
                    v.get("patient_phone", ""),
                    v.get("referred_by", ""),
                    f"{v.get('total_amount', 0.0):.2f}",
                    f"{v.get('paid_amount', 0.0):.2f}",
                    f"{v.get('due_amount', 0.0):.2f}",
                    status
                ), tags=(tag,))

                target_vno = maintain_selection_vno or default_selected_vno
                if target_vno and v["voucher_no"] == target_vno:
                    select_item_id = iid

            # Update Metrics
            stat_cards["count"].configure(text=f"{len(vouchers)}")
            stat_cards["billed"].configure(text=f"{curr} {tot_billed:.2f}")
            stat_cards["collected"].configure(text=f"{curr} {tot_paid:.2f}")
            stat_cards["due"].configure(text=f"{curr} {tot_due:.2f}", fg="#f87171" if tot_due > 0 else "#4ade80")

            # Selection
            children = hist_tree.get_children()
            if select_item_id and select_item_id in children:
                hist_tree.selection_set(select_item_id)
                hist_tree.focus(select_item_id)
                hist_tree.see(select_item_id)
                _on_hist_tree_select(None)
            elif children:
                hist_tree.selection_set(children[0])
                hist_tree.focus(children[0])
                _on_hist_tree_select(None)
            else:
                selected_voucher_holder[0] = None
                v_no_lbl.configure(text="-- NO MATCHING VOUCHERS --")
                tests_tree.delete(*tests_tree.get_children())

        # Live search trace
        search_var.trace_add("write", lambda *args: _load_history())
        status_combo.bind("<<ComboboxSelected>>", lambda e: _load_history())

        # Initial load
        _load_history()

        # Keyboard shortcuts within history window
        win.bind("<Escape>", lambda e: win.destroy())
        win.bind("<F5>", lambda e: _load_history())
        search_entry.focus_set()

    # ==========================================================================
    # DUE PAYMENT COLLECTION MODAL
    # ==========================================================================

    def _open_due_collection_dialog(self, voucher: Dict[str, Any], on_success=None):
        """Open a modal popup to collect due payment on an existing voucher."""
        due_val = float(voucher.get("due_amount", 0.0))
        if due_val <= 0.0:
            messagebox.showinfo("No Due", f"Voucher {voucher['voucher_no']} is already fully PAID.", parent=self.root)
            return

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Collect Due - {voucher['voucher_no']}")
        dlg.geometry("420x350")
        dlg.resizable(False, False)
        dlg.configure(bg="#ffffff")
        dlg.transient(self.root)
        dlg.grab_set()

        # Center on root
        try:
            rx = self.root.winfo_rootx()
            ry = self.root.winfo_rooty()
            rw = self.root.winfo_width()
            rh = self.root.winfo_height()
            dlg.geometry(f"420x350+{max(10, rx + (rw - 420) // 2)}+{max(10, ry + (rh - 350) // 2)}")
        except Exception:
            pass

        # Header
        hdr = tk.Frame(dlg, bg="#0d9488", padx=16, pady=12)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="Collect Due Payment", font=("Segoe UI", 12, "bold"), fg="#ffffff", bg="#0d9488").pack(anchor="w")
        tk.Label(
            hdr,
            text=f"Voucher: {voucher['voucher_no']} | Patient: {voucher.get('patient_name', '')}",
            font=("Segoe UI", 9),
            fg="#ccfbf1",
            bg="#0d9488"
        ).pack(anchor="w")

        body = tk.Frame(dlg, bg="#ffffff", padx=18, pady=14)
        body.pack(fill=tk.BOTH, expand=True)

        curr = database.get_setting("currency_symbol", "Tk")

        # Current Due display
        r1 = tk.Frame(body, bg="#ffffff")
        r1.pack(fill=tk.X, pady=(0, 10))
        tk.Label(r1, text="Current Due:", font=("Segoe UI", 10, "bold"), bg="#ffffff").pack(side=tk.LEFT)
        tk.Label(r1, text=f"{curr} {due_val:.2f}", font=("Segoe UI", 12, "bold"), fg="#dc2626", bg="#ffffff").pack(side=tk.RIGHT)

        # Amount to collect
        r2 = tk.Frame(body, bg="#ffffff")
        r2.pack(fill=tk.X, pady=6)
        tk.Label(r2, text="Amount Received *:", font=("Segoe UI", 10, "bold"), bg="#ffffff").pack(side=tk.LEFT)
        amt_entry = tk.Entry(r2, font=("Segoe UI", 11, "bold"), width=12, bd=1, relief=tk.SOLID, justify=tk.RIGHT)
        amt_entry.insert(0, f"{due_val:.2f}")
        amt_entry.pack(side=tk.RIGHT, ipady=3)
        amt_entry.focus_set()
        amt_entry.select_range(0, tk.END)

        # Payment method
        r3 = tk.Frame(body, bg="#ffffff")
        r3.pack(fill=tk.X, pady=6)
        tk.Label(r3, text="Payment Method:", font=("Segoe UI", 10), bg="#ffffff").pack(side=tk.LEFT)
        method_combo = ttk.Combobox(r3, values=["CASH", "CARD", "bKash / MFS"], width=14, state="readonly")
        method_combo.set("CASH")
        method_combo.pack(side=tk.RIGHT)

        # Note / Remarks
        r4 = tk.Frame(body, bg="#ffffff")
        r4.pack(fill=tk.X, pady=6)
        tk.Label(r4, text="Remarks / Note:", font=("Segoe UI", 10), bg="#ffffff").pack(side=tk.LEFT)
        rem_entry = tk.Entry(r4, font=("Segoe UI", 10), width=16, bd=1, relief=tk.SOLID)
        rem_entry.pack(side=tk.RIGHT, ipady=2)

        status_lbl = tk.Label(body, text="", font=("Segoe UI", 9), fg="#dc2626", bg="#ffffff")
        status_lbl.pack(pady=4)

        def _do_collect():
            amt_str = amt_entry.get().strip()
            try:
                amt = float(amt_str)
                if amt <= 0:
                    status_lbl.configure(text="Amount must be greater than zero.")
                    return
                if amt > due_val:
                    status_lbl.configure(text=f"Cannot collect more than current due ({curr} {due_val:.2f}).")
                    return
            except ValueError:
                status_lbl.configure(text="Please enter a valid numeric amount.")
                return

            try:
                updated_v = database.collect_voucher_due_payment(
                    voucher_id=voucher["id"],
                    amount_paid=amt,
                    payment_method=method_combo.get(),
                    remarks=rem_entry.get().strip()
                )
                if updated_v:
                    # Update local PDF & JSON
                    try:
                        pdf_generator.generate_voucher_pdf(updated_v)
                        data_vault.save_voucher_to_json(updated_v)
                    except Exception:
                        pass

                    dlg.destroy()
                    self.refresh_recent_vouchers()
                    messagebox.showinfo(
                        "Payment Recorded",
                        f"Successfully collected {curr} {amt:.2f} for voucher {voucher['voucher_no']}!\n"
                        f"New Due: {curr} {updated_v['due_amount']:.2f} ({updated_v['payment_status']})",
                        parent=self.root
                    )
                    if on_success:
                        on_success(updated_v)
            except Exception as e:
                status_lbl.configure(text=f"Error saving: {e}")

        # Action buttons
        btn_box = tk.Frame(body, bg="#ffffff")
        btn_box.pack(fill=tk.X, pady=(12, 0))

        tk.Button(
            btn_box,
            text="✔ Confirm Payment",
            font=("Segoe UI", 10, "bold"),
            bg="#0d9488",
            fg="#ffffff",
            activebackground="#0f766e",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=12,
            pady=6,
            command=_do_collect
        ).pack(side=tk.LEFT)

        tk.Button(
            btn_box,
            text="Cancel",
            font=("Segoe UI", 10),
            bg="#f1f5f9",
            fg="#475569",
            relief=tk.FLAT,
            padx=12,
            pady=6,
            command=dlg.destroy
        ).pack(side=tk.RIGHT)

        amt_entry.bind("<Return>", lambda e: _do_collect())

    def _trigger_backup(self):
        self.footer_status.configure(text="⏳ Executing 3-layer backup...")
        res = backup_manager.perform_full_backup(async_mode=True)
        messagebox.showinfo("Backup Triggered", "3-Layer Backup (Local ZIP, USB, Telegram) running in background.")

    def _open_admin(self):
        if self.on_open_admin:
            self.on_open_admin()


if __name__ == "__main__":
    database.init_db()
    app = tk.Tk()
    dash = BillingDashboard(app, on_open_admin=lambda: print("Admin clicked"))
    app.mainloop()
