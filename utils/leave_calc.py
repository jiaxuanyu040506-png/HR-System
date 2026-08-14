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
import pandas as pd
from collections import defaultdict
from datetime import date, datetime, timedelta
from utils.sheets_client import read_table, append_row, update_row, delete_row, get_row
from utils.date_utils import parse_date
from utils.leave_rules import (
    count_working_days,
    get_prorated_annual_entitlement,
    get_prorated_medical_entitlement,
    split_annual_leave_to_unpaid,
)

LEAVE_TYPES = ["Annual", "Unpaid", "Medical", "Maternity", "Hospitalization", "Special", "Married"]

MATERNITY_MAX_DAYS = 98
HOSPITALIZATION_MAX_CONTINUOUS_DAYS = 60


# ============================================================
# Balance: read / init / recalculate
# ============================================================

def get_leave_usage(employee_id: str, year: int, include_pending: bool = False) -> dict[str, float]:
    """Return approved leave usage for a specific employee/year.

    LeaveRequests is the source of truth. Pending and rejected requests do not
    contribute to the used days calculation.

    For Annual leave, a request may be split across Annual and Unpaid when the
    employee has limited annual balance remaining. Example: AL remaining = 0.5,
    request = 1.0 -> annual_used = 0.5, unpaid_used = 0.5.
    """
    df = read_table("LeaveRequests")
    usage = {
        "annual_used": 0.0,
        "medical_used": 0.0,
        "unpaid_used": 0.0,
    }

    if df.empty:
        return usage

    filtered = df[df["employee_id"].astype(str) == str(employee_id)].copy()
    if filtered.empty:
        return usage

    if not include_pending:
        filtered = filtered[filtered["status"].astype(str).str.lower() == "approved"]

    employee = get_row("Employees", {"employee_id": employee_id})
    annual_total = 0.0
    if employee is not None:
        annual_total = get_prorated_annual_entitlement(employee["join_date"], year)

    annual_used_so_far = 0.0

    for _, row in filtered.iterrows():
        try:
            start_date = parse_date(row["start_date"])
            end_date = parse_date(row["end_date"])
        except Exception:
            continue

        if start_date.year != year and end_date.year != year:
            continue

        leave_type = str(row.get("leave_type", "")).strip()
        days = float(row.get("days", 0) or 0)

        if leave_type == "Annual":
            annual_used, unpaid_days = split_annual_leave_to_unpaid(days, annual_total - annual_used_so_far)
            usage["annual_used"] += annual_used
            usage["unpaid_used"] += unpaid_days
            annual_used_so_far += annual_used
        elif leave_type == "Medical":
            usage["medical_used"] += days
        elif leave_type == "Unpaid":
            usage["unpaid_used"] += days

    return usage


def get_leave_summary(employee_id: str, year: int, include_pending: bool = False) -> dict:
    """Return leave entitlement and usage derived from the current rules.

    This keeps the calculation centralized and ensures each page consumes the same
    annual/medical/unpaid totals and used values.
    """
    employee = get_row("Employees", {"employee_id": employee_id})
    if employee is None:
        return {
            "employee_id": employee_id,
            "year": year,
            "annual_total": 0.0,
            "annual_used": 0.0,
            "annual_remaining": 0.0,
            "medical_total": 0.0,
            "medical_used": 0.0,
            "medical_remaining": 0.0,
            "unpaid_used": 0.0,
        }

    annual_total = get_prorated_annual_entitlement(employee["join_date"], year)
    medical_total = get_prorated_medical_entitlement(employee["join_date"], year)
    usage = get_leave_usage(employee_id, year, include_pending=include_pending)

    annual_used = usage["annual_used"]
    medical_used = usage["medical_used"]
    unpaid_used = usage["unpaid_used"]

    return {
        "employee_id": employee_id,
        "year": year,
        "annual_total": annual_total,
        "annual_used": annual_used,
        "annual_remaining": annual_total - annual_used,
        "medical_total": medical_total,
        "medical_used": medical_used,
        "medical_remaining": medical_total - medical_used,
        "unpaid_used": unpaid_used,
    }


def get_leave_balance(employee_id: str, year: int) -> dict | None:
    """Compatibility wrapper preserving the old API while using LeaveRequests as the source of truth."""
    employee = get_row("Employees", {"employee_id": employee_id})
    if employee is None:
        return None

    summary = get_leave_summary(employee_id, year)
    balance_row = read_table("LeaveBalance")
    if not balance_row.empty:
        match = balance_row[(balance_row["employee_id"].astype(str) == str(employee_id)) & (balance_row["year"].astype(str) == str(year))]
        if not match.empty:
            current = match.iloc[0].to_dict()
            current["annual_total"] = summary["annual_total"]
            current["annual_used"] = summary["annual_used"]
            current["medical_total"] = summary["medical_total"]
            current["medical_used"] = summary["medical_used"]
            current["unpaid_used"] = summary["unpaid_used"]
            return current

    return summary


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
        effective_type = _apply_approval_to_balance(employee_id, leave_type, days, start_date.year)
        if effective_type != leave_type:
            update_row("LeaveRequests", {"request_id": request_id}, {
                "leave_type": effective_type,
                "reason": f"{reason} (auto-converted to Unpaid: no annual leave left)".strip(),
            })

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
        print("DEBUG", employee_id, days, remaining)
        annual_used, unpaid_days = split_annual_leave_to_unpaid(days, remaining)

        if annual_used > 0:
            update_row("LeaveBalance", {"employee_id": employee_id, "year": str(year)},
                       {"annual_used": float(balance["annual_used"]) + annual_used})

        if unpaid_days > 0:
            update_row("LeaveBalance", {"employee_id": employee_id, "year": str(year)},
                       {"unpaid_used": float(balance.get("unpaid_used", 0)) + unpaid_days})

        if annual_used == 0:
            return "Unpaid"

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


# Updated 7 Aug, 2026 - Added month filtering based on actual leave start/end dates
def _request_matches_month(row, year: int, month: int | None = None) -> bool:
    """
    Return True if the request's leave period overlaps the given year/month.
    This is based on the actual leave dates (start_date / end_date),
    not the submit date.
    """
    try:
        start_date = parse_date(row["start_date"])
        end_date = parse_date(row["end_date"])
    except Exception:
        return False

    if month is None:
        return start_date.year <= year <= end_date.year

    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year, 12, 31)
    else:
        month_end = date(year, month + 1, 1) - timedelta(days=1)

    return start_date <= month_end and end_date >= month_start


# Updated 7 Aug, 2026 - Added leave history lookup for HR and employee views
def get_leave_history(year: int | None = None, month: int | None = None,
                      employee_id: str | None = None, name: str | None = None,
                      status: str | None = None) -> list[dict]:
    """
    Return leave history with optional filters.
    - For HR: year/month/name
    - For employee self-view: employee_id only
    Uses actual leave period (start/end), not submit date.
    """
    df = read_table("LeaveRequests")
    if df.empty:
        return []

    filtered = df.copy()

    if employee_id:
        filtered = filtered[filtered["employee_id"].astype(str) == str(employee_id)]

    if name:
        name_q = str(name).strip().lower()
        filtered = filtered[
            filtered["employee_name"].astype(str).str.lower().str.contains(name_q, na=False)
        ]

    if status:
        filtered = filtered[
            filtered["status"].astype(str).str.lower() == str(status).lower()
        ]

    if year is not None and month is not None:
        filtered = filtered[
            filtered.apply(lambda row: _request_matches_month(row, year, month), axis=1)
        ]
    elif year is not None:
        filtered = filtered[
            filtered["start_date"].astype(str).str.startswith(str(year))
            | filtered["end_date"].astype(str).str.startswith(str(year))
        ]

    if filtered.empty:
        return []

    return filtered.sort_values("start_date", ascending=False).to_dict("records")


# Updated 7 Aug, 2026 - 'Action'
def get_hr_leave_summary(year: int | None = None, month: int | None = None,
                         name: str | None = None) -> list[dict]:
    """
    Return a simple employee-level summary for HR:
    Annual / Medical / Unpaid / Other / Total
    for the selected year/month/name.
    """
    history = get_leave_history(year=year, month=month, name=name)

    employees = read_table("Employees")
    employee_lookup = {}
    if not employees.empty:
        employee_lookup = {
            str(row["employee_id"]): row
            for _, row in employees.iterrows()
        }

    summaries: dict[str, dict] = {}

    for row in history:
        emp_id = str(row.get("employee_id", ""))
        if not emp_id:
            continue

        if emp_id not in summaries:
            employee_row = employee_lookup.get(emp_id, {})
            summaries[emp_id] = {
                "employee_id": emp_id,
                "employee_name": row.get("employee_name") or employee_row.get("name", emp_id),
                "department": employee_row.get("department", ""),
                "annual": 0.0,
                "medical": 0.0,
                "unpaid": 0.0,
                "other": 0.0,
                "total": 0.0,
            }

        leave_type = row.get("leave_type", "Unknown")
        days = float(row.get("days", 0) or 0)

        if leave_type == "Annual":
            summaries[emp_id]["annual"] += days
        elif leave_type == "Medical":
            summaries[emp_id]["medical"] += days
        elif leave_type == "Unpaid":
            summaries[emp_id]["unpaid"] += days
        else:
            summaries[emp_id]["other"] += days

        summaries[emp_id]["total"] += days

    result = []
    for emp_id, item in summaries.items():
        item["annual"] = round(item["annual"], 1)
        item["medical"] = round(item["medical"], 1)
        item["unpaid"] = round(item["unpaid"], 1)
        item["other"] = round(item["other"], 1)
        item["total"] = round(item["total"], 1)
        result.append(item)

    return sorted(result, key=lambda x: x["employee_name"].lower())


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
    """Per-employee leave summary computed from LeaveRequests.

    LeaveRequests is the source of truth. LeaveBalance is treated as a derived
    cache / summary table and should not be used as the primary input for business
    logic or page-level display values.
    """
    if year is None:
        year = date.today().year

    employees = read_table("Employees")
    if employees.empty:
        return []

    summaries = []

    for _, employee in employees.iterrows():
        emp_id = str(employee["employee_id"])
        summary = get_leave_summary(emp_id, year)

        annual_used = summary["annual_used"]
        medical_used = summary["medical_used"]
        unpaid_used = summary["unpaid_used"]
        annual_total = summary["annual_total"]
        medical_total = summary["medical_total"]

        summaries.append({
            "employee_id": emp_id,
            "employee_name": employee.get("name", ""),
            "department": employee.get("department", ""),
            "annual_total": annual_total,
            "annual_used": annual_used,
            "annual_remaining": annual_total - annual_used,
            "medical_total": medical_total,
            "medical_used": medical_used,
            "medical_remaining": medical_total - medical_used,
            "unpaid_used": unpaid_used,
            "year": year,
        })

    return summaries

def normalize_approved_leave_requests_for_year(year: int):
    """Normalize approved requests so the saved leave_type reflects current annual split logic.

    This matters when historical rows were saved as plain Unpaid even though an Annual
    request should have been split against remaining annual leave. The stored request type
    should not be trusted as the business truth when recalculating balances.
    """
    requests = read_table("LeaveRequests")
    if requests.empty:
        return

    approved = requests[(requests["status"].astype(str).str.lower() == "approved")].copy()
    if approved.empty:
        return

    approved["_start_year"] = approved["start_date"].apply(lambda v: parse_date(v).year if str(v).strip() else None)
    approved = approved[approved["_start_year"] == year].copy()

    for _, req in approved.iterrows():
        req_id = str(req.get("request_id", ""))
        if not req_id:
            continue

        employee_id = str(req.get("employee_id", ""))
        employee = get_row("Employees", {"employee_id": employee_id})
        if employee is None:
            continue

        annual_total = get_prorated_annual_entitlement(employee["join_date"], year)
        if str(req.get("leave_type", "")).strip() not in {"Annual", "Unpaid", "Medical"}:
            continue

        # Recompute the actual annual/unpaid split from the current rules, using only
        # the approved requests for this employee/year in date order.
        emp_requests = approved[approved["employee_id"].astype(str) == employee_id].sort_values(
            by=["start_date", "end_date"], kind="mergesort"
        )

        annual_used_so_far = 0.0
        for _, row in emp_requests.iterrows():
            row_id = str(row.get("request_id", ""))
            if row_id == req_id:
                days = float(row.get("days", 0) or 0)
                leave_type = str(row.get("leave_type", "")).strip()

                if leave_type == "Annual":
                    annual_applied, unpaid_applied = split_annual_leave_to_unpaid(days, annual_total - annual_used_so_far)
                    if annual_applied == 0 and unpaid_applied > 0:
                        update_row("LeaveRequests", {"request_id": req_id}, {"leave_type": "Unpaid"})
                    elif annual_applied > 0 and unpaid_applied > 0:
                        update_row("LeaveRequests", {"request_id": req_id}, {"leave_type": "Annual"})
                elif leave_type == "Unpaid":
                    # Unpaid requests stay unpaid unless the historical row was incorrectly
                    # saved as Unpaid for an Annual request that still had annual balance.
                    annual_applied, unpaid_applied = split_annual_leave_to_unpaid(days, annual_total - annual_used_so_far)
                    if annual_applied > 0:
                        update_row("LeaveRequests", {"request_id": req_id}, {"leave_type": "Annual"})
                annual_used_so_far += max(annual_applied if leave_type == "Annual" else 0.0, 0.0)
                break

            if str(row.get("leave_type", "")).strip() == "Annual":
                days = float(row.get("days", 0) or 0)
                annual_used_so_far += split_annual_leave_to_unpaid(days, annual_total - annual_used_so_far)[0]

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
    from utils.sheets_client import read_table, append_row, delete_row, clear_sheet_caches

    if year is None:
        year = date.today().year

    normalize_approved_leave_requests_for_year(year)

    employees = read_table("Employees")
    requests = read_table("LeaveRequests")

    if employees.empty:
        return

    # Only approved requests count
    if requests.empty:
        approved_requests = pd.DataFrame()
    else:
        approved_requests = requests[(requests["status"].astype(str).str.lower() == "approved")]

    new_balances = []

    for _, employee in employees.iterrows():

        employee_id = str(employee["employee_id"])

        annual_total = get_prorated_annual_entitlement(employee["join_date"], year)
        medical_total = get_prorated_medical_entitlement(employee["join_date"], year)

        annual_used = 0.0
        medical_used = 0.0
        unpaid_used = 0.0
        annual_remaining = annual_total

        if not approved_requests.empty:
            emp_requests = approved_requests[approved_requests["employee_id"].astype(str) == employee_id]

            for _, req in emp_requests.iterrows():
                try:
                    start_year = int(str(req["start_date"])[:4])
                except Exception:
                    continue

                if start_year != year:
                    continue

                days = float(req.get("days", 0) or 0)
                leave_type = str(req.get("leave_type", "")).strip()

                if leave_type == "Annual":
                    annual_applied, unpaid_applied = split_annual_leave_to_unpaid(days, annual_remaining)
                    annual_used += annual_applied
                    unpaid_used += unpaid_applied
                    annual_remaining = max(annual_total - annual_used, 0.0)
                elif leave_type == "Medical":
                    medical_used += days
                elif leave_type == "Unpaid":
                    unpaid_used += days

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

    for balance in new_balances:
        append_row(
            "LeaveBalance",
            balance
        )

    clear_sheet_caches()