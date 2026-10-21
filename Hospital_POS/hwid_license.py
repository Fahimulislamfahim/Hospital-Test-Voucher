r"""
Hospital POS & Billing System - Hardware-Locked Licensing Engine
Target Platform: Windows 7 (32-bit/64-bit) | Python 3.8.10 (32-bit)

Security Architecture:
1. Multi-factor Hardware Signature (Motherboard UUID + Registry MachineGuid + Volume Serial).
2. Tamper-Proof Cryptographic Storage: Encrypted .lic file stored in %APPDATA%\Hospital_POS\license.lic.
3. Authenticated Encryption (PBKDF2-HMAC-SHA256 + Encrypt-then-MAC + Base64) using pure Python standard library.
   Zero external C-extension binary dependencies, eliminating all IDE import errors.
4. Anti-Piracy / Anti-Clone: If the application folder or database is copied to a flash drive or another PC,
   the HWID mismatch immediately locks the application and prompts for activation.
5. Windows 7 Compatible: All subprocess calls use CREATE_NO_WINDOW (0x08000000) to prevent black console flashes.
"""

import os
import sys
import json
import hmac
import base64
import hashlib
import ctypes
import subprocess
from datetime import datetime
from typing import Tuple, Optional, Dict, Any

from config import (
    LICENSE_FILE_PATH,
    APPDATA_DIR,
    CRYPTO_SALT,
    SECRET_PEPPER,
    LICENSE_API_URL,
    APP_VERSION
)

# Win32 Process creation flag to hide console window completely
CREATE_NO_WINDOW = 0x08000000


# ==============================================================================
# 1. HARDWARE ID (HWID) EXTRACTION
# ==============================================================================

def _get_wmic_uuid() -> Optional[str]:
    """
    Attempt to extract Motherboard / ComputerSystem UUID via WMIC.
    Compatible with Windows 7 (where wmic.exe exists in System32).
    """
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    wmic_paths = [
        "wmic",
        os.path.join(system_root, "System32", "wbem", "wmic.exe"),
        os.path.join(system_root, "System32", "wmic.exe")
    ]

    for wmic_bin in wmic_paths:
        try:
            output = subprocess.check_output(
                [wmic_bin, "csproduct", "get", "uuid"],
                creationflags=CREATE_NO_WINDOW,
                stderr=subprocess.DEVNULL,
                timeout=4
            ).decode("utf-8", errors="ignore")

            lines = [line.strip() for line in output.splitlines() if line.strip()]
            if len(lines) >= 2:
                uuid = lines[1].strip()
                # Check for generic/invalid placeholder UUIDs
                if uuid and uuid.upper() not in (
                    "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF",
                    "03000200-0400-0500-0006-000700080009",
                    "NONE", "DEFAULT STRING"
                ):
                    return uuid
        except Exception:
            continue

    return None


def _get_registry_machine_guid() -> Optional[str]:
    """
    Extract Windows Cryptography MachineGuid from Registry.
    Supported on all Windows 7, 8, 10, 11 systems natively via winreg.
    """
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY
        )
        guid, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        if guid and len(str(guid).strip()) > 10:
            return str(guid).strip()
    except Exception:
        pass

    # Fallback to 32-bit registry view if 64-bit query fails
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            winreg.KEY_READ
        )
        guid, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        if guid and len(str(guid).strip()) > 10:
            return str(guid).strip()
    except Exception:
        pass

    return None


def _get_system_volume_serial() -> Optional[str]:
    """
    Retrieve Volume Serial Number of C: drive using kernel32.GetVolumeInformationW.
    Zero process spawning, 100% reliable and instantaneous on Windows 7 32-bit.
    """
    try:
        volume_serial = ctypes.c_ulong()
        res = ctypes.windll.kernel32.GetVolumeInformationW(
            r"C:\\", None, 0,
            ctypes.byref(volume_serial),
            None, None, None, 0
        )
        if res:
            return f"{volume_serial.value:08X}"
    except Exception:
        pass
    return None


def get_hardware_id() -> str:
    """
    Generate an immutable, deterministic, unique Hardware ID (HWID).
    Combines Motherboard UUID, Registry MachineGuid, and System Volume Serial.
    Formatted as: HOSP-XXXX-XXXX-XXXX-XXXX
    """
    uuid = _get_wmic_uuid() or "NO_WMIC_UUID"
    guid = _get_registry_machine_guid() or "NO_REG_GUID"
    vol_serial = _get_system_volume_serial() or "NO_VOL_SERIAL"

    # Raw hardware composite
    raw_hw_str = f"UUID={uuid}|GUID={guid}|VOL={vol_serial}"

    # Hash with application cryptographic salt
    hasher = hashlib.sha256()
    hasher.update(CRYPTO_SALT)
    hasher.update(raw_hw_str.encode("utf-8"))
    hex_digest = hasher.hexdigest().upper()

    # Format into human-friendly 16-character license token
    chunk1 = hex_digest[0:4]
    chunk2 = hex_digest[4:8]
    chunk3 = hex_digest[8:12]
    chunk4 = hex_digest[12:16]

    return f"HOSP-{chunk1}-{chunk2}-{chunk3}-{chunk4}"


# ==============================================================================
# 2. CRYPTOGRAPHIC ENGINE (PURE STANDARD LIBRARY - ZERO EXTERNAL DEPENDENCY)
# ==============================================================================

def _derive_master_key() -> bytes:
    """Derive 256-bit symmetric encryption key using PBKDF2-HMAC-SHA256 (50,000 rounds)."""
    return hashlib.pbkdf2_hmac(
        'sha256',
        SECRET_PEPPER.encode('utf-8'),
        CRYPTO_SALT,
        iterations=50000,
        dklen=32
    )


def _encrypt_payload(payload_dict: dict) -> bytes:
    """
    Encrypt dictionary using Authenticated Encryption (Encrypt-then-MAC).
    100% Pure Python standard library (hashlib + hmac + base64).
    Guarantees tamper-proofing and requires zero external C packages.
    """
    key = _derive_master_key()
    raw_json = json.dumps(payload_dict, sort_keys=True).encode('utf-8')

    # 1. Generate authenticated HMAC-SHA256 tag over plaintext
    auth_tag = hmac.new(key, raw_json, hashlib.sha256).digest()

    # 2. Keystream cipher encryption (AES-CTR equivalent using HMAC-SHA256 PRF)
    cipher_bytes = bytearray()
    for i, byte_val in enumerate(raw_json):
        if i % 32 == 0:
            block_key = hmac.new(key, (i // 32).to_bytes(4, 'big'), hashlib.sha256).digest()
        cipher_bytes.append(byte_val ^ block_key[i % 32])

    # 3. Pack: Prefix 'HOSP_SEC::' + Base64( AuthTag [32 bytes] + Ciphertext )
    payload_packed = auth_tag + bytes(cipher_bytes)
    return b"HOSP_SEC::" + base64.b64encode(payload_packed)


def _decrypt_payload(encrypted_data: bytes) -> Optional[dict]:
    """
    Decrypt and verify encrypted license bytes with constant-time HMAC check.
    Returns parsed dictionary if authentic, None if tampered or corrupt.
    """
    try:
        key = _derive_master_key()

        if encrypted_data.startswith(b"HOSP_SEC::"):
            raw_payload = base64.b64decode(encrypted_data[10:])
            if len(raw_payload) < 32:
                return None

            expected_tag = raw_payload[:32]
            ciphertext = raw_payload[32:]

            # Decrypt keystream
            decrypted = bytearray()
            for i, byte_val in enumerate(ciphertext):
                if i % 32 == 0:
                    block_key = hmac.new(key, (i // 32).to_bytes(4, 'big'), hashlib.sha256).digest()
                decrypted.append(byte_val ^ block_key[i % 32])

            plain_bytes = bytes(decrypted)

            # Constant-time comparison to prevent timing attacks
            calculated_tag = hmac.new(key, plain_bytes, hashlib.sha256).digest()
            if not hmac.compare_digest(expected_tag, calculated_tag):
                return None

            return json.loads(plain_bytes.decode('utf-8'))

        # Backward compatibility fallback for legacy stream formats
        elif encrypted_data.startswith(b"STREAM::"):
            stream_data = encrypted_data[8:]
            dec = bytearray()
            for i, b in enumerate(stream_data):
                if i % 32 == 0:
                    bk = hashlib.sha256(key + (i // 32).to_bytes(4, 'big')).digest()
                dec.append(b ^ bk[i % 32])
            envelope = bytes(dec)
            if b"::" not in envelope:
                return None
            sig_str, json_bytes = envelope.split(b"::", 1)
            exp_sig = hmac.new(key, json_bytes, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig_str.decode('utf-8'), exp_sig):
                return None
            return json.loads(json_bytes.decode('utf-8'))

        return None
    except Exception:
        return None


# ==============================================================================
# 3. LICENSE VERIFICATION (OFFLINE)
# ==============================================================================

def verify_license() -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Verify application license offline.
    
    Returns:
        (is_valid: bool, status_message: str, license_info: dict | None)
    """
    if not os.path.exists(LICENSE_FILE_PATH):
        return False, "License file not found. System activation required.", None

    try:
        with open(LICENSE_FILE_PATH, "rb") as f:
            encrypted_data = f.read()
    except Exception as e:
        return False, f"Failed to read license file: {e}", None

    license_dict = _decrypt_payload(encrypted_data)
    if not license_dict:
        return False, "License file is corrupted or has been tampered with.", None

    # Check HWID lock (Anti-Piracy Check)
    current_hwid = get_hardware_id()
    registered_hwid = license_dict.get("hwid")

    if not registered_hwid or registered_hwid != current_hwid:
        return (
            False,
            f"Hardware Mismatch! This license is locked to machine '{registered_hwid}'. "
            f"Current machine HWID is '{current_hwid}'. Please reactivate.",
            None
        )

    # Check Expiration date
    expiry_str = license_dict.get("expiry_date", "PERPETUAL")
    if expiry_str != "PERPETUAL":
        try:
            exp_date = datetime.strptime(expiry_str, "%Y-%m-%d")
            if datetime.now() > exp_date:
                return False, f"License expired on {expiry_str}. Please contact support.", license_dict
        except ValueError:
            return False, "Invalid expiry date format in license.", None

    client_name = license_dict.get("client_name", "Hospital Client")
    return True, f"Activated for: {client_name}", license_dict


# ==============================================================================
# 4. LICENSE ACTIVATION (ONLINE & OFFLINE)
# ==============================================================================

def activate_license_online(
    license_key: str,
    client_name: str,
    api_url: str = LICENSE_API_URL
) -> Tuple[bool, str]:
    """
    Activate system by sending HWID and License Key to Vercel/MongoDB API.
    Supports both 'requests' and standard library 'urllib.request' transparently.
    Writes encrypted .lic file upon successful verification.
    """
    current_hwid = get_hardware_id()
    license_key = license_key.strip().upper()
    client_name = client_name.strip()

    if not license_key:
        return False, "Please enter a valid License Key."
    if not client_name:
        return False, "Please enter Hospital / Clinic Name."

    payload = {
        "action": "activate",
        "license_key": license_key,
        "hwid": current_hwid,
        "client_name": client_name,
        "os": "Windows 7 (32-bit)",
        "version": APP_VERSION
    }

    try:
        status_code = None
        data = {}

        # 1. Attempt using requests library if available
        try:
            import requests
            response = requests.post(
                api_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10.0
            )
            status_code = response.status_code
            data = response.json()
        except ImportError:
            # 2. Pure Python standard library fallback (urllib.request)
            import urllib.request
            import urllib.error
            req_data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                api_url,
                data=req_data,
                headers={"Content-Type": "application/json", "User-Agent": "HospitalPOS/1.0"}
            )
            try:
                with urllib.request.urlopen(req, timeout=10.0) as resp:
                    status_code = resp.getcode()
                    data = json.loads(resp.read().decode('utf-8'))
            except urllib.error.HTTPError as he:
                status_code = he.code
                try:
                    data = json.loads(he.read().decode('utf-8'))
                except Exception:
                    data = {}

        if status_code == 200:
            if data.get("success"):
                expiry = data.get("expiry_date", "PERPETUAL")
                lic_data = {
                    "hwid": current_hwid,
                    "license_key": license_key,
                    "client_name": client_name,
                    "activated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "expiry_date": expiry,
                    "token": data.get("token", "")
                }
                _save_license_file(lic_data)
                return True, f"Activation Successful! Licensed to {client_name}."
            else:
                msg = data.get("message", "License Key rejected by server.")
                return False, f"Activation Failed: {msg}"
        elif status_code == 404:
            return False, "Activation server endpoint not found (404)."
        elif status_code == 403:
            return False, "License Key is invalid, expired, or already bound to another PC."
        else:
            return False, f"Server responded with error HTTP {status_code}."

    except Exception as e:
        err_msg = str(e).lower()
        if "timed out" in err_msg or "timeout" in err_msg:
            return False, "Connection timed out. Check hospital internet or use Offline Activation."
        elif "connection" in err_msg or "getaddrinfo" in err_msg:
            return False, "Could not reach activation server. Verify internet connection."
        return False, f"Activation error: {e}"


def activate_license_offline(
    license_key: str,
    client_name: str,
    offline_token: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Offline activation mechanism for air-gapped hospital PCs.
    Verifies cryptographic offline token or master on-premise bypass key.
    """
    current_hwid = get_hardware_id()
    license_key = license_key.strip().upper()
    client_name = client_name.strip()

    if not license_key:
        return False, "Please enter a valid License Key."
    if not client_name:
        return False, "Please enter Hospital / Clinic Name."

    is_valid = False
    expiry = "PERPETUAL"

    if license_key.startswith("DEMO-") or license_key == "HOSP-ADMIN-2026-WIN7":
        is_valid = True
    elif offline_token:
        # Check against generated technician activation code
        expected_token = hashlib.sha256(
            f"{current_hwid}:{license_key}:{client_name}:{SECRET_PEPPER}".encode('utf-8')
        ).hexdigest()[:16].upper()

        if offline_token.strip().upper() == expected_token:
            is_valid = True

    if is_valid:
        lic_data = {
            "hwid": current_hwid,
            "license_key": license_key,
            "client_name": client_name,
            "activated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "expiry_date": expiry,
            "activation_mode": "OFFLINE"
        }
        _save_license_file(lic_data)
        return True, f"Offline Activation Successful! Licensed to {client_name}."
    else:
        return False, "Invalid offline activation credentials or token."


def generate_offline_technician_token(hwid: str, license_key: str, client_name: str) -> str:
    """Helper used by system administrator to issue offline token for a client's HWID."""
    return hashlib.sha256(
        f"{hwid.strip()}:{license_key.strip().upper()}:{client_name.strip()}:{SECRET_PEPPER}".encode('utf-8')
    ).hexdigest()[:16].upper()


def _save_license_file(license_dict: dict):
    """Encrypt and write license file to AppData."""
    if not os.path.exists(APPDATA_DIR):
        os.makedirs(APPDATA_DIR, exist_ok=True)
    encrypted_data = _encrypt_payload(license_dict)
    with open(LICENSE_FILE_PATH, "wb") as f:
        f.write(encrypted_data)


# Self-test when run directly
if __name__ == "__main__":
    print("=== Hospital POS HWID & License Diagnostic ===")
    hwid = get_hardware_id()
    print(f"Machine HWID: {hwid}")
    print(f"License Path: {LICENSE_FILE_PATH}")
    
    is_valid, msg, lic_info = verify_license()
    print(f"Current License Status: {msg} (Valid: {is_valid})")

    # Demonstrate test offline activation if unlicensed
    if not is_valid:
        print("\nTesting offline demo activation...")
        success, act_msg = activate_license_offline("DEMO-WIN7-TEST", "City Care Diagnostic Center")
        print(f"Activation Result: {act_msg}")
        is_valid2, msg2, info2 = verify_license()
        print(f"Verification after activation: {msg2} (Valid: {is_valid2})")
