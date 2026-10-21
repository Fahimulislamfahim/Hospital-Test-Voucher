"""
Hospital POS & Billing System - Activation & License Management UI
Target Platform: Windows 7 (32-bit/64-bit) | Python 3.8.10 (32-bit)
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
from typing import Callable, Optional

import hwid_license
from config import APP_NAME, APP_VERSION


class LicenseActivationWindow:
    def __init__(self, root: tk.Tk, on_success_callback: Optional[Callable] = None):
        self.root = root
        self.on_success_callback = on_success_callback

        self.root.title(f"{APP_NAME} - System Activation")
        self.root.geometry("560x540")
        self.root.resizable(False, False)

        # Center window on screen
        self._center_window(560, 540)

        self.current_hwid = hwid_license.get_hardware_id()
        self.is_processing = False

        self._setup_style()
        self._create_widgets()

    def _center_window(self, width: int, height: int):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = max(0, (sw - width) // 2)
        y = max(0, (sh - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _setup_style(self):
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        # Configure colors (Professional Hospital Teal / Slate Palette)
        self.root.configure(bg="#f4f7f9")
        self.style.configure(".", background="#f4f7f9", font=("Segoe UI", 10))
        self.style.configure("TLabel", background="#f4f7f9", foreground="#2c3e50")
        self.style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"), foreground="#1a365d")
        self.style.configure("SubHeader.TLabel", font=("Segoe UI", 10), foreground="#4a5568")
        self.style.configure("HWID.TLabel", font=("Consolas", 12, "bold"), foreground="#0d9488")
        self.style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), foreground="#ffffff", background="#0d9488")
        self.style.map("Primary.TButton", background=[("active", "#0f766e"), ("pressed", "#115e59")])
        self.style.configure("Secondary.TButton", font=("Segoe UI", 10))

    def _create_widgets(self):
        main_frame = ttk.Frame(self.root, padding=24)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header Icon & Title
        title_lbl = ttk.Label(main_frame, text="🏥 System Activation & Licensing", style="Header.TLabel")
        title_lbl.pack(anchor="w", pady=(0, 2))

        sub_lbl = ttk.Label(
            main_frame,
            text=f"Version {APP_VERSION} | Hardware-Locked Enterprise Installation",
            style="SubHeader.TLabel"
        )
        sub_lbl.pack(anchor="w", pady=(0, 16))

        # HWID Card
        hwid_card = tk.LabelFrame(
            main_frame,
            text=" Machine Hardware Fingerprint (HWID) ",
            font=("Segoe UI", 9, "bold"),
            bg="#ffffff",
            fg="#2c3e50",
            relief=tk.GROOVE,
            bd=1,
            padx=12,
            pady=10
        )
        hwid_card.pack(fill=tk.X, pady=(0, 16))

        hwid_desc = tk.Label(
            hwid_card,
            text="Provide this unique Hardware ID to your vendor to receive an activation key:",
            bg="#ffffff",
            fg="#718096",
            font=("Segoe UI", 9),
            anchor="w"
        )
        hwid_desc.pack(fill=tk.X, pady=(0, 4))

        hwid_box = tk.Frame(hwid_card, bg="#ffffff")
        hwid_box.pack(fill=tk.X)

        self.hwid_entry = tk.Entry(
            hwid_box,
            font=("Consolas", 11, "bold"),
            bg="#f8fafc",
            fg="#0f766e",
            bd=1,
            relief=tk.SOLID
        )
        self.hwid_entry.insert(0, self.current_hwid)
        self.hwid_entry.configure(state="readonly")
        self.hwid_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)

        copy_btn = tk.Button(
            hwid_box,
            text="📋 Copy HWID",
            font=("Segoe UI", 9, "bold"),
            bg="#0d9488",
            fg="#ffffff",
            activebackground="#0f766e",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=10,
            command=self._copy_hwid
        )
        copy_btn.pack(side=tk.LEFT, padx=(6, 0), ipady=2)

        # Form Fields Frame
        form_frame = tk.LabelFrame(
            main_frame,
            text=" Activation Credentials ",
            font=("Segoe UI", 9, "bold"),
            bg="#ffffff",
            fg="#2c3e50",
            relief=tk.GROOVE,
            bd=1,
            padx=12,
            pady=12
        )
        form_frame.pack(fill=tk.X, pady=(0, 16))

        # Hospital Name
        tk.Label(form_frame, text="Hospital / Diagnostic Center Name:", bg="#ffffff", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 2))
        self.client_entry = tk.Entry(form_frame, font=("Segoe UI", 10), bd=1, relief=tk.SOLID)
        self.client_entry.insert(0, "City Care Diagnostic Center")
        self.client_entry.pack(fill=tk.X, pady=(0, 10), ipady=4)

        # License Key
        tk.Label(form_frame, text="License / Activation Key:", bg="#ffffff", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 2))
        self.key_entry = tk.Entry(form_frame, font=("Consolas", 11), bd=1, relief=tk.SOLID)
        self.key_entry.insert(0, "DEMO-WIN7-TEST")  # Demo test key pre-filled for convenience
        self.key_entry.pack(fill=tk.X, pady=(0, 6), ipady=4)

        # Status Label
        self.status_var = tk.StringVar(value="Enter your activation key above and proceed.")
        self.status_lbl = tk.Label(
            main_frame,
            textvariable=self.status_var,
            font=("Segoe UI", 9, "italic"),
            bg="#f4f7f9",
            fg="#4a5568",
            wraplength=500,
            justify=tk.LEFT
        )
        self.status_lbl.pack(anchor="w", pady=(0, 12))

        # Action Buttons Frame
        btn_frame = tk.Frame(main_frame, bg="#f4f7f9")
        btn_frame.pack(fill=tk.X)

        self.online_btn = tk.Button(
            btn_frame,
            text="🌐 Activate Online",
            font=("Segoe UI", 10, "bold"),
            bg="#0d9488",
            fg="#ffffff",
            activebackground="#0f766e",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=14,
            pady=6,
            command=self._handle_online_activation
        )
        self.online_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.offline_btn = tk.Button(
            btn_frame,
            text="🔑 Offline / On-Premise Activation",
            font=("Segoe UI", 10),
            bg="#e2e8f0",
            fg="#1e293b",
            activebackground="#cbd5e1",
            relief=tk.FLAT,
            padx=14,
            pady=6,
            command=self._handle_offline_activation
        )
        self.offline_btn.pack(side=tk.LEFT)

        # Hint for demo mode
        hint_lbl = tk.Label(
            main_frame,
            text="💡 Offline Demo Key: 'DEMO-WIN7-TEST' activates instant trial offline.",
            bg="#f4f7f9",
            fg="#64748b",
            font=("Segoe UI", 8)
        )
        hint_lbl.pack(anchor="w", pady=(14, 0))

    def _copy_hwid(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.current_hwid)
        self.status_var.set("HWID copied to clipboard! Share it with the system administrator.")
        self.status_lbl.configure(fg="#0d9488")

    def _set_ui_state(self, is_busy: bool):
        self.is_processing = is_busy
        state = tk.DISABLED if is_busy else tk.NORMAL
        self.online_btn.configure(state=state)
        self.offline_btn.configure(state=state)

    def _handle_online_activation(self):
        if self.is_processing:
            return

        client_name = self.client_entry.get().strip()
        license_key = self.key_entry.get().strip()

        if not client_name or not license_key:
            messagebox.showwarning("Incomplete Input", "Please provide both Hospital Name and License Key.")
            return

        self._set_ui_state(True)
        self.status_var.set("Contacting activation server... Please wait.")
        self.status_lbl.configure(fg="#2563eb")

        def _thread_target():
            success, msg = hwid_license.activate_license_online(license_key, client_name)
            self.root.after(0, lambda: self._on_activation_complete(success, msg))

        threading.Thread(target=_thread_target, daemon=True).start()

    def _handle_offline_activation(self):
        if self.is_processing:
            return

        client_name = self.client_entry.get().strip()
        license_key = self.key_entry.get().strip()

        if not client_name or not license_key:
            messagebox.showwarning("Incomplete Input", "Please provide both Hospital Name and License Key.")
            return

        success, msg = hwid_license.activate_license_offline(license_key, client_name)
        self._on_activation_complete(success, msg)

    def _on_activation_complete(self, success: bool, message: str):
        self._set_ui_state(False)
        if success:
            self.status_var.set(message)
            self.status_lbl.configure(fg="#059669")
            messagebox.showinfo("Activation Successful", f"{message}\n\nLaunching Billing Dashboard...")
            if self.on_success_callback:
                self.on_success_callback()
        else:
            self.status_var.set(message)
            self.status_lbl.configure(fg="#dc2626")
            messagebox.showerror("Activation Failed", message)


if __name__ == "__main__":
    app_root = tk.Tk()
    win = LicenseActivationWindow(app_root, on_success_callback=lambda: print("Activation passed!"))
    app_root.mainloop()
