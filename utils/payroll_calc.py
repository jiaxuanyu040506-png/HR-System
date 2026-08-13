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

SPECIAL_EPF_EMPLOYER_IDS = {"LH-LHY", "LH-QKC"}

def _epf_employer_column(employee_id: str) -> str:
    return "lhy_employer_amount" if employee_id in SPECIAL_EPF_EMPLOYER_IDS else "employer_amount"

def _skip_unpaid_leave_deduction(employee_id: str) -> bool:
    return employee_id == "LH-LHY"

def lookup_epf(basic_salary: float, age: int, employer_column: str = "employer_amount") -> dict:
    """
    Look up EPF employer/employee contribution amounts for a given
    basic salary, from the EPF tab (age < 60) or EPF_60 tab (age >= 60).

    Returns: {"employer": float, "employee": float}
    Raises ValueError if the salary falls outside the table's range.
    """
    tab_name = "EPF_60" if age >= 60 else "EPF"
    df = read_rate_table(tab_name)
    match = df[(df["salary_min"].astype(float) <= float(basic_salary)) & (df["salary_max"].astype(float) >= float(basic_salary))]
    if match.empty:
        raise ValueError(f"Salary RM{basic_salary} is outside the {tab_name} rate table range.")
    row = match.iloc[0]
    return {
        "employer": float(row[employer_column]),
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
        "eis_employer": float(row["eis_employer"]),
    }

# Updated 7 Aug, 2026 - Round payroll amounts so final cents are only 0 or 5
def round_to_nearest_five_cents(amount: float) -> float:
    amount = round(float(amount), 2)
    cents = int(round(amount * 100))
    remainder = cents % 5
    if remainder == 0:
        return float(cents / 100)
    if remainder < 5:
        cents -= remainder
    else:
        cents += 5 - remainder
    return float(cents / 100)

# Updated 7 Aug, 2026 - Use allowance wording for bonus and split red_packet separately
def calculate_payslip(employee_id: str, employee_name: str, month: str, basic_salary: float, allowance: float, date_of_birth: str,
                      pcb: float = 0.0, include_skbbk: bool = True, red_packet: float = 0.0, bik: float = 0.0, join_date: str | None = None,) -> dict:
    """
    Calculate a full payslip for one employee/month and save it
    to the Payslips sheet.

    If the payslip already exists for the same employee/month,
    the existing record will be updated instead of creating
    a duplicate.
    """

    # Normalize input values
    employee_id = str(employee_id).strip()
    employee_name = str(employee_name).strip()
    month = str(month).strip()

    basic_salary = float(basic_salary or 0)
    allowance = float(allowance or 0)
    red_packet = float(red_packet or 0)
    bik = float(bik or 0)
    pcb = float(pcb or 0)

    # Validate month
    try:
        year, month_num = map(int, month.split("-"))
        days_in_month = calendar.monthrange(year, month_num)[1]
    except (ValueError, TypeError):
        raise ValueError("Invalid month format. Please use YYYY-MM.")

    age = get_age(date_of_birth)                # Employee age

    # Unpaid Leave Deduction
    unpaid_days = 0.0
    if not _skip_unpaid_leave_deduction(employee_id):
        unpaid_days = get_unpaid_leave_days(employee_id, month,)
    if _skip_unpaid_leave_deduction(employee_id):
        unpaid_leave_deduction = 0.0
    else:
        unpaid_leave_deduction = round((basic_salary / days_in_month) * unpaid_days, 2,)

    # Pre-join Salary Deduction
    pre_join_days, pre_join_deduction = (get_pre_join_salary_deduction(basic_salary, month, join_date,))
    total_unpaid_days = (float(unpaid_days) + float(pre_join_days))
    total_unpaid_deduction = round(float(unpaid_leave_deduction) + float(pre_join_deduction), 2,)

    # Adjusted Basic Salary
    adjusted_basic_salary = round(basic_salary - total_unpaid_deduction, 2,)

    # Contribution Bases
    # Bonus is included in EPF base
    epf_base_salary = round(adjusted_basic_salary + allowance, 2,)

    # SOCSO / EIS use adjusted basic salary
    socso_base_salary = adjusted_basic_salary

    # Gross Salary
    gross_salary = round(adjusted_basic_salary + allowance + red_packet + bik, 2,)

    # EPF
    epf = lookup_epf(epf_base_salary, age, employer_column =_epf_employer_column(employee_id),)

    # SOCSO / EIS / SKBBK 
    socso_eis = lookup_socso_and_eis(socso_base_salary, age,)
    skbbk_employee = (socso_eis["skbbk"] if include_skbbk else 0.0)

    # Net Pay
    net_pay = round(gross_salary - epf["employee"] - socso_eis["socso_employee"] - skbbk_employee - socso_eis["eis_employee"] - pcb, 2,)
    net_pay = round_to_nearest_five_cents(net_pay)

    # Payslip ID
    payslip_id = (f"PS-{month}-{employee_id}")

    # Payslip Record
    record = {
        "payslip_id": payslip_id,
        "employee_id": employee_id,
        "employee_name": employee_name,
        "month": month,

        "basic_salary": basic_salary,
        "allowance": allowance,
        "red_packet": red_packet,
        "bik": bik,

        "unpaid_leave_days": total_unpaid_days,
        "unpaid_leave_deduction": total_unpaid_deduction,

        "pre_join_days": pre_join_days,
        "pre_join_deduction": pre_join_deduction,

        "gross_salary": gross_salary,

        "epf_employee": epf["employee"],
        "epf_employer": epf["employer"],

        "socso_employee": socso_eis["socso_employee"],
        "socso_employer": socso_eis["socso_employer"],

        "eis_employee": socso_eis["eis_employee"],
        "eis_employer": socso_eis["eis_employer"],

        "skbbk": skbbk_employee,
        "skbbk_status": ("Yes" if include_skbbk else "No"),

        "pcb": pcb,
        "net_pay": net_pay,
    }

    # INSERT or UPDATE
    existing = get_row("Payslips", {"payslip_id": payslip_id},)
    if existing:
        update_row("Payslips", {"payslip_id": payslip_id}, record,)
    else:
        append_row("Payslips", record,)

    return record

def preview_payslip(employee_id: str, basic_salary: float, month: str, allowance: float,
                    date_of_birth: str, pcb: float = 0.0, include_skbbk: bool = True,
                    red_packet: float = 0.0, bik: float = 0.0, join_date: str | None = None) -> dict:
    """
    Preview payroll calculation before saving.
    """
    age = get_age(date_of_birth)

    year, month_num = map(int, month.split("-"))
    days_in_month = calendar.monthrange(year, month_num)[1]
    unpaid_leave_days = get_unpaid_leave_days(employee_id, month)

    unpaid_leave_deduction = 0.0 if _skip_unpaid_leave_deduction(employee_id) else round((float(basic_salary) / days_in_month) * unpaid_leave_days, 2)

    pre_join_days, pre_join_deduction = get_pre_join_salary_deduction(basic_salary, month, join_date)
    total_unpaid_days = unpaid_leave_days + pre_join_days
    total_unpaid_deduction = round(unpaid_leave_deduction + pre_join_deduction, 2)

    adjusted_salary = round(float(basic_salary) - total_unpaid_deduction, 2)
    epf_base_salary = round(adjusted_salary + float(allowance), 2)
    socso_base_salary = adjusted_salary
    gross_salary = round(
        adjusted_salary
        + float(allowance)
        + float(red_packet)
        + float(bik),
        2,
    )

    epf = lookup_epf(epf_base_salary, age, employer_column=_epf_employer_column(employee_id),)
    socso_eis = lookup_socso_and_eis(socso_base_salary, age)
    skbbk = (socso_eis["skbbk"] if include_skbbk else 0.0)

    total_deduction = (
        epf["employee"]
        + socso_eis["socso_employee"]
        + skbbk
        + socso_eis["eis_employee"]
        + float(pcb)
    )
    net_pay = round(gross_salary - total_deduction, 2)
    net_pay = round_to_nearest_five_cents(net_pay)

    return {
        "unpaid_leave_days": total_unpaid_days,
        "unpaid_leave_deduction": total_unpaid_deduction,
        "pre_join_days": pre_join_days,
        "pre_join_deduction": pre_join_deduction,
        "basic_salary": basic_salary,
        "allowance": allowance,
        "red_packet": red_packet,
        "bik": float(bik),
        "gross_salary": gross_salary,
        "epf_employee": epf["employee"],
        "epf_employer": epf["employer"],
        "socso_employee": socso_eis["socso_employee"],
        "socso_employer": socso_eis["socso_employer"],
        "eis_employee": socso_eis["eis_employee"],
        "eis_employer": socso_eis["eis_employer"],
        "skbbk": skbbk,
        "pcb": float(pcb),
        "total_deduction": round(total_deduction, 2),
        "net_pay": net_pay,
    }

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

        if current.weekday() >= 5:
            continue

        if is_public_holiday(current):
            continue

        working_days += 1
    return working_days


def get_unpaid_leave_days(employee_id: str, month: str,) -> float:
    """
    Calculate approved unpaid leave days that fall within
    the specified payroll month.

    This prevents a multi-month unpaid leave request from
    being counted in full for both months.

    Example:

        29 Aug - 2 Sep
        Total leave = 5 calendar days

        August payroll -> 3 days
        September payroll -> 2 days

    The calculation is based on the actual dates inside
    the requested payroll month.
    """

    df = read_table("LeaveRequests")

    if df.empty:
        return 0.0

    required_columns = {"employee_id", "leave_type", "status", "start_date", "end_date",}
    if not required_columns.issubset(df.columns):
        return 0.0

    # Filter employee + approved unpaid leave
    df = df[(df["employee_id"].astype(str) == str(employee_id))
        & (df["leave_type"].astype(str).str.strip() == "Unpaid")
        & (df["status"].astype(str).str.strip() == "Approved")]

    if df.empty:
        return 0.0

    # Payroll month
    try:
        year, month_num = map(int, month.split("-"),)
    except (ValueError, TypeError):
        return 0.0

    month_start = date(year, month_num, 1,)
    days_in_month = calendar.monthrange( year, month_num,)[1]
    month_end = date( year, month_num, days_in_month,)

    # Calculate overlap with payroll month
    total = 0.0
    for _, row in df.iterrows():
        try:
            start = parse_date(row["start_date"])
            end = parse_date(row["end_date"])
        except Exception:
            continue

        # No overlap with this payroll month
        if end < month_start or start > month_end:
            continue

        # Actual overlapping dates
        overlap_start = max(start, month_start,)
        overlap_end = min(end, month_end,)

        if overlap_start > overlap_end:
            continue

        # Count calendar days within this month
        overlap_days = (overlap_end - overlap_start).days + 1
        total += overlap_days

    return float(total)

def get_pre_join_salary_deduction(basic_salary: float, month: str, join_date: str | None) -> tuple[float, float]:
    """
    If the employee joins in the middle of the payroll month,
    deduct the salary for the days before join date.
    """
    if not join_date:
        return 0.0, 0.0

    join = parse_date(join_date)
    year, month_num = map(int, month.split("-"))
    if join.year != year or join.month != month_num or join.day <= 1:
        return 0.0, 0.0

    days_in_month = calendar.monthrange(year, month_num)[1]
    pre_join_days = min(join.day - 1, days_in_month)
    daily_rate = float(basic_salary) / days_in_month
    pre_join_deduction = round(daily_rate * pre_join_days, 2)
    return float(pre_join_days), pre_join_deduction