"""
attendance.py

Daily attendance, per employee, per month.

Attendance status is derived automatically unless HR has manually
logged an attendance exception for that specific date.

Priority:

1. Employee has not joined yet              -> Not Joined (-)
2. Manual Attendance record exists          -> use manual status
3. Approved leave request covers that date  -> Leave Type
4. Public Holiday                           -> PH
5. Special Holiday                          -> SH
6. Rest Day (Saturday / Sunday)             -> Rest Day
7. Future working day                       -> Not Joined (-)
8. Normal working day                       -> Present (/)

Only manual attendance exceptions are stored in the Attendance sheet.

Attendance sheet:
    employee_id
    employee_name
    date
    status
    remarks

Holiday Management is stored separately in:

PublicHolidays sheet:
    date
    holiday_name
    holiday_type

holiday_type:
    Public Holiday
    Special Holiday
"""

from __future__ import annotations

import calendar as _calendar
from datetime import date

import pandas as pd

from utils.sheets_client import (
    read_table,
    append_row,
    update_row,
    delete_row,
    get_row,
)

from utils.leave_rules import (
    is_public_holiday,
    is_special_leave_day,
    is_rest_day,
    get_holiday_info,
)

from utils.date_utils import parse_date

# STATUS DEFINITIONS
# Manual statuses that HR can directly record.
MANUAL_STATUSES = ["Absent", "Late", "Half Day",]

# Display codes used in attendance matrix / Excel.
STATUS_CODES = {
    "Present": "/",
    "Absent": "A",
    "Late": "L",
    "Half Day": "HD",
    "Public Holiday": "PH",
    "Special Holiday": "SH",
    "Rest Day": "S",
    "Not Joined": "-",
}


# Leave type codes.
# These are used when an approved LeaveRequest covers a working day.
LEAVE_TYPE_CODES = {
    "Annual": "AL",
    "Medical": "MC",
    "Unpaid": "UPL",
    "Special": "SL",
    "Maternity": "ML",
    "Married": "MRL",
    "Hospitalization": "HL",
}

# Grey fill used by Attendance UI / Excel export.
REST_DAY_FILL = "D9D9D9"

# STATUS CODE CONVERSION
def get_status_code(status: str, remarks: str = "") -> str:
    """
    Convert a status + remarks pair into a short attendance code.

    Examples:

        Present            -> /
        Absent             -> A
        Late               -> L
        Half Day           -> HD
        Public Holiday     -> PH
        Special Holiday    -> SH
        Rest Day           -> S
        Annual Leave       -> AL
        Medical Leave      -> MC
    """

    status = str(status or "").strip()
    remarks = str(remarks or "").strip()

    # Already a leave code.
    if status in LEAVE_TYPE_CODES.values():
        return status

    # Old format:
    # status = "On Leave"
    # remarks = "Annual"
    if status == "On Leave":
        return LEAVE_TYPE_CODES.get(remarks, "OL")

    # Raw leave type.
    if status in LEAVE_TYPE_CODES:
        return LEAVE_TYPE_CODES[status]

    return STATUS_CODES.get(status, "-")

# MANUAL ATTENDANCE

def mark_attendance(employee_id: str, employee_name: str, day: date, 
                    status: str, remarks: str = "",):
    """
    Log a manual attendance exception for one day.

    If a record already exists for the employee/date,
    it will be overwritten.

    Typical statuses:
        Absent
        Late
        Half Day
    """

    existing = get_row("Attendance",
                       {"employee_id": employee_id, 
                        "date": str(day),},)
    record = {
        "employee_id": employee_id,
        "employee_name": employee_name,
        "date": str(day),
        "status": status,
        "remarks": remarks,}
    
    if existing:
        update_row("Attendance",
                   {"employee_id": employee_id,
                    "date": str(day),
                    }, record,)
    else:
        append_row("Attendance", record,)

def clear_attendance_override(employee_id: str, day: date,):
    """
    Remove a manual attendance record.

    After removing the override, the attendance status will
    automatically be recalculated from:

        Leave
        Holiday
        Rest Day
        Present
    """

    delete_row("Attendance",
               {"employee_id": employee_id,
                "date": str(day),
                },)

# APPROVED LEAVE
def _approved_leave_ranges(employee_id: str,) -> list[tuple[date, date, str]]:
    """
    Return all approved leave ranges for an employee.

    Returns:
        [
            (start_date, end_date, leave_type),
            ...
        ]
    """

    df = read_table("LeaveRequests")

    if df.empty:
        return []

    required_columns = {"employee_id", "status","start_date", "end_date", "leave_type",}
    if not required_columns.issubset(df.columns):
        return []

    mine = df[(df["employee_id"].astype(str) == str(employee_id)) & (df["status"].astype(str) == "Approved")]
    ranges = []

    for _, row in mine.iterrows():
        try:
            start_date = parse_date(row["start_date"])
            end_date = parse_date(row["end_date"])
        except Exception:
            continue

        leave_type = str(row.get("leave_type", "")).strip()
        ranges.append((start_date, end_date, leave_type,))
    return ranges

# EMPLOYEE JOIN DATE
def _get_employee_join_date(employee_id: str,) -> date | None:
    """
    Get employee join date from Employees sheet.
    """

    employee = get_row("Employees",{"employee_id": employee_id,},)
    if not employee:
        return None

    join_date_value = employee.get("join_date")
    if not join_date_value:
        return None

    try:
        return parse_date(join_date_value)
    except Exception:
        return None

# DAILY ATTENDANCE
def get_attendance_for_month(employee_id: str, employee_name: str, year: int, month: int,) -> list[dict]:
    """
    Generate attendance for every calendar day in a month.

    Priority:

    1. Before join date
    2. Manual attendance override
    3. Approved leave
    4. Public Holiday
    5. Special Holiday
    6. Rest Day
    7. Future working day
    8. Present

    Returns a list like:

        {
            "date": "2026-08-01",
            "status": "Present",
            "remarks": "",
            "source": "auto",
        }
    """

    join_date = _get_employee_join_date(employee_id)               # Employee join date

    # Manual attendance records
    manual_df = read_table("Attendance")
    manual_by_date = {}
    if not manual_df.empty:
        required_columns = {"employee_id", "date", "status",}
        if required_columns.issubset(manual_df.columns):
            mine = manual_df[manual_df["employee_id"].astype(str) == str(employee_id)]
            manual_by_date = {str(row["date"]): row for _, row in mine.iterrows()}

    # Approved leave ranges
    leave_ranges = _approved_leave_ranges(employee_id)

    # Month setup
    days_in_month = _calendar.monthrange(year, month,)[1]
    results = []

    # PROCESS EACH DAY
    for day_num in range(1, days_in_month + 1,):
        d = date(year, month, day_num,)
        d_str = str(d)

        # 1. NOT JOINED
        if join_date and d < join_date:
            results.append(
                {"date": d_str,
                 "status": "Not Joined",
                 "remarks": "",
                 "source": "auto",
                })
            continue

        # 2. MANUAL ATTENDANCE OVERRIDE
        if d_str in manual_by_date:
            row = manual_by_date[d_str]
            results.append(
                {"date": d_str,
                 "status": str(row.get("status", "")),
                 "remarks": str(row.get("remarks", "")),
                 "source": "manual",
                })
            continue

        # HOLIDAY INFORMATION
        holiday_info = get_holiday_info(d)
        public_holiday = (holiday_info is not None and holiday_info.get("type") == "Public Holiday")
        special_holiday = (holiday_info is not None and holiday_info.get("type") == "Special Holiday")

        # 3. APPROVED LEAVE
        on_leave_type = None
        for start, end, leave_type in leave_ranges:
            if start <= d <= end:
                on_leave_type = leave_type
                break

        # Approved leave only applies to normal working days.
        if (on_leave_type and not public_holiday and not special_holiday and not is_rest_day(d)):
            status = LEAVE_TYPE_CODES.get(on_leave_type, on_leave_type,)
            remarks = on_leave_type
            results.append(
                {"date": d_str,
                 "status": status,
                 "remarks": remarks,
                 "source": "leave",
                })
            continue

        # 4. PUBLIC HOLIDAY
        if public_holiday:
            status = "Public Holiday"
            remarks = (holiday_info.get("name", "",) if holiday_info else "")
            results.append(
                {"date": d_str,
                 "status": status,
                 "remarks": remarks,
                 "source": "holiday",
                })
            continue

        # 5. SPECIAL HOLIDAY
        if special_holiday:
            status = "Special Holiday"
            remarks = (holiday_info.get( "name", "",) if holiday_info else "")
            results.append(
                {"date": d_str,
                 "status": status,
                 "remarks": remarks,
                 "source": "holiday",
                })
            continue

        # 6. REST DAY
        if is_rest_day(d):
            results.append(
                {"date": d_str,
                 "status": "Rest Day",
                 "remarks": "",
                 "source": "auto",
                })
            continue

        # 7. FUTURE DATE
        if d > date.today():
            results.append(
                {"date": d_str,
                 "status": "Not Joined",
                 "remarks": "Future Date",
                 "source": "auto",
                })
            continue

        # 8. PRESENT
        results.append(
            {"date": d_str,
             "status": "Present",
             "remarks": "",
             "source": "auto",
            })
    return results

# MONTHLY SUMMARY
def get_monthly_summary(employee_id: str, employee_name: str, year: int, month: int,) -> dict:
    """
    Count attendance statuses for one month.

    Leave codes are excluded here because leave usage is calculated
    separately from LeaveRequests.
    """

    rows = get_attendance_for_month(employee_id, employee_name, year, month,)
    summary = {}
    leave_codes = set(LEAVE_TYPE_CODES.values())
    for row in rows:
        status = row["status"]

        # Leave is summarized separately.
        if status in leave_codes:
            continue

        summary[status] = (summary.get(status, 0) + 1)
    return summary

# YEARLY LEAVE SUMMARY
def get_yearly_leave_summary( employee_id: str, year: int,) -> dict:
    """
    Calculate approved leave usage for the year.

    Source:
        LeaveRequests

    Example:

        {
            "AL": 5,
            "MC": 2,
            "UPL": 1,
        }
    """

    requests = read_table("LeaveRequests")
    if requests.empty:
        return {}

    required_columns = {"employee_id", "status", "start_date", "end_date", "leave_type",}
    if not required_columns.issubset(requests.columns):
        return {}

    df = requests[(requests["employee_id"].astype(str) == str(employee_id)) & (requests["status"].astype(str) == "Approved")]
    if df.empty:
        return {}

    summary = {}
    for _, row in df.iterrows():
        try:
            start_date = parse_date(row["start_date"])
            end_date = parse_date(row["end_date"])

        except Exception:
            continue

        # Skip requests that don't overlap this year.
        if (start_date.year != year and end_date.year != year):
            continue

        leave_type = str(row.get("leave_type", "",)).strip()
        code = LEAVE_TYPE_CODES.get(leave_type, leave_type,)
        try:
            days = float(row.get("days", 0,) or 0)
        except Exception:
            days = 0.0

        summary[code] = (summary.get(code, 0) + days)
    return summary

# REST DAY COLUMNS
def get_rest_day_columns( year: int, month: int,) -> list[int]:
    """
    Return day numbers that are Saturday/Sunday.

    Used to grey out rest-day columns in the Attendance UI
    and Excel export.
    """

    days_in_month = _calendar.monthrange(year, month,)[1]
    return [d for d in range(1, days_in_month + 1,)
        if is_rest_day(date(year, month, d,))]

# ALL EMPLOYEES MONTHLY MATRIX
def get_attendance_matrix(year: int, month: int,):
    """
    Attendance grid for all employees.

    Rows:
        Employee

    Columns:
        1 ... 31

    Values:
        /, AL, MC, PH, SH, etc.
    """

    employees = read_table("Employees")
    if employees.empty:
        return pd.DataFrame()

    days_in_month = _calendar.monthrange(year, month,)[1]
    columns = list(range(1, days_in_month + 1,))

    data = {}
    for _, emp in employees.iterrows():
        employee_id = emp["employee_id"]
        employee_name = emp["name"]

        rows = get_attendance_for_month(employee_id, employee_name, year, month,)
        data[employee_name] = [get_status_code(row["status"], row.get("remarks", ""),) for row in rows]

    return pd.DataFrame.from_dict(data, orient="index", columns=columns,)

# FULL YEAR MATRICES
def get_attendance_matrices_for_year(year: int,) -> dict:
    """
    Return:

        {
            1: January matrix,
            2: February matrix,
            ...
            12: December matrix,
        }

    Used by full-year Excel export.
    """

    return {month: get_attendance_matrix(year, month,)
        for month in range(1, 13,)}

# INDIVIDUAL EMPLOYEE YEAR MATRIX
def get_attendance_matrix_for_employee_year(employee_id: str, employee_name: str, year: int,):
    """
    Attendance grid for ONE employee for the entire year.

    Rows:
        Jan
        Feb
        ...
        Dec

    Columns:
        1 ... 31
    """

    columns = list(range(1, 32,))
    data = {}

    for month in range(1, 13,):
        days_in_month = _calendar.monthrange(year, month,)[1]
        rows = get_attendance_for_month(employee_id, employee_name, year, month,)
        codes = [get_status_code(row["status"], row.get("remarks", ""),) for row in rows]

        # Pad shorter months.
        codes += [""] * (31 - days_in_month)
        month_label = _calendar.month_abbr[month]
        data[month_label] = codes

    return pd.DataFrame.from_dict(data, orient="index", columns=columns,)

# YEARLY SUMMARY
def get_yearly_summary(employee_id: str, employee_name: str,year: int,) -> dict:
    """
    Counts of attendance statuses across the whole year.

    Leave usage is then added from LeaveRequests.

    Example:

        {
            "Present": 210,
            "Public Holiday": 11,
            "Rest Day": 104,
            "AL": 5,
            "MC": 2,
        }
    """

    summary = {}

    for month in range(1, 13,):
        month_summary = get_monthly_summary(employee_id, employee_name, year, month,)

        for status, count in month_summary.items():
            summary[status] = (summary.get(status, 0) + count)

    # 2. Leave based
    leave_summary = get_yearly_leave_summary( employee_id, year,)
    for status, days in leave_summary.items():
        summary[status] = days
    return summary

# FULL YEAR FLATTENED ATTENDANCE
def get_attendance_for_year(employee_id: str, employee_name: str, year: int,) -> list[dict]:
    """
    Return every day of the year as a flat list.

    Used when HR needs to list or clear manual attendance
    exceptions across the whole year.
    """

    all_rows = []

    for month in range(1, 13,):
        all_rows.extend(get_attendance_for_month(employee_id, employee_name, year, month,))
    return all_rows