"""
payroll_calc.py

Calculates statutory deductions (EPF, SOCSO, SKBBK, EIS) by looking up
the official rate tables, and writes the final computed numbers into the
Payslips sheet — never a formula, so historical payslips stay correct
even if the rate tables are updated later.

RATE TABLE SOURCE: the "SOCSO_EPF_RateConfig" Google Sheet, with 3 tabs
that must use these CLEANED column names (see the *_cleaned.csv files
provided alongside this code):

    EPF tab / EPF_60 tab:
        salary_min, salary_max, employer_amount, employee_amount

    SOCSO tab:
        salary_min, salary_max,
        cat1_employer, cat1_employee_keilatan, cat1_employee_skbbk,
        cat2_employer, cat2_employee_skbbk,
        eis_employer, eis_employee

    "Category 1" (cat1_*) applies to employees under 60.
    "Category 2" (cat2_*) applies to employees 60 and above — it has no
    "Keilatan" (invalidity) portion, only the SKBBK portion.
    EIS contributions stop once an employee reaches 60 (per LHDN/PERKESO
    rules), so eis_employee is forced to 0 for age >= 60.

PCB (monthly income tax deduction) is NOT auto-calculated here — see the
note above calculate_payslip() for why. HR enters this figure manually
after computing it on LHDN's official e-PCB calculator.
"""
from __future__ import annotations

from datetime import date
import calendar
from utils.sheets_client import read_rate_table, append_row, update_row, get_row, read_table
from utils.date_utils import parse_date
from utils.leave_rules import is_public_holiday

def get_age(date_of_birth: str) -> int:
    """
    Calculate an employee's current age in whole years from their
    date_of_birth string (format: YYYY-MM-DD, as stored in the
    Employees sheet). Used to decide EPF vs EPF_60, and SOCSO
    Category 1 vs Category 2.
    """
    dob = date.fromisoformat(str(date_of_birth))
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def lookup_epf(basic_salary: float, age: int) -> dict:
    """
    Look up EPF employer/employee contribution amounts for a given
    basic salary, from the EPF tab (age < 60) or EPF_60 tab (age >= 60).

    Returns: {"employer": float, "employee": float}
    Raises ValueError if the salary falls outside the table's range.
    """
    tab_name = "EPF_60" if age >= 60 else "EPF"
    df = read_rate_table(tab_name)
    match = df[
        (df["salary_min"].astype(float) <= float(basic_salary)) &
        (df["salary_max"].astype(float) >= float(basic_salary))
    ]
    if match.empty:
        raise ValueError(f"Salary RM{basic_salary} is outside the {tab_name} rate table range.")
    row = match.iloc[0]
    return {
        "employer": float(row["employer_amount"]),
        "employee": float(row["employee_amount"]),
    }


def lookup_socso_and_eis(basic_salary: float, age: int) -> dict:
    """
    Look up SOCSO (split into the "SOCSO" and "SKBBK" lines used on the
    company's payslip template) and EIS contribution amounts, from the
    single SOCSO tab, for a given basic salary and age.

    Category 1 (age < 60) has two employee-side sub-components:
      - "Keilatan" (invalidity)         -> shown as the "SOCSO" line
      - "Bukan Bencana Kerja" (SKBBK)    -> shown as the "BBK" line
    Category 2 (age >= 60) only has the SKBBK sub-component; there is
    no separate "SOCSO" (Keilatan) employee amount for this age group.

    Returns:
        {
            "socso_employee": float,   # Keilatan portion (0 for age >= 60)
            "socso_employer": float,   # full employer SOCSO contribution
            "skbbk": float,            # employee's SKBBK portion
            "eis_employee": float,     # 0 once age >= 60
        }
    Raises ValueError if the salary falls outside the table's range.
    """
    df = read_rate_table("SOCSO")
    match = df[
        (df["salary_min"].astype(float) <= float(basic_salary)) &
        (df["salary_max"].astype(float) >= float(basic_salary))
    ]
    if match.empty:
        raise ValueError(f"Salary RM{basic_salary} is outside the SOCSO rate table range.")
    row = match.iloc[0]

    if age >= 60:
        socso_employee = 0.0
        socso_employer = float(row["cat2_employer"])
        skbbk = float(row["cat2_employee_skbbk"])
        eis_employee = 0.0  # EIS stops at age 60
    else:
        socso_employee = float(row["cat1_employee_keilatan"])
        socso_employer = float(row["cat1_employer"])
        skbbk = float(row["cat1_employee_skbbk"])
        eis_employee = float(row["eis_employee"])

    return {
        "socso_employee": socso_employee,
        "socso_employer": socso_employer,
        "skbbk": skbbk,
        "eis_employee": eis_employee,
    }


def calculate_payslip(employee_id: str, employee_name: str, month: str, basic_salary: float,
                       allowance: float, date_of_birth: str, pcb: float = 0.0,  include_skbbk: bool = True,) -> dict:
    """
    Calculate a full payslip for one employee/month and save it to the
    Payslips sheet. This is the single function pages/3_Payslip_Management.py
    should call.

    EPF, SOCSO, SKBBK, EIS are all auto-calculated from the rate tables.
    PCB is NOT auto-calculated (see module docstring) — pass in the
    figure HR has already worked out via LHDN's e-PCB calculator.
    If you don't have it yet, leave pcb=0.0 and update the row later.

    net_pay = basic_salary + allowance
              - epf_employee - socso_employee - skbbk - eis_employee - pcb

    Returns the full payslip record (dict) that was written to the sheet.
    """
    age = get_age(date_of_birth)

    # 1. Unpaid Leave deduction
    # working_days = get_working_days(month)
    # unpaid_days = get_unpaid_leave_days(employee_id, month)

    # if working_days > 0:
    #     daily_rate = (float(basic_salary) / month)
    #     unpaid_leave_deduction = round(daily_rate * unpaid_days, 2)
    # else:
    #     unpaid_leave_deduction = 0.0

    year, month_num = map(int, month.split("-"))
    days_in_month = calendar.monthrange(year, month_num)[1]
    unpaid_days = get_unpaid_leave_days(employee_id, month)

    daily_rate = float(basic_salary) / days_in_month
    unpaid_leave_deduction = round(daily_rate * unpaid_days, 2)

    adjusted_basic_salary = round( float(basic_salary) - unpaid_leave_deduction, 2)

    # 2. Statutory calculation
    epf = lookup_epf(adjusted_basic_salary, age)
    socso_eis = lookup_socso_and_eis(adjusted_basic_salary, age)
    skbbk_employee = (socso_eis["skbbk"] if include_skbbk else 0.0)

    # 3. Salary calculation
    gross_salary = round(adjusted_basic_salary + float(allowance), 2)
    net_pay = round(
        gross_salary
        - epf["employee"]
        - socso_eis["socso_employee"]
        - skbbk_employee
        - socso_eis["eis_employee"]
        - float(pcb),
        2,
    )

    payslip_id = f"PS-{month}-{employee_id}"
    record = {
        "payslip_id": payslip_id,
        "employee_id": employee_id,
        "employee_name": employee_name,
        "month": month,
        "basic_salary": basic_salary,
        "allowance": allowance,
        # "working_days": working_days,
        "unpaid_leave_days": unpaid_days,
        "unpaid_leave_deduction": unpaid_leave_deduction,
        "gross_salary": gross_salary,
        "epf_employee": epf["employee"],
        "epf_employer": epf["employer"],
        "socso_employee": socso_eis["socso_employee"],
        "socso_employer": socso_eis["socso_employer"],
        "eis_employee": socso_eis["eis_employee"],
        "skbbk": skbbk_employee,
        "skbbk_status": "Yes" if include_skbbk else "No",
        "pcb": pcb,
        "net_pay": net_pay,
    }

    # Upsert: if a payslip for this employee+month already exists (e.g. you're
    # re-testing different pay amounts), overwrite it instead of appending a
    # duplicate row — duplicates were exactly what caused the earlier
    # "duplicate key" error on the download buttons.
    existing = get_row("Payslips", {"payslip_id": payslip_id})
    if existing:
        update_row("Payslips", {"payslip_id": payslip_id}, record)
    else:
        append_row("Payslips", record)
    return record

def preview_payslip(employee_id: str, basic_salary: float, month: str, allowance: float, date_of_birth: str, 
                    pcb: float = 0.0, include_skbbk: bool = True,) -> dict:
    """
    Preview payroll calculation before saving.

    Does NOT write anything into Google Sheet.
    Used for HR confirmation before generating payslip.
    """

    age = get_age(date_of_birth)

    year, month_num = map(int, month.split("-"))
    days_in_month = calendar.monthrange(year, month_num)[1]
    unpaid_leave_days = get_unpaid_leave_days(employee_id, month)

    daily_rate = float(basic_salary) / days_in_month
    unpaid_leave_deduction = round(daily_rate * unpaid_leave_days, 2)

    adjusted_salary = round(float(basic_salary) - unpaid_leave_deduction, 2)

    # Statutory
    epf = lookup_epf(adjusted_salary, age)                         # EPF
    socso_eis = lookup_socso_and_eis(adjusted_salary, age)         # SOCSO + EIS + SKBBK
    skbbk = (socso_eis["skbbk"] if include_skbbk else 0.0)      # SKBBK

    gross_salary = (adjusted_salary + float(allowance))
    total_deduction = (epf["employee"] + socso_eis["socso_employee"] + skbbk + socso_eis["eis_employee"] + float(pcb))
    net_pay = round(gross_salary - total_deduction, 2)

    return {
        # "working_days": working_days,
        "unpaid_leave_days": unpaid_leave_days,
        "unpaid_leave_deduction":unpaid_leave_deduction,
        "basic_salary": basic_salary,
        "allowance": allowance,
        "gross_salary": round(gross_salary, 2),
        "epf_employee": epf["employee"],
        "epf_employer": epf["employer"],
        "socso_employee": socso_eis["socso_employee"],
        "socso_employer": socso_eis["socso_employer"],
        "skbbk": skbbk,
        "eis_employee": socso_eis["eis_employee"],
        "pcb": float(pcb),
        "total_deduction": round(total_deduction,2),
        "net_pay": net_pay,
    }

# Calculate working days
def get_working_days(month: str) -> int:
    """
    Calculate working days for payroll month.

    Exclude:
    - Saturday
    - Sunday
    - Public Holiday

    month format:
    YYYY-MM
    """

    year, mon = map(int, month.split("-"))
    total_days = calendar.monthrange(year, mon)[1]
    working_days = 0

    for day in range(1, total_days + 1):
        current = date(year, mon, day)

        # weekend
        if current.weekday() >= 5:
            continue

        # public holiday
        if is_public_holiday(current):
            continue

        working_days += 1
    return working_days

def get_unpaid_leave_days(employee_id: str,month: str) -> float:
    df = read_table("LeaveRequests")

    if df.empty:
        return 0.0

    df = df[(df["employee_id"] == employee_id) & (df["leave_type"] == "Unpaid") & (df["status"] == "Approved")]
    if df.empty:
        return 0.0

    total = 0.0
    for _, row in df.iterrows():
        start = parse_date(row["start_date"])
        end = parse_date(row["end_date"])

        # only count leave inside this payroll month
        if (start.strftime("%Y-%m") == month or end.strftime("%Y-%m") == month):
            total += float(row.get("days",0))

    return total