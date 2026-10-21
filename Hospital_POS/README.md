# Hospital Voucher & Diagnostic Billing System (Windows 7 32-bit & 64-bit)

A high-performance, keyboard-driven offline Hospital POS and Diagnostic Billing System designed specifically for legacy PCs running **Windows 7 (32-bit and 64-bit)** using **Python 3.8.10 (32-bit)**.

---

## 📁 Architecture & File Layout

```
/Hospital_POS
  ├── main.py                  # Entry point, DPI awareness, license router, exit backup hook
  ├── config.py                # System paths, crypto salts, constants, AppData resolver
  ├── database.py              # SQLite WAL mode, atomic voucher transactions, baseline seed
  ├── hwid_license.py          # Multi-factor HWID lock, encrypted .lic file, online & offline activation
  ├── backup_manager.py        # 3-Layer auto-backup (Local ZIP + USB Auto-Sync + Telegram Cloud Vault)
  ├── printer_engine.py        # 100% silent direct printing (RAW 80mm ESC/POS + GDI Windows DC)
  ├── build_exe.bat            # PyInstaller compilation batch script for Windows 7 32-bit
  ├── requirements.txt         # Pinned packages with verified cp38-win32 binary wheels
  └── /ui
      ├── login_license.py     # Activation UI with HWID copy, online & offline activation
      ├── billing_dashboard.py # Zero-mouse 10-second receptionist billing screen
      └── admin_panel.py       # PIN-protected test CRUD, daily reports, settings & backup
```

---

## ⚡ Zero-Mouse Receptionist Workflow (10-Second Voucher Creation)

| Key | Action |
| :--- | :--- |
| **`F1`** | **New Patient / Clear All** (Autofocuses `Patient Name`) |
| **`Enter`** | **Field Advance** (`Name` ➔ `Age` ➔ `Sex` ➔ `Phone` ➔ `Ref By` ➔ `Test Search`) |
| **`Shortcode` + `Enter`** | **Instant Add to Cart** (e.g. typing `101` or `cbc` + `Enter` adds CBC, resets & refocuses search) |
| **`F2`** | Jump focus directly to **Test Search Bar** |
| **`F4`** | Jump focus to **Discount** field (press `Enter` to jump to Paid Amount) |
| **`F5`** | Jump focus to **Paid Amount** field |
| **`F8`** | Open **Admin Console** (Default PIN: `1234`) |
| **`F9`** | Trigger **Immediate 3-Layer Backup** |
| **`F11`** | **Reprint Last Voucher** |
| **`F12` or `Ctrl+P`** | **SAVE & SILENT PRINT** (Saves to DB, prints silently, resets for next patient) |
| **`Delete` or `Ctrl+D`** | Remove selected test from the cart |

---

## 🔒 Feature Highlights

### 1. Hardware-Locked Anti-Piracy Licensing
- Extracts Motherboard UUID (`wmic csproduct get uuid` with `CREATE_NO_WINDOW`), Windows `MachineGuid` registry key, and system drive volume serial.
- Encrypts license into `%APPDATA%\Hospital_POS\license.lic` using AES/Fernet with HMAC signature verification.
- If copied to another PC or flash drive, the hardware mismatch immediately locks the application and requests activation.
- Supports both **Online Activation** via Vercel/MongoDB REST API and **Offline On-Premise Activation** (Demo Key: `DEMO-WIN7-TEST`).

### 2. Direct Silent Printing Engine
- Spools directly to target printer using `win32print` with **zero print dialog popups**.
- Formats standard 80mm thermal continuous roll receipts with automatic ESC/POS paper-cut commands.
- Includes a fallback GDI Device Context (`win32ui`) for standard A5/A4 laser printers.
- Saves text previews in `receipt_previews/` automatically for audit and verification.

### 3. 3-Layer Automated Disaster Recovery
- **Layer 1 (Local):** Uses SQLite's native online backup API to take a non-blocking snapshot and compresses it to `D:\Hospital_Backup\Hospital_Backup_YYYYMMDD_HHMMSS.zip` on application exit.
- **Layer 2 (USB):** Detects if any removable flash drive is plugged in; if found, mirrors the backup ZIP silently.
- **Layer 3 (Telegram Cloud):** If an active internet connection is detected, uploads the database archive silently to a private Telegram channel using your bot credentials.

---

## 🛠️ Installation & Execution

### Running from Source
```bash
cd Hospital_POS
pip install -r requirements.txt
python main.py
```

### Packaging into Standalone Windows 7 Executable
Run `build_exe.bat` or execute:
```bash
pyinstaller --noconfirm --onedir --windowed --name "Hospital_POS" --add-data "ui;ui" main.py
```
The output executable will be created in `dist\Hospital_POS\Hospital_POS.exe`.
