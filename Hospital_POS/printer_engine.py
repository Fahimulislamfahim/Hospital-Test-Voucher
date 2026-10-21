"""
Hospital POS & Billing System - Direct Silent Printing Engine
Target Platform: Windows 7 (32-bit/64-bit) | Python 3.8.10 (32-bit)

Key Architectural Features:
1. Zero Dialogs: Never opens Windows print dialog popups. Directly spools to the target printer.
2. Dual Print Pipelines:
   - Pipeline A: Direct RAW / Text Spooling for 80mm Thermal Roll Printers (ESC/POS paper-cut support).
   - Pipeline B: Windows GDI Device Context (win32ui) for pixel-perfect typography on A5/A4 laser printers.
3. Fallback & Simulation: If running in a test environment without pywin32 or physical printers,
   gracefully generates a formatted thermal preview file and logs spool output without crashing.
4. Automatic Default Printer Resolution from Windows Spooler or Database Settings.
"""

import os
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional

from config import APP_DIR
import database

# Check pywin32 availability
HAS_WIN32 = False
try:
    import win32print
    import win32ui
    import win32con
    import win32api
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


# ==============================================================================
# 1. PRINTER DISCOVERY & SELECTION
# ==============================================================================

def get_available_printers() -> List[str]:
    """Return a list of all installed printer names on this Windows PC."""
    if not HAS_WIN32:
        return ["Default Virtual Printer (Simulation)"]

    printers = []
    try:
        # Flags: PRINTER_ENUM_LOCAL | PRINTER_ENUM_CONNECTIONS
        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        for p in win32print.EnumPrinters(flags):
            # p[2] is the printer name
            printers.append(p[2])
    except Exception as e:
        print(f"[PrinterEngine] Error querying printers: {e}")

    return printers or ["Default Windows Printer"]


def get_target_printer() -> str:
    """
    Resolve target printer name:
    1. Check database setting 'printer_name'.
    2. If set to 'DEFAULT' or invalid, fetch Windows OS default printer.
    """
    configured = database.get_setting("printer_name", "DEFAULT")
    if configured and configured != "DEFAULT":
        return configured

    if HAS_WIN32:
        try:
            return win32print.GetDefaultPrinter()
        except Exception:
            pass

    return "DEFAULT"


# ==============================================================================
# 2. 80mm THERMAL RECEIPT TEXT BUILDER (Zero-Lag, Universal Roll Printing)
# ==============================================================================

def generate_80mm_receipt_text(voucher: Dict[str, Any], settings: Optional[Dict[str, str]] = None) -> str:
    """
    Construct a clean, well-aligned 80mm thermal receipt (48-column standard).
    Compatible with any 80mm receipt printer (Epson, Xprinter, Rongta, Posiflex).
    """
    if not settings:
        settings = database.get_all_settings()

    h_name = settings.get("hospital_name", "CITY CARE DIAGNOSTIC CENTER")
    h_tag = settings.get("hospital_tagline", "24/7 Digital Diagnostic Center")
    h_addr = settings.get("hospital_address", "Medical College Road, Central Gate")
    h_phone = settings.get("hospital_phone", "Ph: +880 1711-000000")
    footer = settings.get("voucher_footer", "Report delivery within 24 hours. Get well soon.")
    curr = settings.get("currency_symbol", "Tk")

    W = 48  # 48 characters width standard for 80mm font A
    sep_single = "-" * W
    sep_double = "=" * W

    def center(txt: str) -> str:
        txt = str(txt).strip()
        if len(txt) >= W:
            return txt[:W]
        pad = (W - len(txt)) // 2
        return " " * pad + txt

    def row(left: str, right: str) -> str:
        left = str(left)
        right = str(right)
        space = W - len(left) - len(right)
        if space < 1:
            space = 1
        return left + (" " * space) + right

    lines = []
    lines.append("")
    lines.append(center(h_name.upper()))
    if h_tag:
        lines.append(center(h_tag))
    if h_addr:
        lines.append(center(h_addr))
    if h_phone:
        lines.append(center(h_phone))
    lines.append(center("*** DIAGNOSTIC BILL / MONEY RECEIPT ***"))
    lines.append(sep_double)

    # Voucher & Date Info
    v_no = voucher.get("voucher_no", "V-00000000-0000")
    created_at = voucher.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
    receptionist = voucher.get("created_by", "Reception")

    lines.append(row(f"Voucher: {v_no}", f"Date: {created_at[:16]}"))
    lines.append(row(f"Operator: {receptionist}", f"Print Count: {voucher.get('printed_count', 0) + 1}"))
    lines.append(sep_single)

    # Patient Information
    p_name = voucher.get("patient_name", "Walking Patient")
    p_age = voucher.get("patient_age", 0)
    p_gender = voucher.get("patient_gender", "Male")
    p_phone = voucher.get("patient_phone", "N/A")
    ref_by = voucher.get("referred_by", "Self")

    lines.append(row(f"Patient: {p_name[:24]}", f"Age/Sex: {p_age}Y / {p_gender[:1]}"))
    lines.append(row(f"Phone  : {p_phone}", f"Ref: {ref_by[:18]}"))
    lines.append(sep_single)

    # Line Items Header
    # Format: Code (5) | Test Name (28) | Price (12)
    lines.append(f"{'SL':<3} {'Test Description':<30} {'Qty':<4} {'Amount':>8}")
    lines.append(sep_single)

    items = voucher.get("items", [])
    for idx, item in enumerate(items, 1):
        code = item.get("test_code", "")
        name = item.get("test_name", "")
        qty = item.get("quantity", 1)
        price = float(item.get("item_total", item.get("unit_price", 0)))
        
        # Display: first line has SL, short name, Qty, Price
        short_name = name[:28]
        lines.append(f"{idx:<3} {short_name:<30} {qty:<4} {price:>8.2f}")
        # If test name is longer than 28 chars, print remainder on second line
        if len(name) > 28:
            lines.append(f"    {name[28:56]}")

    lines.append(sep_single)

    # Billing Totals Breakdown
    subtotal = float(voucher.get("subtotal", 0.0))
    disc_val = float(voucher.get("discount_val", 0.0))
    disc_type = voucher.get("discount_type", "fixed")
    disc_amt = float(voucher.get("discount_amount", 0.0))
    total = float(voucher.get("total_amount", 0.0))
    paid = float(voucher.get("paid_amount", 0.0))
    due = float(voucher.get("due_amount", 0.0))
    method = voucher.get("payment_method", "CASH")
    status = voucher.get("payment_status", "PAID")

    lines.append(row("Subtotal:", f"{curr} {subtotal:>8.2f}"))
    if disc_amt > 0:
        disc_label = f"Discount ({disc_val:.0f}%):" if disc_type == "percent" else "Discount (Fixed):"
        lines.append(row(disc_label, f"-{curr} {disc_amt:>8.2f}"))

    lines.append(row("NET PAYABLE TOTAL:", f"{curr} {total:>8.2f}"))
    lines.append(row(f"Paid Amount ({method}):", f"{curr} {paid:>8.2f}"))
    
    if due > 0:
        lines.append(row("BALANCE DUE:", f"*** {curr} {due:>8.2f} ***"))
    else:
        lines.append(row("STATUS:", "PAID IN FULL"))

    lines.append(sep_double)

    # Barcode representation & Footer
    lines.append(center(f"*{v_no}*"))
    if footer:
        lines.append(center(footer))
    lines.append(center("Software Powered by Hospital POS"))
    lines.append("\n\n\n")  # Line feeds for paper cut

    return "\n".join(lines)


# ==============================================================================
# 3. SILENT DIRECT PRINT PIPELINE
# ==============================================================================

def print_voucher_silently(
    voucher: Dict[str, Any],
    printer_name: Optional[str] = None,
    paper_size: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute 100% silent direct print without popping up any print dialog.
    
    Returns:
        {'success': bool, 'message': str, 'printer': str, 'preview_file': str}
    """
    if not printer_name:
        printer_name = get_target_printer()

    if not paper_size:
        paper_size = database.get_setting("paper_size", "80mm")

    settings = database.get_all_settings()
    receipt_text = generate_80mm_receipt_text(voucher, settings)

    # Always save a copy of the receipt preview locally
    preview_dir = os.path.join(APP_DIR, "receipt_previews")
    os.makedirs(preview_dir, exist_ok=True)
    v_no = voucher.get("voucher_no", "voucher").replace("/", "_").replace("\\", "_")
    preview_file = os.path.join(preview_dir, f"{v_no}.txt")

    try:
        with open(preview_file, "w", encoding="utf-8") as f:
            f.write(receipt_text)
    except Exception as e:
        print(f"[PrinterEngine] Warning: Could not write preview file: {e}")

    # If running on target Windows 7 PC with pywin32
    if HAS_WIN32:
        try:
            # 1. Resolve printer handle
            if printer_name == "DEFAULT":
                printer_name = win32print.GetDefaultPrinter()

            h_printer = win32print.OpenPrinter(printer_name)
            try:
                # 2. Spool raw document directly to the printer
                doc_name = f"Voucher_{v_no}"
                # ESC/POS commands: Initialize printer (ESC @), Cut paper (GS V 66 0)
                raw_bytes = bytearray()
                raw_bytes.extend(b"\x1b\x40")  # ESC @ : Initialize printer
                raw_bytes.extend(receipt_text.encode("cp437", errors="replace"))
                raw_bytes.extend(b"\n\n\n\n\x1d\x56\x42\x00")  # GS V 'B' 0 : Cut paper

                job_info = ("Hospital_Voucher", None, "RAW")
                job_id = win32print.StartDocPrinter(h_printer, 1, job_info)
                win32print.StartPagePrinter(h_printer)
                win32print.WritePrinter(h_printer, bytes(raw_bytes))
                win32print.EndPagePrinter(h_printer)
                win32print.EndDocPrinter(h_printer)

                # Increment printed audit count in DB
                v_id = voucher.get("id")
                if v_id:
                    database.increment_print_count(v_id)

                return {
                    "success": True,
                    "message": f"Voucher {v_no} sent silently to printer '{printer_name}'.",
                    "printer": printer_name,
                    "preview_file": preview_file
                }
            finally:
                win32print.ClosePrinter(h_printer)

        except Exception as e:
            # If RAW mode fails or printer is a GDI/Laser printer, fallback to GDI TextOut
            print(f"[PrinterEngine] RAW spool failed ({e}), attempting GDI DC print...")
            gdi_res = _print_via_gdi_dc(voucher, receipt_text, printer_name)
            if gdi_res["success"]:
                v_id = voucher.get("id")
                if v_id:
                    database.increment_print_count(v_id)
                return gdi_res
            else:
                return {
                    "success": False,
                    "message": f"Print failed on '{printer_name}': {e}",
                    "printer": printer_name,
                    "preview_file": preview_file
                }
    else:
        # Simulation Mode (for dev environment where pywin32 is uninstalled)
        print(f"[PrinterEngine - SIMULATION] Silent print triggered for: {v_no}")
        print(f"[PrinterEngine - SIMULATION] Spooled to preview: {preview_file}")
        v_id = voucher.get("id")
        if v_id:
            database.increment_print_count(v_id)

        return {
            "success": True,
            "message": f"[Simulation] Voucher printed to preview file: {preview_file}",
            "printer": "Simulation_Virtual_Printer",
            "preview_file": preview_file
        }


def _print_via_gdi_dc(voucher: Dict[str, Any], text: str, printer_name: str) -> Dict[str, Any]:
    """
    Fallback GDI Printing Pipeline using win32ui Device Context.
    Handles standard Windows laser / inkjet printers (A5 / Letter / A4).
    """
    try:
        h_dc = win32ui.CreateDC()
        h_dc.CreatePrinterDC(printer_name)
        h_dc.StartDoc(f"Voucher_{voucher.get('voucher_no', 'Receipt')}")
        h_dc.StartPage()

        # Create Monospace font for crisp alignment
        font_dict = {
            "name": "Courier New",
            "height": 22,
            "weight": 600
        }
        font = win32ui.CreateFont(font_dict)
        h_dc.SelectObject(font)

        # Print line by line
        y = 50
        line_height = 28
        for line in text.splitlines():
            h_dc.TextOut(50, y, line)
            y += line_height

        h_dc.EndPage()
        h_dc.EndDoc()
        h_dc.DeleteDC()

        return {
            "success": True,
            "message": f"Printed via GDI Device Context to '{printer_name}'.",
            "printer": printer_name
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"GDI Print error: {e}",
            "printer": printer_name
        }


# ==============================================================================
# 4. HTML RECEIPT EXPORT (For Browser View, Archival or PDF)
# ==============================================================================

def generate_html_voucher(voucher: Dict[str, Any], settings: Optional[Dict[str, str]] = None) -> str:
    """Generate modern, clean HTML template formatted for 80mm thermal receipt printing."""
    if not settings:
        settings = database.get_all_settings()

    h_name = settings.get("hospital_name", "City Care Diagnostic Center")
    h_tag = settings.get("hospital_tagline", "24/7 Digital Diagnostic Center")
    h_addr = settings.get("hospital_address", "Medical College Road, Central Gate")
    h_phone = settings.get("hospital_phone", "Ph: +880 1711-000000")
    footer = settings.get("voucher_footer", "Report delivery within 24 hours. Valid with doctor signature.")
    curr = settings.get("currency_symbol", "Tk")

    v_no = voucher.get("voucher_no", "V-00000000-0000")
    p_name = voucher.get("patient_name", "")
    p_age = voucher.get("patient_age", 0)
    p_gender = voucher.get("patient_gender", "Male")
    p_phone = voucher.get("patient_phone", "")
    ref_by = voucher.get("referred_by", "Self")
    created_at = voucher.get("created_at", "")

    items_html = ""
    for idx, item in enumerate(voucher.get("items", []), 1):
        items_html += f"""
        <tr>
            <td style="text-align:center;">{idx}</td>
            <td><strong>{item.get('test_name')}</strong><br><small>{item.get('test_code')}</small></td>
            <td style="text-align:center;">{item.get('quantity', 1)}</td>
            <td style="text-align:right;">{float(item.get('item_total', 0)):.2f}</td>
        </tr>
        """

    subtotal = float(voucher.get("subtotal", 0.0))
    disc_amt = float(voucher.get("discount_amount", 0.0))
    total = float(voucher.get("total_amount", 0.0))
    paid = float(voucher.get("paid_amount", 0.0))
    due = float(voucher.get("due_amount", 0.0))

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Voucher {v_no}</title>
<style>
  @page {{ size: 80mm auto; margin: 3mm; }}
  body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; font-size: 12px; margin: 0; padding: 5px; color: #000; width: 74mm; }}
  .text-center {{ text-align: center; }}
  .text-right {{ text-align: right; }}
  .bold {{ font-weight: bold; }}
  h2 {{ margin: 0; font-size: 16px; text-transform: uppercase; }}
  p {{ margin: 2px 0; }}
  .divider {{ border-top: 1px dashed #000; margin: 6px 0; }}
  .double-divider {{ border-top: 2px solid #000; margin: 6px 0; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 11px; }}
  th, td {{ padding: 3px 1px; }}
  th {{ border-bottom: 1px solid #000; text-align: left; }}
  .badge {{ display: inline-block; padding: 2px 5px; border: 1px solid #000; font-weight: bold; }}
</style>
</head>
<body>
  <div class="text-center">
    <h2>{h_name}</h2>
    <p>{h_tag}</p>
    <p>{h_addr}</p>
    <p>{h_phone}</p>
    <p class="bold" style="margin-top: 4px;">*** MONEY RECEIPT / VOUCHER ***</p>
  </div>
  <div class="double-divider"></div>
  <table style="margin-bottom: 4px;">
    <tr><td><strong>Voucher:</strong> {v_no}</td><td class="text-right"><strong>Date:</strong> {created_at[:16]}</td></tr>
    <tr><td><strong>Patient:</strong> {p_name}</td><td class="text-right"><strong>Age/Sex:</strong> {p_age}Y / {p_gender}</td></tr>
    <tr><td><strong>Phone:</strong> {p_phone}</td><td class="text-right"><strong>Ref:</strong> {ref_by}</td></tr>
  </table>
  <div class="divider"></div>
  <table>
    <thead>
      <tr>
        <th style="width: 10%; text-align:center;">#</th>
        <th style="width: 55%;">Test Name</th>
        <th style="width: 15%; text-align:center;">Qty</th>
        <th style="width: 20%; text-align:right;">Total</th>
      </tr>
    </thead>
    <tbody>
      {items_html}
    </tbody>
  </table>
  <div class="divider"></div>
  <table>
    <tr><td>Subtotal:</td><td class="text-right">{curr} {subtotal:.2f}</td></tr>
    <tr><td>Discount:</td><td class="text-right">-{curr} {disc_amt:.2f}</td></tr>
    <tr class="bold" style="font-size: 13px;"><td>NET TOTAL:</td><td class="text-right">{curr} {total:.2f}</td></tr>
    <tr><td>Paid Amount:</td><td class="text-right">{curr} {paid:.2f}</td></tr>
    <tr class="bold"><td>Balance Due:</td><td class="text-right">{curr} {due:.2f}</td></tr>
  </table>
  <div class="double-divider"></div>
  <div class="text-center">
    <p class="bold" style="letter-spacing: 2px; font-size: 14px;">*{v_no}*</p>
    <p>{footer}</p>
    <p style="font-size: 10px; margin-top: 6px;">Hospital Voucher Printing System</p>
  </div>
</body>
</html>"""
    return html


# Diagnostic test when run directly
if __name__ == "__main__":
    print("Available printers detected:", get_available_printers())
    print("Resolved target printer:", get_target_printer())
    dummy_voucher = {
        "id": 1,
        "voucher_no": "V-20261021-0001",
        "patient_name": "Test Patient",
        "patient_age": 32,
        "patient_gender": "Male",
        "patient_phone": "01711223344",
        "referred_by": "Prof. Dr. Rahman",
        "subtotal": 550.0,
        "discount_type": "fixed",
        "discount_val": 50.0,
        "discount_amount": 50.0,
        "total_amount": 500.0,
        "paid_amount": 500.0,
        "due_amount": 0.0,
        "payment_method": "CASH",
        "payment_status": "PAID",
        "created_by": "Receptionist_1",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "printed_count": 0,
        "items": [
            {"test_code": "101", "test_name": "Complete Blood Count (CBC with ESR)", "quantity": 1, "item_total": 400.0},
            {"test_code": "201", "test_name": "Random Blood Sugar (RBS)", "quantity": 1, "item_total": 150.0}
        ]
    }
    res = print_voucher_silently(dummy_voucher)
    print("Print Result:", res["message"])
