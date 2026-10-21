"""
Hospital POS & Diagnostic Billing System - Application Entry Point
Target Platform: Windows 7 (32-bit/64-bit) | Python 3.8.10 (32-bit)

Lifecycle:
1. High-DPI Awareness initialization for crisp display rendering.
2. SQLite Database initialization & baseline tests seeding.
3. Hardware-Locked License Verification:
   - If unlicensed or hardware mismatch: Opens Activation UI.
   - If licensed: Launches Zero-Mouse Receptionist Billing Dashboard.
4. Exit Hook: Performs automated 3-layer backup (Local ZIP + USB + Telegram) upon application exit.
"""

import os
import sys
import ctypes
import tkinter as tk
from tkinter import messagebox

# Add application root directory to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Add ui/ subdirectory to sys.path
UI_DIR = os.path.join(BASE_DIR, "ui")
if UI_DIR not in sys.path:
    sys.path.insert(0, UI_DIR)

import config
import database
import hwid_license
import backup_manager
import printer_engine
from ui.billing_dashboard import BillingDashboard
from ui.login_license import LicenseActivationWindow
from ui.admin_panel import AdminPanelWindow


def enable_high_dpi_awareness():
    """Enable High DPI scaling for Windows 7 / 8 / 10 / 11."""
    if sys.platform == "win32":
        try:
            # Windows 10/11 per-monitor DPI awareness
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                # Windows 7 / 8 system DPI awareness fallback
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


class HospitalPOSApp:
    def __init__(self):
        enable_high_dpi_awareness()

        # Initialize storage directories & SQLite database schema
        config.ensure_directories()
        database.init_db()

        # Primary Tkinter Root
        self.root = tk.Tk()
        self.root.title(config.APP_NAME)
        self.dashboard_instance = None

        # Bind window close protocol for safe automated backup
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)

        # Evaluate License Status
        self._route_window()

    def _route_window(self):
        """Check hardware lock and route to either Activation or Billing Dashboard."""
        is_valid, msg, lic_info = hwid_license.verify_license()

        if is_valid:
            print(f"[Main] Hardware License Validated: {msg}")
            self._launch_billing_dashboard()
        else:
            print(f"[Main] License invalid: {msg}. Opening Activation UI.")
            self._launch_activation_window()

    def _bring_to_foreground(self):
        """Ensure window is deiconified, brought to the front, and given keyboard focus."""
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(200, lambda: self.root.attributes("-topmost", False))
            self.root.focus_force()
        except Exception:
            pass

    def _launch_activation_window(self):
        """Display license activation dialog."""
        # Clear any existing child widgets
        for widget in self.root.winfo_children():
            widget.destroy()

        self.activation_ui = LicenseActivationWindow(
            self.root,
            on_success_callback=self._launch_billing_dashboard
        )
        self._bring_to_foreground()

    def _launch_billing_dashboard(self):
        """Display the main keyboard-driven reception billing dashboard."""
        for widget in self.root.winfo_children():
            widget.destroy()

        self.dashboard_instance = BillingDashboard(
            self.root,
            on_open_admin=self.open_admin_panel
        )
        self._bring_to_foreground()

    def open_admin_panel(self):
        """Open Administrative Management Window."""
        AdminPanelWindow(
            self.root,
            on_settings_updated=self._on_settings_updated
        )

    def _on_settings_updated(self):
        """Callback when administrator updates hospital name or printer."""
        if self.dashboard_instance:
            self.dashboard_instance.h_name_lbl.configure(
                text=database.get_setting("hospital_name", "City Care Diagnostic & Hospital")
            )
            self.dashboard_instance.printer_status_lbl.configure(
                text=f"🖨️ Printer: {printer_engine.get_target_printer()}"
            )

    def on_exit(self):
        """Handle application exit: triggers 3-layer backup before quitting."""
        try:
            # Run exit backup routine
            backup_manager.backup_on_exit()
        except Exception as e:
            print(f"[Main] Notice: Exit backup error: {e}")
        finally:
            self.root.destroy()

    def run(self):
        """Start the Tkinter event loop."""
        self.root.mainloop()


if __name__ == "__main__":
    app = HospitalPOSApp()
    app.run()
