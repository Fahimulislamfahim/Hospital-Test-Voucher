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
  * F4: Focus Discount Field
  * F5: Focus Paid Amount Field
  * F8: Open Admin Panel
  * F12 or Ctrl+P: Save Voucher & Silent Direct Print
  * Delete or Ctrl+D: Remove selected test from cart
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import List, Dict, Any, Optional

import database
import printer_engine
import backup_manager
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

        self._setup_styles()
        self._build_ui()
        self._bind_global_shortcuts()

        # Load initial data
        self.refresh_recent_vouchers()
        self.reset_form()

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

        right_col = tk.Frame(body_frame, bg=self.c_bg, width=380)
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

        # Live Clock & Status
        right_info = tk.Frame(header_frame, bg="#0f172a")
        right_info.pack(side=tk.RIGHT, pady=8)

        self.printer_status_lbl = tk.Label(
            right_info,
            text=f"🖨️ Printer: {printer_engine.get_target_printer()}",
            font=("Segoe UI", 9),
            fg="#94a3b8",
            bg="#0f172a"
        )
        self.printer_status_lbl.pack(side=tk.LEFT, padx=12)

        admin_btn = tk.Button(
            right_info,
            text="⚙️ Admin Panel (F8)",
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
        tk.Label(r5, text="Method:", font=("Segoe UI", 9), bg=self.c_card).pack(side=tk.LEFT)
        self.method_combo = ttk.Combobox(r5, values=["CASH", "CARD", "bKash / MFS", "DUE"], width=10, state="readonly")
        self.method_combo.set("CASH")
        self.method_combo.pack(side=tk.LEFT, padx=(4, 0))

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
            text=" Recent Vouchers Today ",
            font=("Segoe UI", 9, "bold"),
            bg=self.c_card,
            fg="#334155",
            padx=8,
            pady=6,
            relief=tk.SOLID,
            bd=1
        )
        card.pack(fill=tk.BOTH, expand=True)

        cols = ("vno", "patient", "total", "status")
        self.recent_tree = ttk.Treeview(card, columns=cols, show="headings", height=5, selectmode="browse")

        self.recent_tree.heading("vno", text="Voucher No")
        self.recent_tree.heading("patient", text="Patient")
        self.recent_tree.heading("total", text="Total")
        self.recent_tree.heading("status", text="Status")

        self.recent_tree.column("vno", width=110, anchor=tk.W)
        self.recent_tree.column("patient", width=110, anchor=tk.W)
        self.recent_tree.column("total", width=60, anchor=tk.E)
        self.recent_tree.column("status", width=60, anchor=tk.CENTER)

        self.recent_tree.pack(fill=tk.BOTH, expand=True)
        self.recent_tree.bind("<Double-Button-1>", lambda e: self._on_double_click_recent())

    def _build_shortcut_bar(self):
        bar = tk.Frame(self.root, bg="#1e293b", height=32, padx=12)
        bar.pack(fill=tk.X, side=tk.BOTTOM)

        shortcuts = [
            ("F1", "New Patient"),
            ("F2", "Search Test"),
            ("F4", "Discount"),
            ("F5", "Paid"),
            ("F8", "Admin"),
            ("F9", "Backup Now"),
            ("F12", "SAVE & PRINT"),
            ("Del", "Remove Test"),
        ]

        for key, desc in shortcuts:
            pill = tk.Frame(bar, bg="#334155", padx=6, pady=2)
            pill.pack(side=tk.LEFT, padx=3, pady=4)
            tk.Label(pill, text=key, font=("Segoe UI", 8, "bold"), bg="#334155", fg="#38bdf8").pack(side=tk.LEFT)
            tk.Label(pill, text=f": {desc}", font=("Segoe UI", 8), bg="#334155", fg="#cbd5e1").pack(side=tk.LEFT)

        # Status note
        self.footer_status = tk.Label(bar, text="Ready", font=("Segoe UI", 8, "italic"), bg="#1e293b", fg="#94a3b8")
        self.footer_status.pack(side=tk.RIGHT, padx=6)

    # ==========================================================================
    # KEYBOARD NAVIGATION & ZERO-MOUSE SHORTCUTS
    # ==========================================================================

    def _bind_global_shortcuts(self):
        self.root.bind("<F1>", lambda e: self.reset_form())
        self.root.bind("<F2>", lambda e: self.search_entry.focus_set())
        self.root.bind("<F4>", lambda e: self.discount_entry.focus_set())
        self.root.bind("<F5>", lambda e: self.paid_entry.focus_set())
        self.root.bind("<F8>", lambda e: self._open_admin())
        self.root.bind("<F9>", lambda e: self._trigger_backup())
        self.root.bind("<F11>", lambda e: self._reprint_last_voucher())
        self.root.bind("<F12>", lambda e: self.save_and_print_voucher())
        self.root.bind("<Control-p>", lambda e: self.save_and_print_voucher())
        self.root.bind("<Control-P>", lambda e: self.save_and_print_voucher())
        self.root.bind("<Delete>", lambda e: self._remove_selected_cart_item())
        self.root.bind("<Control-d>", lambda e: self._remove_selected_cart_item())

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
        # Check if already in cart -> increment quantity
        for item in self.cart_items:
            if item["test_id"] == test["id"]:
                item["quantity"] += 1
                item["item_total"] = round(item["price"] * item["quantity"], 2)
                self._refresh_cart_view()
                self._recalculate()
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

            # 2. Trigger Silent Print (No Dialogs!)
            print_res = printer_engine.print_voucher_silently(voucher)
            
            # Show toast / footer update
            v_no = voucher["voucher_no"]
            self.footer_status.configure(text=f"✅ Saved & Printed: {v_no} ({print_res['message']})")

            # 3. Refresh Recent List & Reset for Next Patient
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
        self.recent_tree.delete(*self.recent_tree.get_children())
        vouchers = database.get_recent_vouchers(limit=25)
        for v in vouchers:
            self.recent_tree.insert("", tk.END, values=(
                v["voucher_no"],
                v["patient_name"],
                f"{v['total_amount']:.0f}",
                v["payment_status"]
            ))

    def _on_double_click_recent(self):
        selected = self.recent_tree.selection()
        if not selected:
            return
        item_vals = self.recent_tree.item(selected[0])["values"]
        v_no = item_vals[0]
        v = database.get_voucher_by_no(v_no)
        if v:
            res = printer_engine.print_voucher_silently(v)
            messagebox.showinfo("Reprint Sent", f"Reprinting voucher {v_no}:\n{res['message']}")

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
