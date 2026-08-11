"""
attendance.py

Daily attendance, per employee, per month. Instead of requiring HR to
manually mark every single day for every employee (20 people x 30 days
x 12 months — nobody would keep that up), each day's status is DERIVED
automatically unless HR has logged an exception for that specific date:

    1. A manual Attendance record exists for that date -> use it
       (this is how Absent / Late / Half Day get recorded)
    2. An Approved leave request covers that date        -> "On Leave"
    3. It's a public holiday (leave_rules.py)             -> "Public Holiday"
    4. It's a rest day, i.e. Sat/Sun (leave_rules.py)      -> "Rest Day"
    5. Otherwise                                           -> "Present"

Only exceptions (step 1) are stored in the Attendance sheet tab:
    employee_id, employee_name, date, status, remarks
"""
from __future__ import annotations

import calendar as _calendar
from datetime import date
from utils.sheets_client import read_table, append_row, update_row, delete_row, get_row
from utils.leave_rules import is_public_holiday, is_rest_day
from utils.date_utils import parse_date

MANUAL_STATUSES = ["Absent", "Late", "Half Day"]

# Present now uses "/" (matches your latest scheme) — Absent had to move
# off "/" to avoid clashing with it, so it's "A" instead. Each LEAVE TYPE
# gets its own code (not one generic "On Leave" symbol) so HR can tell at
# a glance what kind of leave it was. Rest Day still has no symbol — it's
# a grey column instead (see get_rest_day_columns / excel_export.py).
STATUS_CODES = {
    "Present": "/",
    "Absent": "A",
    "Late": "L",
    "Half Day": "HD",
    "Public Holiday": "PH",
    "Rest Day": "S",
    "Not Joined": "-",
}

# One code per leave type, used when a day's status is "On Leave" (the
# actual leave_type is stored in that day's `remarks`). "Married" was
# added here since it showed up in your legend — also added to
# leave_calc.LEAVE_TYPES so it's selectable when applying leave.
LEAVE_TYPE_CODES = {
    "Annual": "AL",
    "Medical": "MC",
    "Unpaid": "UPL",
    "Special": "SL",
    "Maternity": "ML",
    "Married": "MRL",
    "Hospitalization": "HL",
}


def get_status_code(status: str, remarks: str = "") -> str:
    """Single place that turns a (status, remarks) pair into its display
    code — used by both the on-screen grid and the Excel export so they
    never drift apart."""
    # if status == "On Leave":
    #     return LEAVE_TYPE_CODES.get(remarks, "OL")
    # return STATUS_CODES.get(status, "?")
    # Already converted code
    if status in LEAVE_TYPE_CODES.values():
        return status

    # Old format: On Leave + remarks
    if status == "On Leave":
        return LEAVE_TYPE_CODES.get(remarks, "OL")

    # Raw leave type
    if status in LEAVE_TYPE_CODES:
        return LEAVE_TYPE_CODES[status]

    return STATUS_CODES.get(status, "-")

REST_DAY_FILL = "D9D9D9"  # grey, used for both the on-screen Styler and the Excel export


def mark_attendance(employee_id: str, employee_name: str, day: date, status: str, remarks: str = ""):
    """Log a manual exception for one day. Overwrites any existing entry for that date."""
    existing = get_row("Attendance", {"employee_id": employee_id, "date": str(day)})
    record = {
        "employee_id": employee_id,
        "employee_name": employee_name,
        "date": str(day),
        "status": status,
        "remarks": remarks,
    }
    if existing:
        update_row("Attendance", {"employee_id": employee_id, "date": str(day)}, record)
    else:
        append_row("Attendance", record)


def clear_attendance_override(employee_id: str, day: date):
    """Remove a manual exception, reverting that date back to auto-derived status."""
    delete_row("Attendance", {"employee_id": employee_id, "date": str(day)})


def _approved_leave_ranges(employee_id: str) -> list[tuple[date, date, str]]:
    df = read_table("LeaveRequests")
    if df.empty:
        return []
    mine = df[(df["employee_id"] == employee_id) & (df["status"] == "Approved")]
    ranges = []
    for _, row in mine.iterrows():
        try:
            ranges.append((parse_date(row["start_date"]), parse_date(row["end_date"]), row["leave_type"]))
        except ValueError:
            continue
    return ranges


def get_attendance_for_month(employee_id: str, employee_name: str, year: int, month: int) -> list[dict]:
    """
    One row per calendar day in the given month.

    Priority:
    1. Before join date          -> Not Joined (-)
    2. Manual attendance record  -> use manual status
    3. Approved leave            -> AL / MC / UPL / etc.
    4. Public holiday            -> PH
    5. Rest day                  -> S
    6. Normal working day        -> Present (/)
    """

    # Employee join date
    employee = get_row("Employees",{"employee_id": employee_id})
    join_date = None
    if employee and employee.get("join_date"):
        try:
            join_date = parse_date(employee["join_date"])
        except Exception:
            join_date = None

    # Manual attendance override
    manual_df = read_table("Attendance")
    manual_by_date = {}
    if not manual_df.empty:
        mine = manual_df[manual_df["employee_id"] == employee_id]
        manual_by_date = {row["date"]: row for _, row in mine.iterrows()}

    # Approved leave ranges
    leave_ranges = _approved_leave_ranges(employee_id)

    days_in_month = _calendar.monthrange(year, month)[1]
    results = []
    for day_num in range(1, days_in_month + 1):
        d = date(year, month, day_num)
        d_str = str(d)

        # Not joined yet
        if join_date and d < join_date:
            results.append({
                "date": d_str, "status": "Not Joined",
                "remarks": "", "source": "auto",
            })
            continue
        
        # Manual override
        if d_str in manual_by_date:
            row = manual_by_date[d_str]
            results.append({
                "date": d_str, "status": row["status"],
                "remarks": row.get("remarks", ""), "source": "manual",
            })
            continue

        # Approved leave
        on_leave_type = None
        for start, end, leave_type in leave_ranges:
            if start <= d <= end:
                on_leave_type = leave_type
                break

        if on_leave_type and not is_public_holiday(d) and not is_rest_day(d):
            status = LEAVE_TYPE_CODES.get(on_leave_type, on_leave_type)
            remarks = on_leave_type
        elif is_public_holiday(d):
            status, remarks = "Public Holiday", ""
        elif is_rest_day(d):
            status, remarks = "Rest Day", ""
        elif d > date.today():
            status = "Not Joined"
            remarks = "Future Date"
        else:
            status, remarks = "Present", ""

        results.append({"date": d_str, "status": status, "remarks": remarks, "source": "auto"})

    return results


def get_monthly_summary(employee_id: str, employee_name: str, year: int, month: int) -> dict:
    """Counts of each status for the month — for a quick summary card/table."""
    rows = get_attendance_for_month(employee_id, employee_name, year, month)
    # summary: dict[str, int] = {}
    # for row in rows:
    #     summary[row["status"]] = summary.get(row["status"], 0) + 1
    # return summary
    summary = {}
    for row in rows:
        status = row["status"]

        # Leave type will be calculated from LeaveRequests
        if status in ["AL","MC","UPL","SL","ML","MRL","HPL"]:
            continue

        summary[status] = (summary.get(status, 0)+ 1)
    return summary

def get_yearly_leave_summary(employee_id: str,year: int) -> dict:
    """
    Calculate approved leave usage.
    Same source as LeaveBalance.
    """
    requests = read_table("LeaveRequests")
    if requests.empty:
        return {}

    df = requests[(requests["employee_id"] == employee_id)&(requests["status"] == "Approved")]
    if df.empty:
        return {}

    summary = {}

    for _, row in df.iterrows():
        start_date = parse_date(row["start_date"])
        end_date = parse_date(row["end_date"])

        # skip other years
        if (start_date.year != year and end_date.year != year):
            continue

        leave_type = row["leave_type"]
        code = LEAVE_TYPE_CODES.get(leave_type,leave_type)
        days = float(row.get("days", 0))

        summary[code] = (summary.get(code, 0) +days)
    return summary


def get_rest_day_columns(year: int, month: int) -> list[int]:
    """Day numbers (1-31) in this month that are rest days (Sat/Sun) —
    used to grey out those columns in the grid, since Rest Day has no
    text symbol of its own."""
    days_in_month = _calendar.monthrange(year, month)[1]
    return [d for d in range(1, days_in_month + 1) if is_rest_day(date(year, month, d))]


def get_attendance_matrix(year: int, month: int):
    """
    Grid view: one row per employee, one column per day of the month,
    values are short status codes. Used for the Monthly Overview (all
    employees) and for Excel export.
    """
    import pandas as pd
    employees = read_table("Employees")
    if employees.empty:
        return pd.DataFrame()

    days_in_month = _calendar.monthrange(year, month)[1]
    columns = list(range(1, days_in_month + 1))

    data = {}
    for _, emp in employees.iterrows():
        rows = get_attendance_for_month(emp["employee_id"], emp["name"], year, month)
        data[emp["name"]] = [get_status_code(r["status"], r["remarks"]) for r in rows]

    return pd.DataFrame.from_dict(data, orient="index", columns=columns)


def get_attendance_matrices_for_year(year: int) -> dict:
    """{month_number: matrix_dataframe} for all 12 months — used for the
    full-year Excel export (one sheet per month)."""
    return {month: get_attendance_matrix(year, month) for month in range(1, 13)}


def get_attendance_matrix_for_employee_year(employee_id: str, employee_name: str, year: int):
    """
    Grid view for ONE employee across the WHOLE year: one row per month
    (Jan-Dec), one column per day (1-31). Short months just have blank
    cells for days that don't exist (e.g. Feb 30). Used for the
    'Individual Employee' view, which shows a full year at a glance.
    """
    import pandas as pd
    columns = list(range(1, 32))
    data = {}
    for month in range(1, 13):
        days_in_month = _calendar.monthrange(year, month)[1]
        rows = get_attendance_for_month(employee_id, employee_name, year, month)
        codes = [get_status_code(r["status"], r["remarks"]) for r in rows]
        codes += [""] * (31 - days_in_month)  # pad short months
        month_label = _calendar.month_abbr[month]
        data[month_label] = codes
    return pd.DataFrame.from_dict(data, orient="index", columns=columns)


def get_yearly_summary(employee_id: str, employee_name: str, year: int) -> dict:
    """Counts of each status across the whole year — for the summary
    cards on the Individual Employee (yearly) view."""
    # summary: dict[str, int] = {}
    # for month in range(1, 13):
    #     month_summary = get_monthly_summary(employee_id, employee_name, year, month)
    #     for status, count in month_summary.items():
    #         summary[status] = summary.get(status, 0) + count
    # return summary
    
    summary = {}

    # 1. Attendance based
    for month in range(1, 13):
        month_summary = get_monthly_summary(employee_id,employee_name,year,month)

        for status, count in month_summary.items():
            summary[status] = (summary.get(status, 0)+count)

    # 2. Leave based
    leave_summary = get_yearly_leave_summary(employee_id,year)
    for status, days in leave_summary.items():
        summary[status] = days
    return summary


def get_attendance_for_year(employee_id: str, employee_name: str, year: int) -> list[dict]:
    """Every day of the year, flattened — used to list/clear manual
    exceptions without being limited to a single month."""
    all_rows = []
    for month in range(1, 13):
        all_rows.extend(get_attendance_for_month(employee_id, employee_name, year, month))
    return all_rows