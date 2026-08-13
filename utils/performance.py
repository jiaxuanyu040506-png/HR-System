"""
performance.py

Tracks which employee handled which company/client's work,
whether it was completed, and whether it was on time.

Google Sheets:
Companies: company_name; category; company_type; year_end
PerformanceRecords: record_id; company_name; category; employee_id; employee_name; due_date; completion_date;status

Status:
    Pending  -> no completion date yet
    On Time  -> completed on or before due date
    Late     -> completed after due date
"""

from __future__ import annotations

import uuid
import calendar
from datetime import date

import pandas as pd

from utils.sheets_client import (
    read_table,
    append_row,
    update_row,
    delete_row,
)

# CONSTANTS
CATEGORIES = ["Private Limited", "Normal Company",]
COMPANY_TYPES = ["Sole Proprietor", "Partnership",]

MONTH_MAP = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}

# COMPANY MANAGEMENT
def get_companies() -> list[dict]:
    """
    Return all companies stored in the Companies sheet.
    """

    df = read_table("Companies")

    if df.empty:
        return []

    return df.to_dict("records")

def add_company(company_name: str, category: str, company_type: str = "", year_end: str = "",):
    """
    Add a new company/client.

    company_type is only relevant for Normal Company.

    year_end is mainly used for Private Limited.
    Example:
        31-Jan
    """

    append_row("Companies",
               {"company_name": company_name,
                "category": category,
                "company_type": (company_type if category == "Normal Company" else ""),
                "year_end": (year_end if category == "Private Limited" else ""),},)

# DUE DATE
def calculate_due_date(company_type: str, year: int, year_end: str | None = None,):
    """
    Calculate annual performance deadline.

    Normal Company:
        15 July every year

    Private Limited:
        Financial Year End + 5 months

    Example:
        Year End = 31-Jan
        Deadline = 30-Jun
    """

    if company_type == "Normal Company":
        return date(year, 7, 15)

    if company_type == "Private Limited":
        if not year_end:
            raise ValueError("Private Limited company requires year end.")

        # Support both: 31-Jan & 31 Jan
        year_end = str(year_end).strip()
        year_end = year_end.replace(" ", "-")

        day_str, month_str = year_end.split("-")
        day = int(day_str)

        month_str = month_str[:3].title()
        if month_str not in MONTH_MAP:
            raise ValueError(f"Invalid year end month: {month_str}")

        month = MONTH_MAP[month_str]
        new_month = month + 5
        new_year = year
        if new_month > 12:
            new_month -= 12
            new_year += 1

        last_day = calendar.monthrange(new_year,new_month,)[1]

        return date(new_year, new_month, min(day, last_day),)

    raise ValueError(f"Unknown company category: {company_type}")

# STATUS CALCULATION
def calculate_performance_status(due_date: date, completion_date: date | None,) -> str:
    """
    Calculate performance status.

    No completion date:
        Before/equal deadline -> Pending
        After deadline -> Late

    Has completion date:
        On/before deadline -> On Time
        After deadline -> Late
    """

    today = date.today()

    # Still not completed
    if completion_date is None:
        if today > due_date:
            return "Late"

        return "Pending"

    # Completed
    if completion_date <= due_date:
        return "On Time"

    return "Late"

# LOG PERFORMANCE RECORD
def submit_performance_record(company_name: str, category: str, employee_id: str, 
                              employee_name: str, due_date_: date, completion_date_: date | None = None,):
    """
    Create a performance record.

    completion_date_ can be None.

    This allows HR to record:

        Company + Employee
        ↓
        Pending

    and later update the record when the work is completed.
    """

    status = calculate_performance_status(due_date_, completion_date_,)
    append_row("PerformanceRecords",
               {"record_id": (f"PF{uuid.uuid4().hex[:8].upper()}"),
                "company_name": company_name,
                "category": category,
                "employee_id": employee_id,
                "employee_name": employee_name,
                "due_date": str(due_date_),
                "completion_date": (str(completion_date_) if completion_date_ else ""),
                "status": status,},)

# GET ALL PERFORMANCE RECORDS
def get_all_performance_records() -> pd.DataFrame:
    """
    Return all performance records.
    """

    df = read_table("PerformanceRecords")
    if df.empty:
        return pd.DataFrame()

    return df

# COMPLETED COUNTS
def get_completed_counts_by_employee() -> pd.DataFrame:
    """
    Number of completed tasks per employee.

    Completed means:
        On Time
        OR
        Late

    Pending is excluded.
    """

    df = read_table("PerformanceRecords")

    if df.empty:
        return pd.DataFrame({"Completed Tasks": []})

    completed = df[df["status"].isin(["On Time", "Late"])]
    if completed.empty:
        return pd.DataFrame({"Completed Tasks": []})

    counts = completed.groupby("employee_name").size()
    counts.name = "Completed Tasks"

    return counts.to_frame()

# DEPARTMENT COMPLETED COUNT
def get_department_completed_count(department: str,) -> int:
    """
    Return total completed performance records
    for a department.

    Pending records are excluded.
    """

    df = read_table("PerformanceRecords")
    employees = read_table("Employees")

    if df.empty or employees.empty:
        return 0

    completed = df[df["status"].isin(["On Time", "Late"])]
    dept_ids = set(employees[employees["department"] == department]["employee_id"].astype(str))

    return int(completed[completed["employee_id"].astype(str).isin(dept_ids)].shape[0])

# ASSIGNED VS COMPLETED
def get_assigned_vs_completed() -> pd.DataFrame:
    """
    Per employee:

        Assigned
        Completed

    Pending records are included in Assigned
    but excluded from Completed.
    """

    df = read_table("PerformanceRecords")

    if df.empty:
        return pd.DataFrame()

    assigned_col = ("assigned_employee_name" if "assigned_employee_name" in df.columns else "employee_name")
    if assigned_col in df.columns:
        assigned_series = (df[assigned_col].fillna(df["employee_name"]))
    else:
        assigned_series = df["employee_name"]

    assigned_counts = (assigned_series.value_counts())
    completed = df[df["status"].isin(["On Time", "Late"])]
    completed_counts = (completed["employee_name"].value_counts())

    all_names = sorted(set(assigned_counts.index)|set(completed_counts.index))
    if not all_names:
        return pd.DataFrame()

    return pd.DataFrame(
        {"Assigned": [int(assigned_counts.get(name,0,)) for name in all_names],
         "Completed": [int(completed_counts.get(name, 0,)) for name in all_names],
         }, index=all_names,)

# EMPLOYEE COMPANY LIST
def get_employee_company_list(employee_name: str,) -> pd.DataFrame:
    """
    Return companies assigned to an employee.

    Shows:

        company_name
        status
        due_date
        completion_date

    Status can be:

        Pending
        On Time
        Late
    """

    df = read_table("PerformanceRecords")

    if df.empty:
        return pd.DataFrame()

    result = df[df["employee_name"] == employee_name].copy()
    if result.empty:
        return pd.DataFrame()

    result = result.drop_duplicates(subset=["company_name"], keep="last",)
    columns = ["company_name", "status", "due_date", "completion_date",]
    existing_columns = [col for col in columns if col in result.columns]

    return result[existing_columns]

# EMPLOYEE PERFORMANCE SUMMARY
def get_employee_performance_summary(employee_name: str,):
    """
    Return employee performance summary.

    Important:

        total
            = completed companies

        on_time
            = completed on/before deadline

        late
            = completed after deadline

        pending
            = assigned but not completed yet

    Example:

        {
            "total": 10,
            "on_time": 8,
            "late": 2,
            "pending": 3
        }
    """

    df = read_table("PerformanceRecords")

    if df.empty:
        return {
            "total": 0,
            "on_time": 0,
            "late": 0,
            "pending": 0,
        }

    df = df[df["employee_name"] == employee_name].copy()
    if df.empty:
        return {
            "total": 0,
            "on_time": 0,
            "late": 0,
            "pending": 0,
        }

    on_time = len(df[df["status"] == "On Time"])
    late = len(df[df["status"] == "Late"])
    pending = len(df[df["status"] == "Pending"])

    # Total = completed companies
    total = on_time + late

    return {
        "total": total,
        "on_time": on_time,
        "late": late,
        "pending": pending,
    }

# EMPLOYEE LATE COMPANIES
def get_employee_late_companies(employee_name: str,) -> pd.DataFrame:
    """
    Return companies completed late
    by the selected employee.
    """

    df = read_table("PerformanceRecords")

    if df.empty:
        return pd.DataFrame()

    late_df = df[(df["employee_name"] == employee_name) & (df["status"] == "Late")].copy()
    if late_df.empty:
        return pd.DataFrame()

    columns = ["company_name", "due_date", "completion_date",]
    existing_columns = [col for col in columns if col in late_df.columns]

    return late_df[existing_columns]

# EMPLOYEE PENDING COMPANIES
def get_employee_pending_companies(employee_name: str,) -> pd.DataFrame:
    """
    Return companies assigned to an employee
    that are still pending.
    """

    df = read_table("PerformanceRecords")

    if df.empty:
        return pd.DataFrame()

    pending_df = df[(df["employee_name"] == employee_name) & (df["status"] == "Pending")].copy()
    if pending_df.empty:
        return pd.DataFrame()

    columns = ["company_name", "due_date", "completion_date",]
    existing_columns = [col for col in columns if col in pending_df.columns]

    return pending_df[existing_columns]

# DELETE PERFORMANCE RECORD
def delete_performance_record(record_id,) -> bool:
    """
    Permanently delete one performance record.
    """

    df = read_table("PerformanceRecords")

    if df.empty:
        return False

    target = df[df["record_id"].astype(str) == str(record_id)]
    if target.empty:
        return False

    row = target.iloc[0].to_dict()
    delete_row("PerformanceRecords",
               {"record_id": row["record_id"] },)
    return True

# UPDATE PERFORMANCE RECORD
def update_performance_record(record_id, company_name, category, employee_id,
                              employee_name, due_date, completion_date,):
    """
    Update an existing performance record.

    completion_date can be None / empty.

    Status is recalculated automatically.
    """

    try:
        # Convert empty values into None
        if completion_date in ["", None,]:
            completion_date_value = None
        elif isinstance(completion_date, date,):
            completion_date_value = completion_date
        else:
            completion_date_value = date.fromisoformat(str(completion_date))

        # Make sure due date is a date
        if not isinstance(due_date, date,):
            due_date = date.fromisoformat(str(due_date))

        status = calculate_performance_status(due_date, completion_date_value,)
        update_row("PerformanceRecords",
            {"record_id": record_id},
            {"company_name": company_name,
             "category": category,
             "employee_id": employee_id,
             "employee_name": employee_name,
             "due_date": str(due_date),
             "completion_date": (str(completion_date_value) if completion_date_value else ""),
             "status": status,
            },)
        return True

    except Exception as e:
        print("Failed to update performance record: " f"{e}")
        return False

# COMPANY COMPLETION / DUE DATE ROLLOVER
def is_company_completed_for_year(company_name: str, year: int) -> bool:
    """
    Check whether a company has already been completed
    for the specified year.

    A company is considered completed when it has a
    PerformanceRecords entry for that year with:

        On Time
        OR
        Late

    Pending does NOT count as completed.
    """

    df = read_table("PerformanceRecords")

    if df.empty:
        return False

    df = df[df["company_name"].astype(str).str.strip() == str(company_name).strip()].copy()
    if df.empty:
        return False

    # Convert due date to datetime
    df["due_date"] = pd.to_datetime(df["due_date"], errors="coerce")

    # Keep only records belonging to this year
    df = df[df["due_date"].dt.year == year]
    if df.empty:
        return False

    # Completed means On Time OR Late
    completed = df[df["status"].isin(["On Time", "Late"])]
    return not completed.empty

def get_due_date_with_completion_rollover(company_name: str, company_type: str, year: int, year_end: str | None = None) -> date:
    """
    Return the correct due date for a company.

    Example:

    Company A
    2026 due date = 15 Jul 2026

    If Company A has already been completed in 2026:
        -> return 15 Jul 2027

    If Company A has NOT been completed:
        -> return 15 Jul 2026

    The rollover only happens when the previous year's
    record has status "On Time" or "Late".
    """

    # First calculate this year's normal deadline
    current_due_date = calculate_due_date(company_type, year, year_end)

    # Only rollover if this year's requirement
    # has already been completed
    if is_company_completed_for_year(company_name,year):
        return calculate_due_date(company_type, year + 1, year_end)

    return current_due_date