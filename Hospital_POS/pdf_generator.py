"""
Hospital POS & Billing System - PDF Generation & Archival Engine
Target Platform: Windows 7 (32-bit/64-bit) | Python 3.8.10 (32-bit)

Features:
1. Automated Voucher PDF Generation (saved on every print/voucher creation).
2. Daily All Calculations & Financial Audit Report PDF Export.
3. Strict Directory Archival:
   - Subfolder 1: Backups (/Backups)
   - Subfolder 2: Printed Vouchers PDF Archive (/Vouchers_PDF)
   - Subfolder 3: Daily Summary & Audit Reports (/Daily_Reports)
4. Robust Architecture: Uses ReportLab Platypus for vector-crisp documents with HTML fallback.
"""

import os
import re
from datetime import datetime
from typing import Dict, Any, List, Optional

import database
from config import DEFAULT_VOUCHER_PDF_DIR, DEFAULT_REPORTS_PDF_DIR

# Check ReportLab availability
HAS_REPORTLAB = False
try:
    from reportlab.lib.pagesizes import A5, A4, portrait
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable
    )
    from reportlab.lib.units import mm
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


def _sanitize_filename(name: str) -> str:
    """Sanitize string for safe Windows filesystem naming."""
    clean = re.sub(r'[\\/*?:"<>| ]', '_', name.strip())
    return clean[:40] if clean else "patient"


def get_voucher_pdf_directory() -> str:
    """Resolve target directory for storing generated voucher PDFs."""
    dir_path = database.get_setting("voucher_pdf_dir", DEFAULT_VOUCHER_PDF_DIR)
    try:
        os.makedirs(dir_path, exist_ok=True)
    except Exception:
        dir_path = os.path.join(os.path.expanduser("~"), "Hospital_POS_Data", "Vouchers_PDF")
        os.makedirs(dir_path, exist_ok=True)
    return dir_path


def get_reports_pdf_directory() -> str:
    """Resolve target directory for daily audit reports."""
    dir_path = database.get_setting("reports_pdf_dir", DEFAULT_REPORTS_PDF_DIR)
    try:
        os.makedirs(dir_path, exist_ok=True)
    except Exception:
        dir_path = os.path.join(os.path.expanduser("~"), "Hospital_POS_Data", "Daily_Reports")
        os.makedirs(dir_path, exist_ok=True)
    return dir_path


# ==============================================================================
# 1. INDIVIDUAL VOUCHER PDF GENERATOR (A5 FORMAT)
# ==============================================================================

def generate_voucher_pdf(voucher: Dict[str, Any], output_dir: Optional[str] = None) -> str:
    """
    Generate professional, vectorized PDF voucher and archive to target directory.
    Returns absolute path of the generated PDF.
    """
    if not output_dir:
        output_dir = get_voucher_pdf_directory()

    os.makedirs(output_dir, exist_ok=True)

    v_no = voucher.get("voucher_no", "V-00000000-0000")
    p_name = _sanitize_filename(voucher.get("patient_name", "patient"))
    filename = f"{v_no}_{p_name}.pdf"
    filepath = os.path.join(output_dir, filename)

    settings = database.get_all_settings()
    h_name = settings.get("hospital_name", "City Care Diagnostic & Hospital")
    h_tag = settings.get("hospital_tagline", "24/7 Digital Diagnostic Center")
    h_addr = settings.get("hospital_address", "Medical College Road, Central Gate")
    h_phone = settings.get("hospital_phone", "+880 1711-000000")
    footer_text = settings.get("voucher_footer", "Report delivery within 24 hours. Valid with doctor signature.")
    curr = settings.get("currency_symbol", "Tk")

    if not HAS_REPORTLAB:
        # Fallback to HTML if ReportLab is missing
        html_content = _build_voucher_html(voucher, settings)
        html_path = os.path.splitext(filepath)[0] + ".html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        return html_path

    # Build PDF using ReportLab
    doc = SimpleDocTemplate(
        filepath,
        pagesize=A5,
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=8 * mm,
        bottomMargin=8 * mm
    )

    styles = getSampleStyleSheet()

    # Custom typography styles
    style_h_name = ParagraphStyle("HName", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=14, leading=16, alignment=1, textColor=colors.HexColor("#0f766e"))
    style_h_sub = ParagraphStyle("HSub", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=10, alignment=1, textColor=colors.HexColor("#475569"))
    style_doc_title = ParagraphStyle("DocTitle", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=11, alignment=1, textColor=colors.HexColor("#0f172a"))
    style_label = ParagraphStyle("Lbl", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=colors.HexColor("#1e293b"))
    style_val = ParagraphStyle("Val", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=10, textColor=colors.HexColor("#0f172a"))
    style_th = ParagraphStyle("TH", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=colors.HexColor("#ffffff"), alignment=1)
    style_td = ParagraphStyle("TD", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=10, textColor=colors.HexColor("#1e293b"))
    style_td_r = ParagraphStyle("TDR", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=10, alignment=2, textColor=colors.HexColor("#1e293b"))
    style_barcode = ParagraphStyle("Barcode", parent=styles["Normal"], fontName="Courier-Bold", fontSize=11, leading=13, alignment=1, textColor=colors.HexColor("#0f766e"))
    style_footer = ParagraphStyle("Foot", parent=styles["Normal"], fontName="Helvetica-Oblique", fontSize=7, leading=9, alignment=1, textColor=colors.HexColor("#64748b"))

    story = []

    # 1. Header Banner
    story.append(Paragraph(h_name.upper(), style_h_name))
    if h_tag:
        story.append(Paragraph(h_tag, style_h_sub))
    story.append(Paragraph(f"{h_addr} • Phone: {h_phone}", style_h_sub))
    story.append(Spacer(1, 3 * mm))

    # Badge Box for Document Type
    badge_table = Table([[Paragraph("DIAGNOSTIC MONEY RECEIPT / BILL", style_doc_title)]], colWidths=[128 * mm])
    badge_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
        ("LINEABOVE", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
    ]))
    story.append(badge_table)
    story.append(Spacer(1, 3 * mm))

    # 2. Patient & Voucher Details Table
    p_age = voucher.get("patient_age", 0)
    p_sex = voucher.get("patient_gender", "Male")
    c_date = str(voucher.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M")))[:16]
    ref_by = voucher.get("referred_by", "Self / General")

    patient_grid = [
        [
            Paragraph("<b>Voucher No:</b>", style_label), Paragraph(v_no, style_val),
            Paragraph("<b>Date / Time:</b>", style_label), Paragraph(c_date, style_val)
        ],
        [
            Paragraph("<b>Patient Name:</b>", style_label), Paragraph(str(voucher.get("patient_name", "")), style_val),
            Paragraph("<b>Age / Gender:</b>", style_label), Paragraph(f"{p_age} Years / {p_sex}", style_val)
        ],
        [
            Paragraph("<b>Phone:</b>", style_label), Paragraph(str(voucher.get("patient_phone", "N/A")), style_val),
            Paragraph("<b>Ref. Doctor:</b>", style_label), Paragraph(str(ref_by), style_val)
        ],
    ]
    p_table = Table(patient_grid, colWidths=[24 * mm, 40 * mm, 24 * mm, 40 * mm])
    p_table.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fafafa")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
    ]))
    story.append(p_table)
    story.append(Spacer(1, 3 * mm))

    # 3. Diagnostic Tests Line Items Table
    test_rows = [
        [
            Paragraph("#", style_th),
            Paragraph("Code", style_th),
            Paragraph("Diagnostic Test Name", style_th),
            Paragraph("Sample", style_th),
            Paragraph("Qty", style_th),
            Paragraph(f"Price ({curr})", style_th),
            Paragraph(f"Total ({curr})", style_th)
        ]
    ]

    items = voucher.get("items", [])
    for idx, item in enumerate(items, 1):
        test_rows.append([
            Paragraph(str(idx), style_td),
            Paragraph(str(item.get("test_code", "")), style_td),
            Paragraph(str(item.get("test_name", "")), style_td),
            Paragraph(str(item.get("sample_type", "Blood")), style_td),
            Paragraph(str(item.get("quantity", 1)), style_td),
            Paragraph(f"{float(item.get('unit_price', item.get('price', 0))):.2f}", style_td_r),
            Paragraph(f"{float(item.get('item_total', 0)):.2f}", style_td_r),
        ])

    items_table = Table(test_rows, colWidths=[8 * mm, 14 * mm, 46 * mm, 20 * mm, 10 * mm, 15 * mm, 15 * mm])
    t_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
    ]
    # Zebra striping
    for i in range(1, len(test_rows)):
        if i % 2 == 0:
            t_style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f8fafc")))

    items_table.setStyle(TableStyle(t_style))
    story.append(items_table)
    story.append(Spacer(1, 3 * mm))

    # 4. Financial Calculations Block
    subtotal = float(voucher.get("subtotal", 0.0))
    disc_amt = float(voucher.get("discount_amount", 0.0))
    total = float(voucher.get("total_amount", 0.0))
    paid = float(voucher.get("paid_amount", 0.0))
    due = float(voucher.get("due_amount", 0.0))
    method = voucher.get("payment_method", "CASH")
    status = voucher.get("payment_status", "PAID")

    due_color = colors.HexColor("#dc2626") if due > 0 else colors.HexColor("#059669")
    status_text = f"DUE ({curr} {due:.2f})" if due > 0 else "PAID IN FULL"

    fin_grid = [
        [
            Paragraph("<b>Payment Status:</b>", style_label),
            Paragraph(f"<b><font color='{due_color.hexval()}'>{status_text}</font></b> (Method: {method})", style_val),
            Paragraph("<b>Subtotal:</b>", style_td_r), Paragraph(f"{curr} {subtotal:.2f}", style_td_r)
        ],
        [
            Paragraph("<b>Printed Count:</b>", style_label), Paragraph(str(voucher.get("printed_count", 1)), style_val),
            Paragraph("<b>Discount:</b>", style_td_r), Paragraph(f"-{curr} {disc_amt:.2f}", style_td_r)
        ],
        [
            Paragraph("", style_label), Paragraph("", style_val),
            Paragraph("<b>NET PAYABLE:</b>", style_td_r), Paragraph(f"<b>{curr} {total:.2f}</b>", style_td_r)
        ],
        [
            Paragraph("", style_label), Paragraph("", style_val),
            Paragraph("<b>Paid Amount:</b>", style_td_r), Paragraph(f"{curr} {paid:.2f}", style_td_r)
        ],
        [
            Paragraph("", style_label), Paragraph("", style_val),
            Paragraph("<b>Balance Due:</b>", style_td_r), Paragraph(f"<b><font color='{due_color.hexval()}'>{curr} {due:.2f}</font></b>", style_td_r)
        ]
    ]

    fin_table = Table(fin_grid, colWidths=[26 * mm, 42 * mm, 30 * mm, 30 * mm])
    fin_table.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("BACKGROUND", (2, 2), (-1, 2), colors.HexColor("#f0fdfa")),
        ("LINEBELOW", (2, 2), (-1, 2), 1, colors.HexColor("#0d9488")),
        ("BOX", (2, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
    ]))
    story.append(KeepTogether(fin_table))
    story.append(Spacer(1, 4 * mm))

    # 5. Signatures and Barcode Footer
    story.append(Paragraph(f"*{v_no}*", style_barcode))
    story.append(Spacer(1, 4 * mm))

    sig_table = Table([
        [Paragraph("____________________<br/>Patient Signature", style_footer),
         Paragraph("____________________<br/>Authorized Signature", style_footer)]
    ], colWidths=[64 * mm, 64 * mm])
    sig_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(sig_table)
    story.append(Spacer(1, 2 * mm))

    if footer_text:
        story.append(Paragraph(footer_text, style_footer))

    doc.build(story)
    print(f"[PDFGenerator] Saved Voucher PDF: {filepath}")
    return filepath


# ==============================================================================
# 2. DAILY ALL CALCULATIONS & FINANCIAL AUDIT PDF EXPORT (A4 FORMAT)
# ==============================================================================

def generate_daily_audit_pdf(date_str: str, output_dir: Optional[str] = None) -> str:
    """
    Generate comprehensive executive financial audit report for a given day.
    Includes KPI summary cards, revenue reconciliation, test breakdown, and patient register.
    """
    if not output_dir:
        output_dir = get_reports_pdf_directory()

    os.makedirs(output_dir, exist_ok=True)
    filename = f"Daily_Audit_Report_{date_str}.pdf"
    filepath = os.path.join(output_dir, filename)

    settings = database.get_all_settings()
    h_name = settings.get("hospital_name", "City Care Diagnostic & Hospital")
    curr = settings.get("currency_symbol", "Tk")

    # Fetch daily metrics
    summary = database.get_daily_summary(date_str)

    # Fetch itemized vouchers
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT voucher_no, patient_name, patient_phone, subtotal, discount_amount,
               total_amount, paid_amount, due_amount, payment_method, payment_status,
               created_at
        FROM vouchers
        WHERE DATE(created_at) = DATE(?)
        ORDER BY id ASC;
    """, (date_str,))
    vouchers = [dict(r) for r in cursor.fetchall()]

    # Fetch test performance distribution
    cursor.execute("""
        SELECT vi.test_name, vi.test_code, COUNT(vi.id) as qty_count, SUM(vi.item_total) as total_rev
        FROM voucher_items vi
        JOIN vouchers v ON vi.voucher_id = v.id
        WHERE DATE(v.created_at) = DATE(?)
        GROUP BY vi.test_name, vi.test_code
        ORDER BY qty_count DESC;
    """, (date_str,))
    test_breakdown = [dict(r) for r in cursor.fetchall()]
    conn.close()

    if not HAS_REPORTLAB:
        # Fallback HTML
        html_path = os.path.splitext(filepath)[0] + ".html"
        _build_daily_audit_html(date_str, summary, vouchers, test_breakdown, settings, html_path)
        return html_path

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm
    )

    styles = getSampleStyleSheet()

    style_title = ParagraphStyle("T", fontName="Helvetica-Bold", fontSize=16, leading=18, alignment=1, textColor=colors.HexColor("#0f766e"))
    style_sub = ParagraphStyle("S", fontName="Helvetica", fontSize=9, leading=11, alignment=1, textColor=colors.HexColor("#475569"))
    style_sec = ParagraphStyle("Sec", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=colors.HexColor("#0f172a"))
    style_th = ParagraphStyle("TH", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=colors.HexColor("#ffffff"), alignment=1)
    style_td = ParagraphStyle("TD", fontName="Helvetica", fontSize=8, leading=10, textColor=colors.HexColor("#1e293b"))
    style_td_r = ParagraphStyle("TDR", fontName="Helvetica", fontSize=8, leading=10, alignment=2, textColor=colors.HexColor("#1e293b"))
    style_kpi_num = ParagraphStyle("KPINum", fontName="Helvetica-Bold", fontSize=12, leading=14, alignment=1, textColor=colors.HexColor("#0f766e"))
    style_kpi_lbl = ParagraphStyle("KPILbl", fontName="Helvetica", fontSize=7, leading=9, alignment=1, textColor=colors.HexColor("#64748b"))

    story = []

    # Title Banner
    story.append(Paragraph(h_name.upper(), style_title))
    story.append(Paragraph(f"DAILY FINANCIAL AUDIT & REVENUE RECONCILIATION REPORT", style_sec))
    story.append(Paragraph(f"Audit Date: <b>{date_str}</b>  |  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", style_sub))
    story.append(Spacer(1, 4 * mm))

    # Executive KPI Summary Cards Table
    kpi_grid = [
        [
            Paragraph(f"<b>{summary['total_vouchers']}</b>", style_kpi_num),
            Paragraph(f"<b>{summary['total_tests']}</b>", style_kpi_num),
            Paragraph(f"<b>{curr} {summary['total_billed']:.2f}</b>", style_kpi_num),
            Paragraph(f"<b>{curr} {summary['total_discount']:.2f}</b>", style_kpi_num),
            Paragraph(f"<b><font color='#059669'>{curr} {summary['total_collected']:.2f}</font></b>", style_kpi_num),
            Paragraph(f"<b><font color='#dc2626'>{curr} {summary['total_due']:.2f}</font></b>", style_kpi_num),
        ],
        [
            Paragraph("Total Vouchers", style_kpi_lbl),
            Paragraph("Tests Conducted", style_kpi_lbl),
            Paragraph("Net Billed", style_kpi_lbl),
            Paragraph("Total Discounts", style_kpi_lbl),
            Paragraph("Cash Collected", style_kpi_lbl),
            Paragraph("Outstanding Due", style_kpi_lbl),
        ]
    ]
    kpi_table = Table(kpi_grid, colWidths=[30 * mm] * 6)
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 6 * mm))

    # Section 1: Top Diagnostic Tests Conducted
    story.append(Paragraph("1. Diagnostic Tests Performance & Volume", style_sec))
    story.append(Spacer(1, 2 * mm))

    test_table_data = [
        [
            Paragraph("#", style_th),
            Paragraph("Code", style_th),
            Paragraph("Diagnostic Test Name", style_th),
            Paragraph("Count", style_th),
            Paragraph(f"Total Revenue ({curr})", style_th),
        ]
    ]

    for idx, t in enumerate(test_breakdown[:12], 1):
        test_table_data.append([
            Paragraph(str(idx), style_td),
            Paragraph(str(t["test_code"]), style_td),
            Paragraph(str(t["test_name"]), style_td),
            Paragraph(str(t["qty_count"]), style_td),
            Paragraph(f"{float(t['total_rev']):.2f}", style_td_r),
        ])

    test_tbl = Table(test_table_data, colWidths=[10 * mm, 20 * mm, 90 * mm, 25 * mm, 35 * mm])
    test_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(test_tbl)
    story.append(Spacer(1, 6 * mm))

    # Section 2: Complete Itemized Billing Register
    story.append(Paragraph(f"2. Patient Billing Register ({len(vouchers)} Vouchers Issued)", style_sec))
    story.append(Spacer(1, 2 * mm))

    reg_data = [
        [
            Paragraph("Voucher #", style_th),
            Paragraph("Time", style_th),
            Paragraph("Patient Name", style_th),
            Paragraph("Phone", style_th),
            Paragraph(f"Billed", style_th),
            Paragraph(f"Paid", style_th),
            Paragraph(f"Due", style_th),
            Paragraph("Status", style_th),
        ]
    ]

    for v in vouchers:
        due_val = float(v["due_amount"])
        due_col = "#dc2626" if due_val > 0 else "#059669"
        reg_data.append([
            Paragraph(str(v["voucher_no"]), style_td),
            Paragraph(str(v["created_at"])[11:16], style_td),
            Paragraph(str(v["patient_name"])[:20], style_td),
            Paragraph(str(v["patient_phone"]), style_td),
            Paragraph(f"{float(v['total_amount']):.2f}", style_td_r),
            Paragraph(f"{float(v['paid_amount']):.2f}", style_td_r),
            Paragraph(f"<font color='{due_col}'>{due_val:.2f}</font>", style_td_r),
            Paragraph(str(v["payment_status"]), style_td),
        ])

    reg_tbl = Table(reg_data, colWidths=[32 * mm, 14 * mm, 42 * mm, 26 * mm, 18 * mm, 18 * mm, 18 * mm, 14 * mm])
    reg_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(reg_tbl)
    story.append(Spacer(1, 8 * mm))

    # Audit Sign-off Block
    sign_grid = [
        [
            Paragraph("____________________________<br/>Prepared By (Reception / Billing)", style_sub),
            Paragraph("____________________________<br/>Checked By (Chief Accountant)", style_sub),
            Paragraph("____________________________<br/>Approved By (Hospital Director)", style_sub),
        ]
    ]
    sign_table = Table(sign_grid, colWidths=[60 * mm, 60 * mm, 60 * mm])
    sign_table.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    story.append(KeepTogether(sign_table))

    doc.build(story)
    print(f"[PDFGenerator] Saved Daily Audit PDF: {filepath}")
    return filepath


# ==============================================================================
# HTML FALLBACK GENERATORS (Zero-Dependency Backup)
# ==============================================================================

def _build_voucher_html(voucher: dict, settings: dict) -> str:
    from printer_engine import generate_html_voucher
    return generate_html_voucher(voucher, settings)


def _build_daily_audit_html(date_str: str, summary: dict, vouchers: list, tests: list, settings: dict, output_path: str):
    h_name = settings.get("hospital_name", "City Care Diagnostic Center")
    curr = settings.get("currency_symbol", "Tk")

    rows = ""
    for v in vouchers:
        rows += f"""
        <tr>
            <td>{v['voucher_no']}</td>
            <td>{str(v['created_at'])[11:16]}</td>
            <td>{v['patient_name']}</td>
            <td>{v['patient_phone']}</td>
            <td style="text-align:right;">{float(v['total_amount']):.2f}</td>
            <td style="text-align:right;">{float(v['paid_amount']):.2f}</td>
            <td style="text-align:right; color:{'red' if float(v['due_amount'])>0 else 'green'};">{float(v['due_amount']):.2f}</td>
            <td style="text-align:center;">{v['payment_status']}</td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Daily Audit Report - {date_str}</title>
<style>
  body {{ font-family: Segoe UI, Arial, sans-serif; margin: 20px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 11px; }}
  th, td {{ border: 1px solid #ccc; padding: 4px 6px; }}
  th {{ background: #0f766e; color: white; }}
  .kpi {{ display: flex; gap: 10px; margin-bottom: 20px; }}
  .card {{ border: 1px solid #ddd; padding: 10px; flex: 1; text-align: center; background: #f8fafc; }}
</style>
</head>
<body>
  <h2>{h_name}</h2>
  <h3>Daily Financial Audit Report - {date_str}</h3>
  <div class="kpi">
    <div class="card"><strong>{summary['total_vouchers']}</strong><br>Vouchers</div>
    <div class="card"><strong>{summary['total_tests']}</strong><br>Tests</div>
    <div class="card"><strong>{curr} {summary['total_billed']:.2f}</strong><br>Billed</div>
    <div class="card"><strong>{curr} {summary['total_collected']:.2f}</strong><br>Collected</div>
    <div class="card"><strong>{curr} {summary['total_due']:.2f}</strong><br>Due</div>
  </div>
  <table>
    <thead>
      <tr><th>Voucher #</th><th>Time</th><th>Patient</th><th>Phone</th><th>Billed</th><th>Paid</th><th>Due</th><th>Status</th></tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
