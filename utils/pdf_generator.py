"""
pdf_generator.py

Generates the payslip PDF laid out to match the company's existing
paper payslip format (see the sample you provided): a deductions table
with separate Employer ("M") and Employee ("P") rows for EPF / SOCSO /
BBK / EIS / PCB.

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

COMPANY_NAME = "LIAN HENG MANAGEMENT (198703062228/JM 0102521-X)"
COMPANY_ADDRESS = "No. 16, Jalan Mengkudu, Taman Makmur, 83000 Batu Pahat, Johor Darul Takzim."
COMPANY_CONTACT = "Tel: 07-431 8833   Fax: 07-432 1222"


def _mask_bank_account(bank_account: str) -> str:
    """Show only the last 4 digits of a bank account number (e.g. ****7890)."""
    bank_account = str(bank_account or "")
    if not bank_account:
        return "-"
    return ("*" * max(len(bank_account) - 4, 0)) + bank_account[-4:]


def generate_payslip_pdf_bytes(employee: dict, payslip: dict) -> bytes:

    pdf = FPDF()
    pdf.add_page()

    # HEADER
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, COMPANY_NAME, ln=True, align="C")

    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, COMPANY_ADDRESS, ln=True, align="C")

    pdf.cell(0, 5, COMPANY_CONTACT, ln=True, align="C")

    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 5,
        "==============================================================",
        ln=True, align="C")

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, f"MONTHLY SALARY SLIP - {payslip.get('month','')}", ln=True, align="C")

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 5,
        "==============================================================",
        ln=True, align="C" )
    pdf.ln(5)

    # EMPLOYEE INFORMATION

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "EMPLOYEE INFORMATION", ln=True)

    pdf.set_font("Helvetica", "", 10)

    info = [("Employee Name",employee.get("name",""),
        "Staff No.", employee.get("employee_id","")),
        ("Bank Account", _mask_bank_account(employee.get("bank_account")),
            "Month",payslip.get("month",""))]

    for left, lv, right, rv in info:
        pdf.cell(45, 7, f"{left}:", border=1)
        pdf.cell(50, 7, str(lv), border=1)
        pdf.cell(45, 7, f"{right}:", border=1)
        pdf.cell(50, 7, str(rv), border=1)
        pdf.ln()
    pdf.ln(5)

    # INCOME
    basic = float(payslip.get("basic_salary",0))
    allowance = float(payslip.get("allowance",0))

    total_income = basic + allowance

    pdf.set_font("Helvetica","B",11)
    pdf.cell(0,7,
        "----------------------------------------------------------------- INCOME -----------------------------------------------------------------",
        ln=True)

    pdf.set_font("Helvetica","",10)
    pdf.cell(120,7,"Basic Salary")

    pdf.cell(50,7,f"RM {basic:.2f}", ln=True, align="R")
    pdf.cell(120, 7, "Allowance")
    pdf.cell(50, 7, f"RM {allowance:.2f}", ln=True, align="R")

    pdf.set_font("Helvetica","B",10)
    pdf.cell(120, 7, "TOTAL INCOME")
    pdf.cell(50, 7, f"RM {total_income:.2f}", ln=True, align="R")
    pdf.ln(5)

    # DEDUCTIONS
    epf_employee = float(payslip.get("epf_employee",0))
    epf_employer = float(payslip.get("epf_employer",0))

    socso_employee = float(payslip.get("socso_employee",0))
    socso_employer = float(payslip.get("socso_employer",0))

    skbbk = float(payslip.get("skbbk",0))
    eis = float(payslip.get("eis_employee",0))
    pcb = float(payslip.get("pcb",0))

    pdf.set_font("Helvetica", "B",11)
    pdf.cell(0, 7,
        "------------------------------------------------------------ DEDUCTIONS --------------------------------------------------------------",
        ln=True)

    pdf.set_font("Helvetica", "B", 9)
    headers=["Type", "EPF", "SOCSO", "BBK", "EIS", "PCB"]
    widths=[35, 30, 30, 30, 30, 30]

    for w,h in zip(widths,headers):
        pdf.cell(w, 7, h, border=1, align="C")

    pdf.ln()
    pdf.set_font("Helvetica", "", 9)

    rows=[["Employee", epf_employee, socso_employee, skbbk, eis, pcb],
        ["Employer", epf_employer, socso_employer, "-", "-", "-"]]

    for row in rows:
        for w,val in zip(widths,row):
            if isinstance(val,(int,float)):
                val=f"{val:.2f}"
            pdf.cell(w, 7, str(val), border=1, align="C")
        pdf.ln()

    total_deduction = (epf_employee + socso_employee + skbbk + eis + pcb)

    pdf.ln(5)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(120, 7, "Total Deduction")
    pdf.cell(50, 7, f"RM {total_deduction:.2f}", ln=True, align="R")
    pdf.ln(3)

    # NET PAY
    net_pay=float(payslip.get("net_pay", total_income-total_deduction))
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8,
        "============================================================================",
        ln=True, align="C")
    pdf.cell(120, 8, "NET SALARY")
    pdf.cell(50, 8, f"RM {net_pay:.2f}", ln=True, align="R")
    pdf.cell(0, 8,
        "============================================================================",
        ln=True, align="C")

    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(0, 5, "This payslip is system generated.", ln=True, align="C")

    output = pdf.output(dest="S")
    if isinstance(output,(bytes,bytearray)):
        return bytes(output)

    return output.encode("latin-1")
