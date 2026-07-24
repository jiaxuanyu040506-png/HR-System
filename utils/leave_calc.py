"""
leave_calc.py

All leave-related business logic lives here: submitting requests,
approving/rejecting, and updating leave balances. Google Sheets only
stores the results — every calculation happens in Python.

LeaveBalance sheet columns (symmetric total/used pairs, so remaining is
always just total - used — no more back-calculating a "remaining-only"
field like the old sick_balance design):
    employee_id, year,
    annual_total, annual_used,
    medical_total, medical_used,
    unpaid_used

Leave types and how each one is tracked:
    Annual           -> draws down annual_used against annual_total.
                        If annual_total - annual_used is already <= 0
                        when a request is APPROVED, that request is
                        automatically converted to Unpaid instead (see
                        approve_request). Otherwise annual_used is
                        simply incremented — if a request is larger
                        than what's left, annual_used CAN exceed
                        annual_total, showing as a negative remaining
                        balance (allowed, not blocked).
    Medical          -> draws down medical_used against medical_total
                        (tenure-based entitlement, prorated — see
                        leave_rules.py).
    Unpaid           -> tracked in unpaid_used (no entitlement/cap).
    Maternity        -> NOT tracked as an annual balance; capped at 98 days per request.
    Hospitalization  -> NOT tracked as an annual balance; capped at 60 continuous days per request.
    Special          -> not tracked, no cap (discretionary, HR judgment).
    Married          -> not tracked, no cap (discretionary, HR judgment).

Tenure-based entitlement and working-day calculation (excluding weekends
+ public holidays) are defined in leave_rules.py.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from utils.sheets_client import read_table, append_row, update_row, delete_row, get_row
from utils.date_utils import parse_date
from utils.leave_rules import (
    count_working_days, get_prorated_annual_entitlement, get_prorated_medical_entitlement,
)

LEAVE_TYPES = ["Annual", "Unpaid", "Medical", "Maternity", "Hospitalization", "Special", "Married"]

MATERNITY_MAX_DAYS = 98
HOSPITALIZATION_MAX_CONTINUOUS_DAYS = 60


# ============================================================
# Balance: read / init / recalculate
# ============================================================

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
    Entitlement is prorated ("purata") for their join year (and for any
    later year in which they cross the 2-year/5-year tenure mark
    partway through), and annual leave is 0 while still within the
    6-month probation period — see leave_rules.py for the full rules.
    """
    employee = get_row("Employees", {"employee_id": employee_id})
    if employee is None:
        raise ValueError(f"Employee {employee_id} not found.")

    annual_total = get_prorated_annual_entitlement(employee["join_date"], year)
    medical_total = get_prorated_medical_entitlement(employee["join_date"], year)

    append_row("LeaveBalance", {
        "employee_id": employee_id,
        "year": year,
        "annual_total": annual_total,
        "annual_used": 0,
        "medical_total": medical_total,
        "medical_used": 0,
        "unpaid_used": 0,
    })


def recalculate_year_balance(employee_id: str, year: int):
    """
    Force-recompute an employee's leave TOTALS for a given year using
    the CURRENT entitlement rules, without touching how much they've
    already used. init_year_balance() only runs once (when no row
    exists yet), so it won't retroactively fix a balance that was
    already created under an older version of the rules — call this
    after changing the proration/probation logic, or if a balance just
    looks wrong.
    """
    employee = get_row("Employees", {"employee_id": employee_id})
    if employee is None:
        raise ValueError(f"Employee {employee_id} not found.")

    existing = get_leave_balance(employee_id, year)
    if existing is None:
        init_year_balance(employee_id, year)
        return

    new_annual_total = get_prorated_annual_entitlement(employee["join_date"], year)
    new_medical_total = get_prorated_medical_entitlement(employee["join_date"], year)

    # Keep existing usage
    annual_used = existing.get("annual_used", 0)
    medical_used = existing.get("medical_used", 0)
    unpaid_used = existing.get("unpaid_used", 0)

    update_row("LeaveBalance", {"employee_id": employee_id, "year": str(year)}, {
        "annual_total": new_annual_total,
        "annual_used": annual_used,

        "medical_total": new_medical_total,
        "medical_used": medical_used,
    })


# ============================================================
# Submitting requests
# ============================================================

def validate_request_days(leave_type: str, days: float) -> str | None:
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


def _calc_days(leave_type: str, start_date: date, end_date: date, session: str) -> float:
    if session == "Half Day":
        return 0.5
    if leave_type in ("Maternity", "Hospitalization"):
        return (end_date - start_date).days + 1
    return count_working_days(start_date, end_date)


def submit_leave_request(employee_id: str, leave_type: str, start_date: date,
                          end_date: date, reason: str, session: str = "Full Day") -> tuple[str, float]:
    """
    Submit a leave request. `days` is the number of actual WORKING days
    in the range (weekends and public holidays excluded), EXCEPT for
    Maternity/Hospitalization where every calendar day counts.
    session: "Full Day" or "Half Day" — Half Day only makes sense for a
    single-day request (start_date == end_date) and counts as 0.5 days.
    """
    employee = get_row("Employees", {"employee_id": employee_id})
    employee_name = employee["name"] if employee else ""

    days = _calc_days(leave_type, start_date, end_date, session)
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
    """Record leave on behalf of an employee, optionally marking it Approved immediately."""
    employee = get_row("Employees", {"employee_id": employee_id})
    employee_name = employee["name"] if employee else ""

    days = _calc_days(leave_type, start_date, end_date, session)
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

    if status == "Approved":
        _apply_approval_to_balance(employee_id, leave_type, days, start_date.year)

    return request_id, days


# ============================================================
# Approving / rejecting / deleting
# ============================================================

def _apply_approval_to_balance(employee_id: str, leave_type: str, days: float, year: int) -> str:
    """
    Deduct an approved request from the right balance bucket. Returns
    the EFFECTIVE leave_type actually applied — this differs from the
    requested leave_type when Annual leave is auto-converted to Unpaid
    because the annual balance is already exhausted (<= 0) BEFORE this
    request. If there's still some balance left but not enough to
    cover the whole request, annual_used is simply allowed to go
    negative on the "remaining" side rather than splitting the request.
    """
    if leave_type not in ("Annual", "Medical", "Unpaid"):
        return leave_type  # Maternity / Hospitalization / Special / Married aren't balance-tracked

    balance = get_leave_balance(employee_id, year)
    if balance is None:
        init_year_balance(employee_id, year)
        balance = get_leave_balance(employee_id, year)

    if leave_type == "Annual":
        remaining = float(balance["annual_total"]) - float(balance["annual_used"])
        if remaining <= 0:
            # No annual leave left at all — this request becomes Unpaid instead.
            new_unpaid = float(balance.get("unpaid_used", 0)) + days
            update_row("LeaveBalance", {"employee_id": employee_id, "year": str(year)},
                        {"unpaid_used": new_unpaid})
            return "Unpaid"
        new_used = float(balance["annual_used"]) + days
        update_row("LeaveBalance", {"employee_id": employee_id, "year": str(year)},
                    {"annual_used": new_used})
        return "Annual"

    if leave_type == "Medical":
        new_used = float(balance["medical_used"]) + days
        update_row("LeaveBalance", {"employee_id": employee_id, "year": str(year)},
                    {"medical_used": new_used})
        return "Medical"

    # Unpaid
    new_unpaid = float(balance.get("unpaid_used", 0)) + days
    update_row("LeaveBalance", {"employee_id": employee_id, "year": str(year)},
                {"unpaid_used": new_unpaid})
    return "Unpaid"


def _reverse_approval_from_balance(employee_id: str, leave_type: str, days: float, year: int):
    """Undo what _apply_approval_to_balance did — used when deleting an approved record."""
    balance = get_leave_balance(employee_id, year)
    if balance is None:
        return
    if leave_type == "Annual":
        new_used = max(float(balance["annual_used"]) - days, 0)
        update_row("LeaveBalance", {"employee_id": employee_id, "year": str(year)}, {"annual_used": new_used})
    elif leave_type == "Medical":
        new_used = max(float(balance["medical_used"]) - days, 0)
        update_row("LeaveBalance", {"employee_id": employee_id, "year": str(year)}, {"medical_used": new_used})
    elif leave_type == "Unpaid":
        new_unpaid = max(float(balance.get("unpaid_used", 0)) - days, 0)
        update_row("LeaveBalance", {"employee_id": employee_id, "year": str(year)}, {"unpaid_used": new_unpaid})


def approve_request(request_id: str, approver_email: str):
    requests = read_table("LeaveRequests")
    req = requests[requests["request_id"] == request_id].iloc[0]
    year = parse_date(req["start_date"]).year

    effective_type = _apply_approval_to_balance(
        req["employee_id"], req["leave_type"], float(req["days"]), year
    )

    updates = {"status": "Approved", "approved_by": approver_email}
    if effective_type != req["leave_type"]:
        # Auto-converted Annual -> Unpaid because the balance was exhausted.
        updates["leave_type"] = effective_type
        updates["reason"] = f"{req.get('reason', '')} (auto-converted to Unpaid: no annual leave left)".strip()
    update_row("LeaveRequests", {"request_id": request_id}, updates)


def reject_request(request_id: str, approver_email: str):
    update_row("LeaveRequests", {"request_id": request_id},
                {"status": "Rejected", "approved_by": approver_email})


def delete_leave_request(request_id: str) -> bool:
    request = get_row("LeaveRequests", {"request_id": request_id})
    if request is None:
        return False

    if request.get("status") == "Approved":
        year = parse_date(request["start_date"]).year
        _reverse_approval_from_balance(
            request["employee_id"], request["leave_type"], float(request.get("days", 0) or 0), year
        )

    return delete_row("LeaveRequests", {"request_id": request_id})


# ============================================================
# Queries used across pages
# ============================================================

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


def get_all_requests() -> list[dict]:
    """Used on the HR 'Employee Leave History' view — every request, any status."""
    df = read_table("LeaveRequests")
    if df.empty:
        return []
    return df.sort_values("submit_date", ascending=False).to_dict("records")


def get_calendar_events() -> list[dict]:
    """
    Build a list of events (FullCalendar format) for every Approved leave
    request company-wide, for the Leave Calendar views. streamlit_calendar
    expects end dates to be exclusive, so we add 1 day to end_date.
    """
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
        "Married": "#f2c94c",
    }

    events = []
    for _, row in approved.iterrows():
        end_exclusive = parse_date(row["end_date"]) + timedelta(days=1)
        events.append({
            "title": f"{row.get('employee_name', row['employee_id'])}",
            "start": str(row["start_date"]),
            "end": str(end_exclusive),
            "color": colors.get(row["leave_type"], "#2f80ed"),
        })
    return events


def get_employee_leave_type_days(year: int | None = None) -> list[dict]:
    """
    Per-employee, per-leave-type total APPROVED days taken — used for the
    'who took how much, broken down by leave type' stacked bar chart on
    the Leave Summary view.
    """
    if year is None:
        year = date.today().year

    df = read_table("LeaveRequests")
    if df.empty:
        return []

    approved = df[df["status"] == "Approved"]
    totals: dict[tuple, float] = defaultdict(float)

    for _, row in approved.iterrows():
        try:
            start_date = parse_date(row["start_date"])
            end_date = parse_date(row["end_date"])
        except ValueError:
            continue
        if start_date.year != year and end_date.year != year:
            continue
        name = row.get("employee_name") or row["employee_id"]
        leave_type = row.get("leave_type", "Unknown")
        totals[(name, leave_type)] += float(row.get("days", 0) or 0)

    return [
        {"employee_name": name, "leave_type": leave_type, "days": round(days, 1)}
        for (name, leave_type), days in totals.items()
    ]


def get_employee_monthly_leave_days(year: int | None = None) -> list[dict]:
    """
    Per-employee, per-month total APPROVED leave days taken — for the
    'who took how much, broken down by month' stacked bar chart. Each
    day of a multi-day request is attributed to the month it actually
    falls in (a request spanning month-end gets split across both).
    """
    if year is None:
        year = date.today().year

    df = read_table("LeaveRequests")
    if df.empty:
        return []

    approved = df[df["status"] == "Approved"]
    totals: dict[tuple, float] = defaultdict(float)

    for _, row in approved.iterrows():
        try:
            start_date = parse_date(row["start_date"])
            end_date = parse_date(row["end_date"])
        except ValueError:
            continue
        if start_date.year != year and end_date.year != year:
            continue

        current = max(start_date, date(year, 1, 1))
        last_of_year = min(end_date, date(year, 12, 31))
        total_days = (end_date - start_date).days + 1 or 1
        per_day = float(row.get("days", total_days)) / total_days if total_days else 0

        while current <= last_of_year:
            month_key = (row.get("employee_name") or row["employee_id"], f"{current.year}-{current.month:02d}")
            totals[month_key] += per_day
            if current.month == 12:
                current = date(current.year + 1, 1, 1)
            else:
                current = date(current.year, current.month + 1, 1)

    return [
        {"employee_name": name, "month": month, "days": round(days, 1)}
        for (name, month), days in totals.items()
    ]


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
        f"{y}-{m:02d}": len(employee_ids)
        for (y, m), employee_ids in sorted(month_employee_map.items())
    }


def get_employee_leave_summaries(year: int | None = None) -> list[dict]:
    """Per-employee annual/medical/unpaid leave usage and remaining balances."""
    if year is None:
        year = date.today().year

    employees = read_table("Employees")
    balances = read_table("LeaveBalance")
    if employees.empty:
        return []

    balance_rows = {}
    if not balances.empty:
        balance_rows = {
            (str(row["employee_id"]), int(row["year"])): row
            for _, row in balances.iterrows()
        }

    summaries = []
    for _, employee in employees.iterrows():
        emp_id = str(employee["employee_id"])
        balance = balance_rows.get((emp_id, year))

        annual_total = float(balance["annual_total"]) if balance is not None else 0.0
        annual_used = float(balance["annual_used"]) if balance is not None else 0.0
        medical_total = float(balance["medical_total"]) if balance is not None else 0.0
        medical_used = float(balance["medical_used"]) if balance is not None else 0.0
        unpaid_used = float(balance.get("unpaid_used", 0)) if balance is not None else 0.0

        summaries.append({
            "employee_id": emp_id,
            "employee_name": employee.get("name", ""),
            "department": employee.get("department", ""),
            "annual_total": annual_total,
            "annual_used": annual_used,
            "annual_remaining": annual_total - annual_used,  # can be negative — allowed by design
            "medical_total": medical_total,
            "medical_used": medical_used,
            "medical_remaining": medical_total - medical_used,
            "unpaid_used": unpaid_used,
            "year": year,
        })

    return summaries

# Added 23 July, 2026
def rebuild_all_leave_balances(year: int | None = None):
    """
    Rebuild LeaveBalance from LeaveRequests.

    LeaveRequests is the source of truth.
    Only Approved leave requests will affect balance.

    This will recreate:
    - annual_used
    - medical_used
    - unpaid_used
    - annual_total
    - medical_total
    """

    from datetime import date
    import pandas as pd
    from utils.sheets_client import read_table, append_row, delete_row

    if year is None:
        year = date.today().year

    employees = read_table("Employees")
    requests = read_table("LeaveRequests")

    if employees.empty:
        return

    # Only approved requests count
    if requests.empty:
        approved_requests = pd.DataFrame()
    else:
        approved_requests = requests[(requests["status"] == "Approved")]

    new_balances = []

    for _, employee in employees.iterrows():

        employee_id = str(employee["employee_id"])

        annual_used = 0.0
        medical_used = 0.0
        unpaid_used = 0.0

        # calculate usage from LeaveRequests
        if not approved_requests.empty:

            emp_requests = approved_requests[approved_requests["employee_id"].astype(str) == employee_id]

            # only current year
            for _, req in emp_requests.iterrows():

                try:
                    start_year = int(str(req["start_date"])[:4])
                except Exception:
                    continue

                if start_year != year:
                    continue

                days = float(req.get("days", 0))

                leave_type = req["leave_type"]

                if leave_type == "Annual":
                    annual_used += days

                elif leave_type == "Medical":
                    medical_used += days

                elif leave_type == "Unpaid":
                    unpaid_used += days


        # calculate entitlement using current rules
        annual_total = get_prorated_annual_entitlement(employee["join_date"], year)

        medical_total = get_prorated_medical_entitlement(employee["join_date"],year)


        new_balances.append({
            "employee_id": employee_id,
            "employee_name": employee.get("name", ""),
            "year": year,

            "annual_total": annual_total,
            "annual_used": annual_used,

            "medical_total": medical_total,
            "medical_used": medical_used,

            "unpaid_used": unpaid_used,
        })


    # remove existing LeaveBalance data
    existing_balances = read_table("LeaveBalance")

    if not existing_balances.empty:
        for _, row in existing_balances.iterrows():
            delete_row(
                "LeaveBalance",
                {
                    "employee_id": str(row["employee_id"]),
                    "year": str(row["year"])
                }
            )


    # insert rebuilt balances
    for balance in new_balances:
        append_row(
            "LeaveBalance",
            balance
        )