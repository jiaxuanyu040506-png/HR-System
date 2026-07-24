"""
performance.py

Tracks which employee handled which company/client's work, whether it
was completed, and whether it was on time. Powers the "who did the
most" bar chart shown on both the HR Dashboard and Employee Dashboard.

Two tabs in the main HR_System_Database Google Sheet:

    Companies:
        company_name, category ("Private Limited" / "Normal Company"),
        company_type ("Sole Proprietor" / "Partnership" — only used
        when category is "Normal Company", blank otherwise)

    PerformanceRecords:
        record_id, company_name, employee_id, employee_name,
        due_date, completion_date, status
        (status is computed automatically: "Pending" if no completion
        date yet, "On Time" if completed on/before due_date, "Late"
        if completed after due_date)
"""
from __future__ import annotations

import uuid
import calendar
from datetime import date
import pandas as pd
from utils.sheets_client import read_table, append_row

CATEGORIES = ["Private Limited", "Normal Company"]
COMPANY_TYPES = ["Sole Proprietor", "Partnership"]


def get_companies() -> list[dict]:
    """All companies/clients on file, for the selectboxes."""
    df = read_table("Companies")
    if df.empty:
        return []
    return df.to_dict("records")


def add_company(company_name: str, category: str, company_type: str = ""):
    """Add a new company/client. company_type is ignored unless category is 'Normal Company'."""
    append_row("Companies", {
        "company_name": company_name,
        "category": category,
        "company_type": company_type if category == "Normal Company" else "",
    })


def submit_performance_record(company_name: str,
                               employee_id: str, employee_name: str,
                               due_date_: date, completion_date_: date | None):
                      
    """
    Log one piece of work. assigned_employee is who was SUPPOSED to do it;
    completed_employee is who ACTUALLY did it (can be someone else, e.g.
    a colleague who helped finish it). status is derived automatically:
      no completion date yet -> "Pending"
      completed on/before due_date -> "On Time"
      completed after due_date -> "Late"
    """

    today = date.today()
    if completion_date_:
        if completion_date_ <= due_date_:
            status = "On Time"
        else:
            status = "Late"
    else:
        if today > due_date_:
            status = "Late"
        else:
            status = "Pending"

    append_row("PerformanceRecords", {
        "record_id": f"PF{uuid.uuid4().hex[:8].upper()}",
        "company_name": company_name,
        "employee_id": employee_id,
        "employee_name": employee_name,
        "due_date": str(due_date_),
        "completion_date": str(completion_date_) if completion_date_ else "",
        "status": status,
    })


def get_completed_counts_by_employee() -> pd.DataFrame:
    """
    Number of COMPLETED tasks (On Time or Late — anything with a
    completion date) per employee. Indexed by employee name so it can
    be passed straight into st.bar_chart. Everyone sees this — it's
    meant to be visible on both HR and Employee dashboards.
    """
    df = read_table("PerformanceRecords")
    if df.empty:
        return pd.DataFrame({"Completed Tasks": []})
    completed = df[df["status"] != "Pending"]
    if completed.empty:
        return pd.DataFrame({"Completed Tasks": []})
    counts = completed.groupby("employee_name").size()
    counts.name = "Completed Tasks"
    return counts.to_frame()


def get_department_completed_count(department: str) -> int:
    """How many tasks were completed by anyone in a given department (e.g. 'Account')."""
    from utils.sheets_client import read_table as _read_table
    df = read_table("PerformanceRecords")
    employees = _read_table("Employees")
    if df.empty or employees.empty:
        return 0
    completed = df[df["status"] != "Pending"]
    dept_ids = set(employees[employees["department"] == department]["employee_id"].astype(str))
    return int(completed[completed["employee_id"].astype(str).isin(dept_ids)].shape[0])


def get_assigned_vs_completed() -> pd.DataFrame:
    """
    Per employee: how many tasks were ASSIGNED to them vs how many they
    ACTUALLY completed themselves. A gap between the two (e.g. assigned
    6, completed 3) means the rest were finished by someone else —
    visualized on the Performance page as a grouped bar chart.
    """
    df = read_table("PerformanceRecords")
    if df.empty:
        return pd.DataFrame()

    assigned_col = "assigned_employee_name" if "assigned_employee_name" in df.columns else "employee_name"
    # Old rows created before this field existed won't have it — treat those
    # as "assigned to whoever completed it" so they still count somewhere.
    assigned_series = df[assigned_col].fillna(df["employee_name"]) if assigned_col in df.columns else df["employee_name"]

    assigned_counts = assigned_series.value_counts()
    completed = df[df["status"] != "Pending"]
    completed_counts = completed["employee_name"].value_counts()

    all_names = sorted(set(assigned_counts.index) | set(completed_counts.index))
    if not all_names:
        return pd.DataFrame()

    return pd.DataFrame({
        "Assigned": [int(assigned_counts.get(n, 0)) for n in all_names],
        "Completed": [int(completed_counts.get(n, 0)) for n in all_names],
    }, index=all_names)

# Added 16 July
# Updated 24 July
def get_employee_company_list(employee_name):
    df = read_table("PerformanceRecords")
    if df.empty:
        return pd.DataFrame()
    result = df[
        df["employee_name"] == employee_name
    ].drop_duplicates(
        subset=["company_name"]
    )
    return result[
        [
            "company_name",
            "status",
            "due_date",
            "completion_date"
        ]
    ]

# Added 16 July
def get_all_performance_records():
    df = read_table("PerformanceRecords")
    if df.empty:
        return pd.DataFrame()
    return df

# Added 16 July
def delete_performance_record(record_id):
    from utils.sheets_client import delete_row
    df = read_table("PerformanceRecords")

    if df.empty:
        return False

    target = df[df["record_id"].astype(str) == str(record_id)]

    if target.empty:
        return False
    
    row = target.iloc[0].to_dict()
    delete_row("PerformanceRecords", {"record_id": row["record_id"]})
    return True

# Added 24 July, 2026
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

def calculate_due_date(company_type: str, year: int, year_end: str | None = None):
    """
    Calculate performance deadline.

    Normal Company:15 July every year

    Private Limited:Financial Year End + 5 months
    """

    if company_type == "Normal Company":
        return date(year, 7, 15)

    if company_type == "Private Limited":
        if not year_end:
            raise ValueError("Private Limited company requires year end.")

        # Example: 31-Jan
        day, month = year_end.split("-")
        day = int(day)
        month = MONTH_MAP[month]

        new_month = month + 5
        new_year = year

        if new_month > 12:
            new_month -= 12
            new_year += 1

        last_day = calendar.monthrange(new_year, new_month)[1]

        return date(new_year, new_month, min(day,last_day))

# Added 24 July, 2026
def get_employee_performance_summary(employee_name):
    """
    Returns:
        {
            "total": 10,
            "on_time": 8,
            "late": 2
        }
    """
    df = read_table("PerformanceRecords")

    if df.empty:
        return {
            "total": 0,
            "on_time": 0,
            "late": 0,
        }

    df = df[df["employee_name"] == employee_name]
    return {
        "total": len(df),
        "on_time": len(df[df["status"] == "On Time"]),
        "late": len(df[df["status"] == "Late"]),
    }

# Added 24 July, 2026
def get_employee_late_companies(employee_name):

    df = read_table("PerformanceRecords")
    if df.empty:
        return pd.DataFrame()

    late_df = df[(df["employee_name"] == employee_name) & (df["status"] == "Late")]
    if late_df.empty:
        return pd.DataFrame()

    return late_df[
        [
            "company_name",
            "due_date",
            "completion_date",
        ]
    ]