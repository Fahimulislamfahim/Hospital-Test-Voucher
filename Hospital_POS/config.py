"""
Hospital POS & Billing System - Configuration Module
Target Platform: Windows 7 (32-bit/64-bit) | Python 3.8.10 (32-bit)
"""

import os
import sys

# Application Identity
APP_NAME = "Hospital Voucher & Diagnostic Billing System"
APP_VERSION = "1.0.0"
APP_SHORT_CODE = "HOSP_POS"

# Determine application directory (Handles PyInstaller frozen bundling)
if getattr(sys, 'frozen', False):
    # Running inside compiled PyInstaller bundle
    APP_DIR = os.path.dirname(sys.executable)
else:
    # Running in standard Python interpreter
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Data storage paths
# database.db is stored locally in the application folder for offline portability
DB_NAME = "database.db"
DB_PATH = os.path.join(APP_DIR, DB_NAME)

# Secure system AppData directory for license storage (prevents simple directory copy-paste piracy)
APPDATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Hospital_POS")
LICENSE_FILE_NAME = "license.lic"
LICENSE_FILE_PATH = os.path.join(APPDATA_DIR, LICENSE_FILE_NAME)

# Storage Root & Sub-Directory Configuration
DEFAULT_STORAGE_ROOT = r"D:\Hospital_POS_Data" if os.path.exists("D:\\") else os.path.join(os.path.expanduser("~"), "Hospital_POS_Data")
LOCAL_BACKUP_DIR = os.path.join(DEFAULT_STORAGE_ROOT, "Backups")
DEFAULT_BACKUP_DIR = LOCAL_BACKUP_DIR
DEFAULT_VOUCHER_PDF_DIR = os.path.join(DEFAULT_STORAGE_ROOT, "Vouchers_PDF")
DEFAULT_REPORTS_PDF_DIR = os.path.join(DEFAULT_STORAGE_ROOT, "Daily_Reports")
USB_BACKUP_FOLDER_NAME = "Hospital_POS_Backup"

# Cloud Backup (Telegram Bot) - Can be overridden in database settings table
DEFAULT_TELEGRAM_BOT_TOKEN = ""
DEFAULT_TELEGRAM_CHAT_ID = ""

# Remote License Verification API endpoint (Vercel / MongoDB Serverless)
LICENSE_API_URL = "https://hospital-pos-license.vercel.app/api/activate"

# Static application cryptographic salt (ensures tamper-proof tokens)
CRYPTO_SALT = b"HOSPITAL_POS_WIN7_STABLE_SALT_x86_v1"
SECRET_PEPPER = "DiagnosticBillingSecureKey2026"

# Ensure runtime directories exist
def ensure_directories():
    """Ensure that necessary directories (AppData, Backup) exist."""
    try:
        if not os.path.exists(APPDATA_DIR):
            os.makedirs(APPDATA_DIR, exist_ok=True)
    except Exception as e:
        print(f"[Config] Warning: Could not create AppData dir: {e}")

# Initialize directories on import
ensure_directories()
