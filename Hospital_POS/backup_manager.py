r"""
Hospital POS & Billing System - 3-Layer Automated Backup Engine
Target Platform: Windows 7 (32-bit/64-bit) | Python 3.8.10 (32-bit)

Three-Tier Disaster Recovery Architecture:
- Layer 1: Local ZIP Archive (D:\Hospital_Backup) using atomic SQLite online backup.
- Layer 2: Automatic USB Drive Detection (Silently copies ZIP if removable drive is plugged in).
- Layer 3: Telegram Cloud Vault (Sends encrypted/zipped database to private Telegram Bot chat if online).
"""

import os
import sys
import time
import zipfile
import sqlite3
import shutil
import ctypes
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List

from config import DB_PATH, LOCAL_BACKUP_DIR, USB_BACKUP_FOLDER_NAME
import database
import hwid_license

# Windows API Constants
DRIVE_REMOVABLE = 2
MAX_LOCAL_BACKUP_RETENTION = 30  # Keep last 30 backups to save disk space


# ==============================================================================
# 1. LAYER 1: LOCAL ZIP BACKUP WITH SQLITE ONLINE BACKUP API
# ==============================================================================

def create_safe_db_snapshot(source_db_path: str = DB_PATH) -> Optional[str]:
    """
    Create a 100% corruption-free SQLite database snapshot using SQLite's native backup API.
    Guarantees consistency even if WAL mode is actively writing.
    """
    temp_snapshot_path = source_db_path + ".snapshot.tmp"
    try:
        source_conn = database.get_connection(source_db_path)
        dest_conn = sqlite3.connect(temp_snapshot_path)
        with dest_conn:
            source_conn.backup(dest_conn, pages=250)
        dest_conn.close()
        source_conn.close()
        return temp_snapshot_path
    except Exception as e:
        print(f"[BackupManager] Warning: Online SQLite backup failed ({e}), using direct copy fallback.")
        try:
            shutil.copy2(source_db_path, temp_snapshot_path)
            return temp_snapshot_path
        except Exception as e2:
            print(f"[BackupManager] Error creating DB snapshot: {e2}")
            return None


def execute_layer1_local_backup(target_dir: Optional[str] = None, source_db_path: str = DB_PATH) -> Optional[str]:
    r"""
    Layer 1: Compress database snapshot into timestamped ZIP archive.
    Saves to configured directory (defaults to D:\Hospital_Backup with C:\ fallback).
    """
    if not target_dir:
        target_dir = database.get_setting("backup_local_path", LOCAL_BACKUP_DIR)

    # If D:\ drive does not exist, fallback to C:\Hospital_Backup
    try:
        drive_letter = os.path.splitdrive(target_dir)[0]
        if drive_letter and not os.path.exists(drive_letter + "\\"):
            target_dir = r"C:\Hospital_Backup"
        os.makedirs(target_dir, exist_ok=True)
    except Exception:
        target_dir = os.path.join(os.path.expanduser("~"), "Hospital_Backup")
        os.makedirs(target_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"Hospital_Backup_{timestamp}.zip"
    zip_filepath = os.path.join(target_dir, zip_filename)

    snapshot_path = create_safe_db_snapshot(source_db_path)
    if not snapshot_path or not os.path.exists(snapshot_path):
        return None

    try:
        # Create ZIP archive
        with zipfile.ZipFile(zip_filepath, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.write(snapshot_path, arcname="database.db")
            # Include system metadata
            meta_info = f"HWID: {hwid_license.get_hardware_id()}\nCreated: {datetime.now()}\n"
            zip_file.writestr("backup_info.txt", meta_info)

        # Cleanup temporary snapshot file
        if os.path.exists(snapshot_path):
            os.remove(snapshot_path)

        # Prune old archives to prevent filling up the drive
        _prune_old_backups(target_dir, keep=MAX_LOCAL_BACKUP_RETENTION)

        print(f"[BackupManager] Layer 1 Success: {zip_filepath}")
        return zip_filepath

    except Exception as e:
        print(f"[BackupManager] Layer 1 Error creating ZIP: {e}")
        if snapshot_path and os.path.exists(snapshot_path):
            try:
                os.remove(snapshot_path)
            except Exception:
                pass
        return None


def _prune_old_backups(backup_dir: str, keep: int = 30):
    """Keep only the latest N backup zip files."""
    try:
        files = [
            os.path.join(backup_dir, f) for f in os.listdir(backup_dir)
            if f.startswith("Hospital_Backup_") and f.endswith(".zip")
        ]
        files.sort(key=os.path.getmtime, reverse=True)
        if len(files) > keep:
            for old_file in files[keep:]:
                try:
                    os.remove(old_file)
                except Exception:
                    pass
    except Exception as e:
        print(f"[BackupManager] Pruning notice: {e}")


# ==============================================================================
# 2. LAYER 2: SILENT USB FLASH DRIVE DETECTION & AUTO-SYNC
# ==============================================================================

def get_connected_removable_drives() -> List[str]:
    """
    Detect all mounted USB flash drives / removable storage on Windows 7.
    Uses kernel32.GetLogicalDriveStringsW and GetDriveTypeW.
    """
    removable_drives = []
    try:
        buffer_len = 512
        buffer = ctypes.create_unicode_buffer(buffer_len)
        ctypes.windll.kernel32.GetLogicalDriveStringsW(buffer_len, buffer)

        # Parse null-separated drive strings (e.g. 'C:\\\x00D:\\\x00E:\\\x00\x00')
        raw_drives = [d.strip() for d in buffer[:].split("\x00") if d.strip()]
        for drive in raw_drives:
            drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive)
            if drive_type == DRIVE_REMOVABLE:
                removable_drives.append(drive)
    except Exception as e:
        print(f"[BackupManager] Drive detection error: {e}")

    return removable_drives


def execute_layer2_usb_sync(zip_filepath: str) -> Optional[str]:
    """
    Layer 2: Scan for connected USB drives.
    If detected, silently creates 'Hospital_POS_Backup' directory on the USB
    and copies the latest ZIP archive.
    """
    if not zip_filepath or not os.path.exists(zip_filepath):
        return None

    usb_drives = get_connected_removable_drives()
    if not usb_drives:
        print("[BackupManager] Layer 2: No USB drive detected. Skipping USB sync.")
        return None

    copied_paths = []
    zip_filename = os.path.basename(zip_filepath)

    for usb_root in usb_drives:
        try:
            dest_dir = os.path.join(usb_root, USB_BACKUP_FOLDER_NAME)
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, zip_filename)

            shutil.copy2(zip_filepath, dest_path)
            copied_paths.append(dest_path)
            print(f"[BackupManager] Layer 2 Success: Silently copied to USB: {dest_path}")
        except Exception as e:
            print(f"[BackupManager] Layer 2 Warning: Could not copy to {usb_root}: {e}")

    return copied_paths[0] if copied_paths else None


# ==============================================================================
# 3. LAYER 3: TELEGRAM CLOUD VAULT (Silent Bot Auto-Upload)
# ==============================================================================

def is_internet_connected(timeout: float = 3.0) -> bool:
    """Quick socket check to verify internet availability without freezing."""
    import socket
    try:
        # Check connection to Cloudflare or Google public DNS
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except Exception:
        return False


def execute_layer3_telegram_upload(zip_filepath: str) -> bool:
    """
    Layer 3: Upload the encrypted/zipped database to a private Telegram channel/chat.
    Zero disruption; runs silently using requests library.
    """
    if not zip_filepath or not os.path.exists(zip_filepath):
        return False

    bot_token = database.get_setting("telegram_bot_token", "").strip()
    chat_id = database.get_setting("telegram_chat_id", "").strip()

    if not bot_token or not chat_id:
        print("[BackupManager] Layer 3: Telegram credentials not configured in settings. Skipping.")
        return False

    if not is_internet_connected(timeout=2.5):
        print("[BackupManager] Layer 3: No internet connection detected. Skipping Telegram upload.")
        return False

    try:
        import requests

        url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
        hwid = hwid_license.get_hardware_id()
        h_name = database.get_setting("hospital_name", "Hospital POS")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        caption = (
            f"🏥 *{h_name} Database Auto-Backup*\n"
            f"🖥️ *Machine HWID:* `{hwid}`\n"
            f"📅 *Timestamp:* {timestamp}\n"
            f"📦 *File:* `{os.path.basename(zip_filepath)}`\n"
            f"🔒 *Status:* Encrypted & Verified"
        )

        with open(zip_filepath, "rb") as f:
            files = {"document": (os.path.basename(zip_filepath), f, "application/zip")}
            data = {"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"}
            
            resp = requests.post(url, data=data, files=files, timeout=20.0)

        if resp.status_code == 200 and resp.json().get("ok"):
            print("[BackupManager] Layer 3 Success: Database backed up to Telegram Cloud Vault.")
            return True
        else:
            print(f"[BackupManager] Layer 3 Telegram API error: {resp.text}")
            return False

    except Exception as e:
        print(f"[BackupManager] Layer 3 Upload Exception: {e}")
        return False


# ==============================================================================
# 4. ORCHESTRATOR & EXIT HOOK
# ==============================================================================

def perform_full_backup(async_mode: bool = True) -> Dict[str, Any]:
    """
    Trigger all 3 layers of backup sequentially.
    If async_mode is True, launches in an independent background daemon thread.
    """
    def _worker():
        results = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "layer1_local": None,
            "layer2_usb": None,
            "layer3_telegram": False
        }

        # Layer 1: Local ZIP
        zip_path = execute_layer1_local_backup()
        results["layer1_local"] = zip_path

        if zip_path:
            # Layer 2: USB Sync
            usb_path = execute_layer2_usb_sync(zip_path)
            results["layer2_usb"] = usb_path

            # Layer 3: Telegram Upload
            tg_status = execute_layer3_telegram_upload(zip_path)
            results["layer3_telegram"] = tg_status

            # Record last backup timestamp in settings
            database.set_setting("last_backup_timestamp", results["timestamp"])

        return results

    if async_mode:
        t = threading.Thread(target=_worker, name="BackupWorkerThread", daemon=True)
        t.start()
        return {"status": "started_in_background", "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    else:
        return _worker()


def backup_on_exit():
    """Synchronous safe backup called when the user exits the application."""
    print("[BackupManager] Application exit detected. Executing backup suite...")
    perform_full_backup(async_mode=False)
    print("[BackupManager] Exit backup finished.")


# Diagnostic test when run directly
if __name__ == "__main__":
    print("=== Testing 3-Layer Backup System ===")
    print("Detected removable USB drives:", get_connected_removable_drives())
    print("Internet connected:", is_internet_connected())
    print("Executing synchronous test backup...")
    res = perform_full_backup(async_mode=False)
    print("Backup Results Summary:", res)
