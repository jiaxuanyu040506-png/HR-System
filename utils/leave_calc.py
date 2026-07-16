"""
leave_calc.py

All leave-related business logic lives here: submitting requests,
approving/rejecting, and updating leave balances. Google Sheets only
stores the results — every calculation happens in Python.

Leave types and how each one is tracked:
    Annual          -> draws down LeaveBalance.annual_used (tenure-based entitlement)
    Medical          -> draws down LeaveBalance.sick_balance (tenure-based entitlement)
    Maternity        -> NOT tracked as an annual balance; capped at 98 days per request
    Hospitalization  -> NOT tracked as an annual balance; capped at 60 continuous days per request
    Unpaid           -> not tracked, no cap
    Special           -> not tracked, no cap (discretionary, HR judgment)

Tenure-based entitlement and working-day calculation (excluding weekends
+ public holidays) are defined in leave_rules.py.
"""
from __future__ import annotations

import uuid
import pandas as pd
from datetime import date, datetime
from utils.sheets_client import read_table, append_row, update_row, get_row
from utils.date_utils import parse_date
from utils.leave_rules import (
    get_annual_leave_entitlement, get_sick_leave_entitlement, count_working_days,
)

LEAVE_TYPES = ["Annual", "Unpaid", "Medical", "Maternity", "Hospitalization", "Special"]

MATERNITY_MAX_DAYS = 98
HOSPITALIZATION_MAX_CONTINUOUS_DAYS = 60


def get_leave_balance(employee_id: str, year: int) -> dict | None:
    df = read_table("LeaveBalance")
    if df.empty:
        return None
    match = df[(df["employee_id"] == employee_id) & (df["year"].astype(str) == str(year))]
    if match.empty:
        return None
    return match.iloc[0].to_dict()


def init_year_balance(employee_id: str, year: int):
    """
    Create this employee's leave balance row for a given year.
    Annual/Medical leave entitlement is automatically calculated from
    their join_date and the tenure rules in leave_rules.py.
    """
    employee = get_row("Employees", {"employee_id": employee_id})
    if employee is None:
        raise ValueError(f"Employee {employee_id} not found.")

    annual_total = get_annual_leave_entitlement(employee["join_date"])
    sick_balance = get_sick_leave_entitlement(employee["join_date"])

    append_row("LeaveBalance", {
        "employee_id": employee_id,
        "year": year,
        "annual_total": annual_total,
        "annual_used": 0,
        "sick_balance": sick_balance,
    })


def validate_request_days(leave_type: str, days: int) -> str | None:
    """
    Returns an error message string if the request breaks a hard cap,
    or None if it's fine. Maternity/Hospitalization have fixed caps
    regardless of any annual balance.
    """
    if leave_type == "Maternity" and days > MATERNITY_MAX_DAYS:
        return f"Maternity leave cannot exceed {MATERNITY_MAX_DAYS} days per request."
    if leave_type == "Hospitalization" and days > HOSPITALIZATION_MAX_CONTINUOUS_DAYS:
        return f"Hospitalization leave cannot exceed {HOSPITALIZATION_MAX_CONTINUOUS_DAYS} continuous days per request."
    return None


def submit_leave_request(employee_id: str, leave_type: str, start_date: date,
                          end_date: date, reason: str, session: str = "Full Day") -> tuple[str, float]:
    """
    Submit a leave request. `days` is the number of actual WORKING days
    in the range (weekends and public holidays excluded — see
    leave_rules.count_working_days), EXCEPT for Maternity/Hospitalization
    where every calendar day counts (these are continuous leave types,
    not deducted from a weekday-only balance).

    session: "Full Day" or "Half Day". Half Day only makes sense for a
    single-day request (start_date == end_date) and counts as 0.5 days.
    """
    employee = get_row("Employees", {"employee_id": employee_id})
    employee_name = employee["name"] if employee else ""

    if session == "Half Day":
        days = 0.5
    elif leave_type in ("Maternity", "Hospitalization"):
        days = (end_date - start_date).days + 1
    else:
        days = count_working_days(start_date, end_date)

    error = validate_request_days(leave_type, days)
    if error:
        raise ValueError(error)

    request_id = f"LR{uuid.uuid4().hex[:8].upper()}"
    append_row("LeaveRequests", {
        "request_id": request_id,
        "employee_id": employee_id,
        "employee_name": employee_name,
        "leave_type": leave_type,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "days": days,
        "session": session,
        "reason": reason,
        "status": "Pending",
        "approved_by": "",
        "submit_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    return request_id, days


def record_leave_request(employee_id: str, leave_type: str, start_date: date,
                         end_date: date, reason: str, session: str = "Full Day",
                         status: str = "Approved", approved_by: str = "HR") -> tuple[str, float]:
    """Record leave on behalf of an employee, optionally marking it Approved."""
    employee = get_row("Employees", {"employee_id": employee_id})
    employee_name = employee["name"] if employee else ""

    if session == "Half Day":
        days = 0.5
    elif leave_type in ("Maternity", "Hospitalization"):
        days = (end_date - start_date).days + 1
    else:
        days = count_working_days(start_date, end_date)

    error = validate_request_days(leave_type, days)
    if error:
        raise ValueError(error)

    request_id = f"LR{uuid.uuid4().hex[:8].upper()}"
    append_row("LeaveRequests", {
        "request_id": request_id,
        "employee_id": employee_id,
        "employee_name": employee_name,
        "leave_type": leave_type,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "days": days,
        "session": session,
        "reason": reason,
        "status": status,
        "approved_by": approved_by if status == "Approved" else "",
        "submit_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })

    if status == "Approved" and leave_type in ("Annual", "Medical"):
        year = start_date.year
        balance = get_leave_balance(employee_id, year)
        if balance is None:
            init_year_balance(employee_id, year)
            balance = get_leave_balance(employee_id, year)

        if leave_type == "Annual":
            new_used = float(balance["annual_used"]) + float(days)
            update_row("LeaveBalance", {"employee_id": employee_id, "year": str(year)}, {"annual_used": new_used})
        else:
            new_balance = float(balance["sick_balance"]) - float(days)
            update_row("LeaveBalance", {"employee_id": employee_id, "year": str(year)}, {"sick_balance": new_balance})

    return request_id, days


def get_pending_requests(admin_email: str) -> list[dict]:
    employees = read_table("Employees")
    requests = read_table("LeaveRequests")
    if employees.empty or requests.empty:
        return []
    team_ids = employees[employees["admin_email"] == admin_email]["employee_id"].tolist()
    pending = requests[
        (requests["employee_id"].isin(team_ids)) & (requests["status"] == "Pending")
    ]
    return pending.to_dict("records")


def get_today_on_leave_count() -> int:
    """Number of employees on Approved leave that covers today's date."""
    from utils.date_utils import parse_date
    df = read_table("LeaveRequests")
    if df.empty:
        return 0
    today = date.today()
    approved = df[df["status"] == "Approved"]
    count = 0
    for _, row in approved.iterrows():
        try:
            if parse_date(row["start_date"]) <= today <= parse_date(row["end_date"]):
                count += 1
        except ValueError:
            continue
    return count


def get_all_pending_requests() -> list[dict]:
    """Used on the HR dashboard — every pending request company-wide."""
    requests = read_table("LeaveRequests")
    if requests.empty:
        return []
    return requests[requests["status"] == "Pending"].to_dict("records")


def get_my_requests(employee_id: str) -> list[dict]:
    df = read_table("LeaveRequests")
    if df.empty:
        return []
    mine = df[df["employee_id"] == employee_id]
    return mine.sort_values("submit_date", ascending=False).to_dict("records")


def approve_request(request_id: str, approver_email: str):
    from utils.date_utils import parse_date

    requests = read_table("LeaveRequests")
    req = requests[requests["request_id"] == request_id].iloc[0]
    year = parse_date(req["start_date"]).year

    if req["leave_type"] in ("Annual", "Medical"):
        balance = get_leave_balance(req["employee_id"], year)
        if balance is None:
            init_year_balance(req["employee_id"], year)
            balance = get_leave_balance(req["employee_id"], year)

        if req["leave_type"] == "Annual":
            new_used = float(balance["annual_used"]) + float(req["days"])
            update_row("LeaveBalance", {"employee_id": req["employee_id"], "year": str(year)},
                        {"annual_used": new_used})
        else:  # Medical
            new_balance = float(balance["sick_balance"]) - float(req["days"])
            update_row("LeaveBalance", {"employee_id": req["employee_id"], "year": str(year)},
                        {"sick_balance": new_balance})
    # Unpaid / Maternity / Hospitalization / Special don't touch any balance

    update_row("LeaveRequests", {"request_id": request_id},
                {"status": "Approved", "approved_by": approver_email})


def delete_leave_request(request_id: str) -> bool:
    from utils.date_utils import parse_date
    from utils.sheets_client import delete_row

    request = get_row("LeaveRequests", {"request_id": request_id})
    if request is None:
        return False

    if request.get("status") == "Approved" and request.get("leave_type") in ("Annual", "Medical"):
        year = parse_date(request["start_date"]).year
        balance = get_leave_balance(request["employee_id"], year)
        if balance is not None:
            if request["leave_type"] == "Annual":
                new_used = float(balance["annual_used"]) - float(request["days"])
                update_row("LeaveBalance", {"employee_id": request["employee_id"], "year": str(year)},
                            {"annual_used": max(new_used, 0)})
            else:
                new_balance = float(balance["sick_balance"]) + float(request["days"])
                update_row("LeaveBalance", {"employee_id": request["employee_id"], "year": str(year)},
                            {"sick_balance": new_balance})

    return delete_row("LeaveRequests", {"request_id": request_id})


def get_calendar_events() -> list[dict]:
    """
    Build a list of events (FullCalendar format) for every Approved leave
    request company-wide, for the HR Leave Calendar view. streamlit_calendar
    expects end dates to be exclusive, so we add 1 day to end_date.
    """
    from datetime import timedelta
    from utils.date_utils import parse_date

    df = read_table("LeaveRequests")
    if df.empty:
        return []
    approved = df[df["status"] == "Approved"]

    colors = {
        "Annual": "#2f80ed",
        "Medical": "#eb5757",
        "Unpaid": "#828282",
        "Maternity": "#bb6bd9",
        "Hospitalization": "#f2994a",
        "Special": "#219653",
    }

    events = []
    for _, row in approved.iterrows():
        end_exclusive = parse_date(row["end_date"]) + timedelta(days=1)
        events.append({
            "title": f"{row.get('employee_name', row['employee_id'])} - {row['leave_type']}",
            "start": str(row["start_date"]),
            "end": str(end_exclusive),
            "color": colors.get(row["leave_type"], "#2f80ed"),
        })
    return events


def get_all_requests() -> list[dict]:
    """Used on the HR 'Employee Leave History' tab — every request, any status."""
    df = read_table("LeaveRequests")
    if df.empty:
        return []
    return df.sort_values("submit_date", ascending=False).to_dict("records")


def get_monthly_approved_leave_headcount(year: int | None = None) -> dict[str, int]:
    """Return unique headcount of employees on approved leave for each month."""
    if year is None:
        year = date.today().year

    df = read_table("LeaveRequests")
    if df.empty:
        return {}

    approved = df[df["status"] == "Approved"]
    month_employee_map: dict[tuple[int, int], set[str]] = {}

    for _, row in approved.iterrows():
        try:
            start_date = parse_date(row["start_date"])
            end_date = parse_date(row["end_date"])
        except ValueError:
            continue

        if end_date.year < year or start_date.year > year:
            if start_date.year != year and end_date.year != year:
                continue

        current = max(start_date, date(year, 1, 1))
        last_of_year = min(end_date, date(year, 12, 31))
        while current <= last_of_year:
            month_key = (current.year, current.month)
            month_employee_map.setdefault(month_key, set()).add(str(row["employee_id"]))
            if current.month == 12:
                current = date(current.year + 1, 1, 1)
            else:
                current = date(current.year, current.month + 1, 1)

    return {
        f"{year}-{month:02d}": len(employee_ids)
        for (year, month), employee_ids in sorted(month_employee_map.items())
    }


def get_employee_leave_summaries(year: int | None = None) -> list[dict]:
    """Return per-employee annual/medical/unpaid leave usage and remaining balances."""
    if year is None:
        year = date.today().year

    employees = read_table("Employees")
    balances = read_table("LeaveBalance")
    requests = read_table("LeaveRequests")
    if employees.empty:
        return []

    balance_rows = {}
    if not balances.empty:
        balance_rows = {
            (str(row["employee_id"]), int(row["year"])): row
            for _, row in balances.iterrows()
        }

    unpaid_by_employee = {}
    if not requests.empty:
        approved = requests[requests["status"] == "Approved"]
        approved = approved[approved["leave_type"] == "Unpaid"]
        for _, row in approved.iterrows():
            try:
                if parse_date(row["start_date"]).year != year:
                    continue
            except ValueError:
                continue
            emp_id = str(row["employee_id"])
            unpaid_by_employee[emp_id] = unpaid_by_employee.get(emp_id, 0) + float(row["days"])

    summaries = []
    for _, employee in employees.iterrows():
        emp_id = str(employee["employee_id"])
        key = (emp_id, year)
        balance = balance_rows.get(key)
        annual_total = float(balance["annual_total"]) if balance is not None else 0.0
        annual_used = float(balance["annual_used"]) if balance is not None else 0.0
        annual_remaining = annual_total - annual_used
        sick_balance = float(balance["sick_balance"]) if balance is not None else 0.0

        sick_entitlement = 0.0
        medical_used = 0.0
        if balance is not None:
            try:
                sick_entitlement = float(get_sick_leave_entitlement(employee["join_date"]))
                medical_used = max(sick_entitlement - sick_balance, 0.0)
            except Exception:
                sick_entitlement = sick_balance
                medical_used = 0.0

        summaries.append({
            "employee_id": emp_id,
            "employee_name": employee.get("name", ""),
            "department": employee.get("department", ""),
            "annual_total": annual_total,
            "annual_used": annual_used,
            "annual_remaining": annual_remaining,
            "sick_entitlement": sick_entitlement,
            "medical_used": medical_used,
            "sick_balance": sick_balance,
            "unpaid_used": unpaid_by_employee.get(emp_id, 0.0),
            "year": year,
        })

    return summaries


def get_leave_days_by_employee(year: int | None = None) -> pd.DataFrame:
    """
    Total APPROVED leave days taken per employee in the given year, broken
    down by leave_type — used for the left-hand chart on the Leave Summary
    view (stacked bar: each employee's bar split by leave type).
    """
    import pandas as pd

    if year is None:
        year = date.today().year
    df = read_table("LeaveRequests")
    if df.empty:
        return pd.DataFrame()

    approved = df[df["status"] == "Approved"].copy()
    if approved.empty:
        return pd.DataFrame()

    def _in_year(row):
        try:
            return parse_date(row["start_date"]).year == year
        except ValueError:
            return False

    approved = approved[approved.apply(_in_year, axis=1)]
    if approved.empty:
        return pd.DataFrame()

    approved["days"] = approved["days"].astype(float)
    pivot = approved.pivot_table(
        index="employee_name", columns="leave_type", values="days", aggfunc="sum", fill_value=0
    )
    return pivot


def reject_request(request_id: str, approver_email: str):
    update_row("LeaveRequests", {"request_id": request_id},
                {"status": "Rejected", "approved_by": approver_email})