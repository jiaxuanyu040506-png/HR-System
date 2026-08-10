"""
pdf_generator.py

Generates the payslip PDF laid out to match the company's existing
paper payslip format: a deductions table with separate Employer ("M")
and Employee ("P") rows for EPF / SOCSO / BBK / EIS / PCB.

PAGE SIZE: half of A4 (210mm x 148.5mm) — so two payslips print on one
A4 sheet, cut/torn down the middle. Fonts and spacing are sized down to
fit comfortably on this smaller page while staying readable.

DESIGN DECISION: PDFs are generated IN MEMORY and returned as bytes,
never saved to local disk. If this app is deployed on Streamlit
Community Cloud, the local filesystem is wiped on every restart/redeploy
— anything saved to disk would eventually disappear. Since every number
needed to rebuild a payslip already lives in the Payslips sheet, we just
regenerate the PDF on demand whenever someone clicks "Download".

COMPANY DETAILS are hardcoded below (from your sample payslip) — edit
the COMPANY_* constants if the registered address/phone ever changes.
"""
from __future__ import annotations

from fpdf import FPDF

# Updated 7 Aug, 2026 - change layout & formatting to match the company's existing paper payslip format.
COMPANY_NAME = "LIAN HENG MANAGEMENT"
COMPANY_REGISTRATION = "Registration No.: 198703062228 / JM 0102521-X"
COMPANY_ADDRESS = "No. 16, Jalan Mengkudu, Taman Makmur, 83000 Batu Pahat, Johor Darul Takzim."
COMPANY_CONTACT = "Tel: 07-431 8833   Fax: 07-432 1222"

# Half of A4 (A4 is 210 x 297mm) — two payslips fit on one printed sheet.
PAGE_WIDTH = 210
PAGE_HEIGHT = 148.5
MARGIN = 10
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN


def _mask_bank_account(bank_account) -> str:
    """Show only the last 4 digits of a bank account number (e.g. ****7890)."""
    bank_account = str(bank_account or "")
    if not bank_account:
        return "-"
    return ("*" * max(len(bank_account) - 4, 0)) + bank_account[-4:]


def _rule(pdf: FPDF, weight: float = 0.3):
    """A clean horizontal line spanning the content width — replaces the
    old '====' / '----' text dividers with something that actually looks
    like a printed document rule."""
    pdf.set_draw_color(90, 90, 90)
    pdf.set_line_width(weight)
    y = pdf.get_y()
    pdf.line(MARGIN, y, PAGE_WIDTH - MARGIN, y)


def _section_header(pdf: FPDF, text: str):
    """Small shaded section label (INCOME / DEDUCTIONS) instead of an
    ASCII-art divider line."""
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(232, 232, 232)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(0, 5.5, f"  {text}", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(0.8)


def generate_payslip_pdf_bytes(employee: dict, payslip: dict) -> bytes:
    pdf = FPDF(orientation="P", unit="mm", format=(PAGE_WIDTH, PAGE_HEIGHT))
    pdf.set_margins(MARGIN, 8, MARGIN)
    pdf.set_auto_page_break(False)
    pdf.add_page()

    # ---------- Header ----------
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 5, COMPANY_NAME, ln=True, align="C")
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(0, 3.7, COMPANY_REGISTRATION, ln=True, align="C")
    pdf.cell(0, 3.7, COMPANY_ADDRESS, ln=True, align="C")
    pdf.cell(0, 3.7, COMPANY_CONTACT, ln=True, align="C")
    pdf.set_text_color(0, 0, 0)

    pdf.ln(1.5)
    _rule(pdf, 0.4)
    pdf.ln(1.8)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 5.5, f"PAYSLIP - {payslip.get('month', '')}", ln=True, align="C")
    pdf.ln(1.5)

    # ---------- Employee info ----------
    col_w = [26, CONTENT_WIDTH / 2 - 26, 26, CONTENT_WIDTH / 2 - 26]
    info_rows = [
        ("Name", employee.get("name", ""), "Staff No.", employee.get("employee_id", "")),
        ("I/C", employee.get("ic_no", ""), "Month", payslip.get("month", "")),
    ]
    for label1, val1, label2, val2 in info_rows:
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(col_w[0], 5, label1)
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(col_w[1], 5, str(val1))
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(col_w[2], 5, label2)
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(col_w[3], 5, str(val2), ln=True)
    pdf.ln(2)

    # ---------- Income ----------
    basic = float(payslip.get("basic_salary", 0))
    allowance = float(payslip.get("allowance", 0))       # allowance (treated as bonus-equivalent)
    # bonus = float(payslip.get("bonus", 0))               # explicit bonus if present
    red_packet = float(payslip.get("red_packet", 0))
    bik = float(payslip.get("bik", 0))
    total_income = basic + allowance + red_packet + bik

    _section_header(pdf, "INCOME")
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(CONTENT_WIDTH - 40, 5, "Basic Salary")
    pdf.cell(40, 5, f"RM {basic:,.2f}", align="R", ln=True)
    pdf.cell(CONTENT_WIDTH - 40, 5, "Bonus")
    pdf.cell(40, 5, f"RM {allowance:,.2f}", align="R", ln=True)
    # pdf.cell(CONTENT_WIDTH - 40, 5, "Bonus")
    # pdf.cell(40, 5, f"RM {bonus:,.2f}", align="R", ln=True)
    pdf.cell(CONTENT_WIDTH - 40, 5, "Red Packet")
    pdf.cell(40, 5, f"RM {red_packet:,.2f}", align="R", ln=True)
    pdf.cell(CONTENT_WIDTH - 40, 5, "BIK")
    pdf.cell(40, 5, f"RM {bik:,.2f}", align="R", ln=True)

    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(CONTENT_WIDTH - 40, 5.5, "Total Income", border="T")
    pdf.cell(40, 5.5, f"RM {total_income:,.2f}", border="T", align="R", ln=True)
    pdf.ln(2)

    # ---------- Deductions ----------
    epf_employee = float(payslip.get("epf_employee", 0))
    epf_employer = float(payslip.get("epf_employer", 0))
    socso_employee = float(payslip.get("socso_employee", 0))
    socso_employer = float(payslip.get("socso_employer", 0))
    skbbk = float(payslip.get("skbbk", 0))
    eis_employee = float(payslip.get("eis_employee", 0))
    eis_employer = float(payslip.get("eis_employer", 0))
    pcb = float(payslip.get("pcb", 0))

    _section_header(pdf, "DEDUCTIONS")

    headers = ["", "EPF", "SOCSO", "BBK", "EIS", "PCB"]
    label_w = 28
    other_w = (CONTENT_WIDTH - label_w) / 5
    widths = [label_w] + [other_w] * 5

    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_fill_color(248, 248, 248)
    pdf.set_draw_color(180, 180, 180)
    for w, h in zip(widths, headers):
        pdf.cell(w, 5, h, border=1, align="C", fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 7.5)
    rows = [
        ["Employee", epf_employee, socso_employee, skbbk, eis_employee, pcb],
        ["Employer", epf_employer, socso_employer, "-", eis_employer, "-"],
    ]
    for row in rows:
        for w, val in zip(widths, row):
            text = f"{val:,.2f}" if isinstance(val, (int, float)) else str(val)
            pdf.cell(w, 5, text, border=1, align="C")
        pdf.ln()

    total_deduction = epf_employee + socso_employee + skbbk + eis_employee + pcb
    pdf.ln(1.5)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(CONTENT_WIDTH - 40, 5, "Total Deduction")
    pdf.cell(40, 5, f"RM {total_deduction:,.2f}", align="R", ln=True)
    pdf.ln(2)

    # ---------- Net pay ----------
    net_pay = float(payslip.get("net_pay", total_income - total_deduction))
    _rule(pdf, 0.5)
    pdf.ln(1.8)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(CONTENT_WIDTH - 45, 7, "NET SALARY")
    pdf.cell(45, 7, f"RM {net_pay:,.2f}", align="R", ln=True)
    _rule(pdf, 0.5)

    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 6.5)
    pdf.set_text_color(130, 130, 130)
    pdf.cell(0, 4, "This payslip is system generated and does not require a signature.", align="C")

    output = pdf.output(dest="S")
    if isinstance(output, (bytes, bytearray)):
        return bytes(output)
    
    return output.encode("latin-1")

