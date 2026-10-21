"""
Hospital POS & Billing System - Data Vault & Cloud Synchronization Engine
Target Platform: Windows 7 (32-bit/64-bit) | Python 3.8.10 (32-bit)

Key Architectural Pillars:
1. Structured JSON Text Replication:
   - Every issued voucher is automatically archived as a human-readable, lossless JSON text file.
   - Format: V-YYYYMMDD-XXXX.json in the configured Vouchers_JSON directory.
   - Text files can be opened in Notepad, inspected, audited, or backed up anywhere.
2. Full Database JSON Text Dump:
   - Dumps all vouchers, voucher_items, diagnostic tests, categories, and settings into a single file.
3. Two-Way Disaster Recovery & Restoration Engine:
   - Restore SQLite database from a single JSON file, a full dump, or an entire directory of JSONs.
4. MongoDB Atlas Cloud Vault:
   - Direct cloud mirror of vouchers collection via pymongo or HTTP endpoint.
   - Background non-blocking sync on new vouchers.
   - 1-click 'Push to Cloud' and 'Pull & Restore from Cloud'.
"""

import os
import re
import json
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

import database
from config import (
    DEFAULT_STORAGE_ROOT,
    DEFAULT_VOUCHER_JSON_DIR,
    DEFAULT_MONGO_URI,
    DEFAULT_MONGO_DB,
    DEFAULT_MONGO_COLLECTION,
    APP_VERSION
)

# Optional pymongo support
try:
    import pymongo
    HAS_PYMONGO = True
except ImportError:
    HAS_PYMONGO = False


def _sanitize_filename(name: str) -> str:
    """Sanitize string for safe Windows filesystem naming."""
    clean = re.sub(r'[\\/*?:"<>| ]', '_', name.strip())
    return clean[:40] if clean else "voucher"


# ==============================================================================
# 1. DIRECTORY RESOLUTION & LOCAL JSON TEXT ARCHIVE
# ==============================================================================

def get_voucher_json_directory() -> str:
    """Resolve target directory for storing generated voucher JSON text files."""
    dir_path = database.get_setting("voucher_json_dir", DEFAULT_VOUCHER_JSON_DIR)
    try:
        os.makedirs(dir_path, exist_ok=True)
    except Exception:
        dir_path = os.path.join(os.path.expanduser("~"), "Hospital_POS_Data", "Vouchers_JSON")
        os.makedirs(dir_path, exist_ok=True)
    return dir_path


def format_voucher_document(voucher: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format a raw SQLite voucher dictionary into a clean, canonical JSON document
    suitable for MongoDB Atlas and filesystem text archiving.
    """
    v_no = voucher.get("voucher_no", "V-UNKNOWN")
    return {
        "_id": v_no,
        "voucher_no": v_no,
        "format_version": "1.0",
        "created_at": str(voucher.get("created_at", "")),
        "created_by": voucher.get("created_by", "Reception"),
        "patient": {
            "name": voucher.get("patient_name", ""),
            "age": voucher.get("patient_age", 0),
            "gender": voucher.get("patient_gender", "Male"),
            "phone": voucher.get("patient_phone", ""),
            "referred_by": voucher.get("referred_by", "Self / General")
        },
        "financials": {
            "subtotal": float(voucher.get("subtotal", 0.0)),
            "discount_type": voucher.get("discount_type", "fixed"),
            "discount_val": float(voucher.get("discount_val", 0.0)),
            "discount_amount": float(voucher.get("discount_amount", 0.0)),
            "total_amount": float(voucher.get("total_amount", 0.0)),
            "paid_amount": float(voucher.get("paid_amount", 0.0)),
            "due_amount": float(voucher.get("due_amount", 0.0)),
            "payment_method": voucher.get("payment_method", "CASH"),
            "payment_status": voucher.get("payment_status", "PAID")
        },
        "items": [
            {
                "test_id": it.get("test_id"),
                "test_code": it.get("test_code", ""),
                "test_name": it.get("test_name", ""),
                "unit_price": float(it.get("unit_price", 0.0)),
                "quantity": int(it.get("quantity", 1)),
                "item_total": float(it.get("item_total", 0.0))
            }
            for it in voucher.get("items", [])
        ],
        "metadata": {
            "remarks": voucher.get("remarks", ""),
            "printed_count": voucher.get("printed_count", 0),
            "last_printed_at": str(voucher.get("last_printed_at", "")),
            "synced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    }


def save_voucher_to_json(voucher: Dict[str, Any], output_dir: Optional[str] = None) -> str:
    """
    Save complete voucher record as a formatted, human-readable JSON text file.
    Returns absolute path of the generated .json file.
    """
    if not output_dir:
        output_dir = get_voucher_json_directory()

    os.makedirs(output_dir, exist_ok=True)

    v_no = voucher.get("voucher_no", "V-UNKNOWN")
    patient_name = _sanitize_filename(voucher.get("patient_name", "patient"))
    filename = f"{v_no}_{patient_name}.json"
    filepath = os.path.join(output_dir, filename)

    doc = format_voucher_document(voucher)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)

    print(f"[DataVault] Archived Voucher JSON Text: {filepath}")
    return filepath


def export_full_database_to_json(output_dir: Optional[str] = None) -> str:
    """
    Export the entire SQLite database (vouchers, items, tests, categories, settings)
    into a single structured JSON master text file.
    """
    if not output_dir:
        output_dir = get_voucher_json_directory()

    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Hospital_POS_Full_Dump_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)

    data = database.get_full_database_dump_data()

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"[DataVault] Exported Full Database JSON: {filepath}")
    return filepath


# ==============================================================================
# 2. RESTORATION ENGINE (FROM LOCAL JSON FILES OR DIRECTORIES)
# ==============================================================================

def restore_from_json_file(file_path: str, overwrite_existing: bool = False) -> Dict[str, Any]:
    """
    Restore data into SQLite from a JSON file.
    Supports both:
    1. Single voucher JSON file (e.g., V-20261021-0001.json)
    2. Full database dump JSON file (containing categories, tests, vouchers)
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Check if this is a Full Database Dump
    if isinstance(data, dict) and data.get("format") == "HOSPITAL_POS_FULL_JSON_BACKUP":
        vouchers = data.get("vouchers", [])
        tests = data.get("tests", [])

        # Restore tests if missing
        restored_tests = 0
        for t in tests:
            code = t.get("code")
            if code and not database.get_test_by_exact_code(code):
                try:
                    database.add_test({
                        "category_id": t.get("category_id"),
                        "name": t.get("name", ""),
                        "code": code,
                        "price": float(t.get("price", 0.0)),
                        "cost": float(t.get("cost", 0.0)),
                        "sample_type": t.get("sample_type", "Blood"),
                        "delivery_time": t.get("delivery_time", "Same Day")
                    })
                    restored_tests += 1
                except Exception:
                    pass

        # Restore vouchers
        added_count = 0
        skipped_count = 0
        for v in vouchers:
            success = database.restore_or_upsert_voucher(v, overwrite_existing=overwrite_existing)
            if success:
                added_count += 1
            else:
                skipped_count += 1

        return {
            "type": "full_dump",
            "restored_vouchers": added_count,
            "skipped_vouchers": skipped_count,
            "restored_tests": restored_tests,
            "total_records": len(vouchers)
        }

    # Otherwise, treat as a single voucher document
    elif isinstance(data, dict) and "voucher_no" in data:
        success = database.restore_or_upsert_voucher(data, overwrite_existing=overwrite_existing)
        return {
            "type": "single_voucher",
            "voucher_no": data.get("voucher_no"),
            "restored": success,
            "overwritten": overwrite_existing and success,
            "skipped": not success
        }
    else:
        raise ValueError("Invalid JSON format: unrecognized schema.")


def restore_from_json_folder(folder_path: str, overwrite_existing: bool = False) -> Dict[str, Any]:
    """
    Bulk restore all .json voucher files within a directory into SQLite.
    """
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        raise NotADirectoryError(f"Directory not found: {folder_path}")

    json_files = [
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if f.lower().endswith(".json") and not f.startswith("Hospital_POS_Full_Dump")
    ]

    total_files = len(json_files)
    added = 0
    skipped = 0
    errors = 0

    for fp in json_files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                doc = json.load(f)
            if isinstance(doc, dict) and "voucher_no" in doc:
                if database.restore_or_upsert_voucher(doc, overwrite_existing=overwrite_existing):
                    added += 1
                else:
                    skipped += 1
            else:
                errors += 1
        except Exception as e:
            print(f"[DataVault] Error restoring {fp}: {e}")
            errors += 1

    return {
        "total_files": total_files,
        "restored": added,
        "skipped": skipped,
        "errors": errors
    }


# ==============================================================================
# 3. MONGODB ATLAS CLOUD VAULT & SYNCHRONIZATION
# ==============================================================================

def get_mongo_settings() -> Tuple[str, str, str]:
    """Retrieve MongoDB connection parameters from settings table or fallback to config."""
    uri = database.get_setting("mongo_atlas_uri", DEFAULT_MONGO_URI).strip()
    db_name = database.get_setting("mongo_db_name", DEFAULT_MONGO_DB).strip() or "Hospital_POS_Cloud"
    collection_name = DEFAULT_MONGO_COLLECTION
    return uri, db_name, collection_name


def test_mongo_connection(uri: Optional[str] = None) -> Dict[str, Any]:
    """
    Test connectivity to MongoDB Atlas cluster.
    Returns status dict with latency, server info, and error message if failed.
    """
    if not HAS_PYMONGO:
        return {
            "success": False,
            "message": "The 'pymongo' library is not available. Run: pip install pymongo dnspython"
        }

    if not uri:
        uri, _, _ = get_mongo_settings()

    if not uri:
        return {
            "success": False,
            "message": "No MongoDB Atlas connection URI configured. Please enter URI in Settings."
        }

    try:
        start_time = datetime.now()
        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
        # Execute ping command
        client.admin.command('ping')
        elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        server_info = client.server_info()
        version = server_info.get("version", "Unknown")
        client.close()

        return {
            "success": True,
            "latency_ms": elapsed_ms,
            "version": version,
            "message": f"Successfully connected to MongoDB Atlas (v{version}) in {elapsed_ms}ms!"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"MongoDB Connection Failed: {str(e)}"
        }


def push_to_mongodb(
    vouchers: Optional[List[Dict[str, Any]]] = None,
    uri: Optional[str] = None,
    db_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Push and upsert vouchers to MongoDB Atlas collection.
    If vouchers list is not provided, pushes all vouchers in the local SQLite database.
    """
    if not HAS_PYMONGO:
        return {"success": False, "message": "pymongo is not installed."}

    cfg_uri, cfg_db, col_name = get_mongo_settings()
    target_uri = uri or cfg_uri
    target_db = db_name or cfg_db

    if not target_uri:
        return {"success": False, "message": "MongoDB Atlas URI is empty. Configure it in Admin Settings."}

    if vouchers is None:
        vouchers = database.get_all_vouchers_with_items()

    if not vouchers:
        return {"success": True, "count": 0, "message": "No vouchers to synchronize."}

    try:
        client = pymongo.MongoClient(target_uri, serverSelectionTimeoutMS=8000)
        db = client[target_db]
        collection = db[col_name]

        # Ensure index on voucher_no
        collection.create_index("voucher_no", unique=True)

        operations = []
        for v in vouchers:
            doc = format_voucher_document(v)
            operations.append(
                pymongo.UpdateOne(
                    {"voucher_no": doc["voucher_no"]},
                    {"$set": doc},
                    upsert=True
                )
            )

        if operations:
            result = collection.bulk_write(operations, ordered=False)
            upserted = len(result.upserted_ids) if result.upserted_ids else 0
            modified = result.modified_count
            total_synced = upserted + modified

            # Record sync timestamp in settings
            database.set_setting("last_mongo_sync_timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            client.close()

            return {
                "success": True,
                "total_vouchers": len(vouchers),
                "upserted": upserted,
                "modified": modified,
                "message": f"Synced {total_synced} vouchers to MongoDB Atlas ({upserted} new, {modified} updated)."
            }
        else:
            client.close()
            return {"success": True, "count": 0, "message": "Zero records processed."}

    except Exception as e:
        return {"success": False, "message": f"MongoDB Sync Error: {str(e)}"}


def pull_and_restore_from_mongodb(
    uri: Optional[str] = None,
    db_name: Optional[str] = None,
    overwrite_existing: bool = False
) -> Dict[str, Any]:
    """
    Download all voucher documents from MongoDB Atlas collection and restore into local SQLite database.
    """
    if not HAS_PYMONGO:
        return {"success": False, "message": "pymongo is not installed."}

    cfg_uri, cfg_db, col_name = get_mongo_settings()
    target_uri = uri or cfg_uri
    target_db = db_name or cfg_db

    if not target_uri:
        return {"success": False, "message": "MongoDB Atlas URI is empty. Configure it in Admin Settings."}

    try:
        client = pymongo.MongoClient(target_uri, serverSelectionTimeoutMS=10000)
        db = client[target_db]
        collection = db[col_name]

        docs = list(collection.find().sort("created_at", 1))
        client.close()

        if not docs:
            return {"success": True, "count": 0, "message": "No vouchers found in MongoDB Atlas collection."}

        added = 0
        skipped = 0
        for doc in docs:
            # Flatten document fields for SQLite restore engine
            voucher_payload = {
                "voucher_no": doc.get("voucher_no"),
                "patient_name": doc.get("patient", {}).get("name", doc.get("patient_name", "")),
                "patient_age": doc.get("patient", {}).get("age", doc.get("patient_age", 0)),
                "patient_gender": doc.get("patient", {}).get("gender", doc.get("patient_gender", "Male")),
                "patient_phone": doc.get("patient", {}).get("phone", doc.get("patient_phone", "")),
                "referred_by": doc.get("patient", {}).get("referred_by", doc.get("referred_by", "Self / General")),
                "subtotal": doc.get("financials", {}).get("subtotal", doc.get("subtotal", 0.0)),
                "discount_type": doc.get("financials", {}).get("discount_type", doc.get("discount_type", "fixed")),
                "discount_val": doc.get("financials", {}).get("discount_val", doc.get("discount_val", 0.0)),
                "discount_amount": doc.get("financials", {}).get("discount_amount", doc.get("discount_amount", 0.0)),
                "total_amount": doc.get("financials", {}).get("total_amount", doc.get("total_amount", 0.0)),
                "paid_amount": doc.get("financials", {}).get("paid_amount", doc.get("paid_amount", 0.0)),
                "due_amount": doc.get("financials", {}).get("due_amount", doc.get("due_amount", 0.0)),
                "payment_method": doc.get("financials", {}).get("payment_method", doc.get("payment_method", "CASH")),
                "payment_status": doc.get("financials", {}).get("payment_status", doc.get("payment_status", "PAID")),
                "remarks": doc.get("metadata", {}).get("remarks", doc.get("remarks", "")),
                "created_by": doc.get("created_by", "Reception"),
                "created_at": doc.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                "items": doc.get("items", [])
            }

            if database.restore_or_upsert_voucher(voucher_payload, overwrite_existing=overwrite_existing):
                added += 1
            else:
                skipped += 1

        return {
            "success": True,
            "total_fetched": len(docs),
            "restored": added,
            "skipped": skipped,
            "message": f"Successfully restored {added} vouchers from MongoDB Atlas (Skipped {skipped} already existing)."
        }

    except Exception as e:
        return {"success": False, "message": f"Error pulling from MongoDB Atlas: {str(e)}"}


# ==============================================================================
# 4. ASYNC BACKGROUND SYNC DISPATCHER
# ==============================================================================

def _async_sync_worker(voucher: Dict[str, Any]):
    """Internal worker running in background thread to sync a newly created voucher."""
    uri, _, _ = get_mongo_settings()
    if not uri:
        return

    auto_sync = database.get_setting("mongo_auto_sync", "1")
    if auto_sync != "1":
        return

    try:
        push_to_mongodb([voucher], uri=uri)
    except Exception as e:
        print(f"[DataVault] Background MongoDB Sync warning: {e}")


def trigger_async_mongo_sync(voucher: Dict[str, Any]):
    """Launch non-blocking background thread to sync voucher to MongoDB Atlas."""
    t = threading.Thread(target=_async_sync_worker, args=(voucher,), daemon=True)
    t.start()
