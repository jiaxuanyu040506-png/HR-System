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
    """
    Build a one-page payslip PDF for a single employee/month and return
    it as raw bytes (ready to hand to st.download_button).

    `employee` must contain: name, employee_id, bank_account
    `payslip` must contain: month, basic_salary, allowance,
        epf_employee, epf_employer, socso_employee, socso_employer,
        skbbk, eis_employee, pcb, net_pay
    """
    pdf = FPDF()
    pdf.add_page()

    # ---------- Company header ----------
    pdf.set_font("Helvetica", "B", 13)
    pdf.multi_cell(0, 6, COMPANY_NAME, align="C")
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 5, COMPANY_ADDRESS, align="C")
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 5, COMPANY_CONTACT, align="C")
    pdf.set_x(pdf.l_margin)
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"MONTHLY SALARY - {payslip.get('month', '')}", ln=True, align="C")
    pdf.ln(2)

    # ---------- Employee info ----------
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(95, 6, f"Employee Name: {employee.get('name', '')}", ln=False)
    pdf.cell(95, 6, f"Staff No.: {employee.get('employee_id', '')}", ln=True)
    pdf.cell(95, 6, f"Salary Rate: RM {float(payslip.get('basic_salary', 0)):.2f}", ln=True)
    pdf.ln(3)

    # ---------- Income ----------
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "INCOME (RM)", ln=True)
    pdf.set_font("Helvetica", "", 10)
    basic = float(payslip.get("basic_salary", 0))
    allowance = float(payslip.get("allowance", 0))
    total_income = basic + allowance
    pdf.cell(0, 6, f"Basic Salary: RM {basic:.2f}", ln=True)
    pdf.cell(0, 6, f"Allowance: RM {allowance:.2f}", ln=True)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, f"Total Income: RM {total_income:.2f}", ln=True)
    pdf.ln(3)

    # ---------- Deductions table (matches the paper payslip layout) ----------
    epf_employee = float(payslip.get("epf_employee", 0))
    epf_employer = float(payslip.get("epf_employer", 0))
    socso_employee = float(payslip.get("socso_employee", 0))
    socso_employer = float(payslip.get("socso_employer", 0))
    skbbk = float(payslip.get("skbbk", 0))
    eis_employee = float(payslip.get("eis_employee", 0))
    pcb = float(payslip.get("pcb", 0))

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "DEDUCTIONS (RM)", ln=True)

    col_w = [28, 27, 27, 27, 27, 27]
    headers = ["", "EPF", "SOCSO", "BBK", "EIS", "PCB"]
    pdf.set_font("Helvetica", "B", 9)
    for w, h in zip(col_w, headers):
        pdf.cell(w, 7, h, border=1, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", "", 9)
    employee_row = ["P (Employee)", f"{epf_employee:.2f}", f"{socso_employee:.2f}",
                    f"{skbbk:.2f}", f"{eis_employee:.2f}", f"{pcb:.2f}"]
    for w, val in zip(col_w, employee_row):
        pdf.cell(w, 7, val, border=1, align="C")
    pdf.ln()

    employer_row = ["M (Employer)", f"{epf_employer:.2f}", f"{socso_employer:.2f}",
                    "-", "-", "-"]
    for w, val in zip(col_w, employer_row):
        pdf.cell(w, 7, val, border=1, align="C")
    pdf.ln(8)

    total_deduction = epf_employee + socso_employee + skbbk + eis_employee + pcb
    net_pay = float(payslip.get("net_pay", total_income - total_deduction))

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Total Deduction: RM {total_deduction:.2f}", ln=True)
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"TOTAL NET SALARY (RM): {net_pay:.2f}", ln=True)
    pdf.ln(4)

    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, f"Bank Account: {_mask_bank_account(employee.get('bank_account'))}", ln=True)

    output = pdf.output(dest="S")
    if isinstance(output, (bytes, bytearray)):
        return bytes(output)
    return output.encode("latin-1")
