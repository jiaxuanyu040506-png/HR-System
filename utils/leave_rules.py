"""
leave_rules.py

Business rules for:
  1. Leave entitlement based on tenure (years of service)
  2. Which days count as "working days" when calculating how many days
     a leave request should deduct (excludes rest days + public holidays)

IMPORTANT — PLEASE READ:
Chinese New Year, Hari Raya Aidilfitri, Hari Raya Haji, and Agong's
Birthday are movable dates (lunar calendar / Islamic calendar / moon-
sighting dependent). The 2026 dates in PUBLIC_HOLIDAYS_2026 below were
compiled from public news sources as of July 2026. In March 2026 the
PM announced an EXTRA public holiday for Hari Raya Aidilfitri (Friday
20 March) on top of the original two days — this extra day is NOT
included below since you only asked for the standard 2 days (初一/初二).
Please double check all movable dates below against your company's
official HR notice / the government gazette before relying on this for
real payroll. Update this file every year — nothing here is calculated
automatically.
"""
from __future__ import annotations

from datetime import date, timedelta
from utils.date_utils import parse_date
from utils.sheets_client import read_table

# 1. Leave entitlement based on tenure
def _years_of_service(join_date: str, as_of: date | None = None) -> float:
    """Years of service as a decimal (e.g. 2.5), based on join_date."""
    jd = parse_date(join_date)
    as_of = as_of or date.today()
    return (as_of - jd).days / 365.25

def get_annual_leave_entitlement(join_date: str) -> int:
    """
    Annual leave days based on tenure:
      < 2 years   -> 8
      2-5 years   -> 12
      > 5 years   -> 16
    """
    years = _years_of_service(join_date)
    if years < 2:
        return 8
    elif years <= 5:
        return 12
    else:
        return 16

def get_sick_leave_entitlement(join_date: str) -> int:
    """
    Sick leave (MC) days based on tenure:
      < 2 years   -> 14
      2-5 years   -> 16
      > 5 years   -> 18
    """
    years = _years_of_service(join_date)
    if years < 2:
        return 14
    elif years <= 5:
        return 16
    else:
        return 18

# Updated 21 July, 2026
# ============================================================
# 1b. Probation + proration ("purata")
# ============================================================
#
# Rules (as confirmed):
#   - Probation lasts a fixed 3 months from join_date.
#   - During probation: NO annual leave at all (entitlement = 0).
#     Medical leave is NOT blocked during probation — it's prorated,
#     same as annual leave once probation clears.
#   - Entitlement is prorated for ANY calendar year in which the
#     employee's tenure bracket actually CHANGES partway through —
#     not just their original join year. This includes:
#       (a) the year they first join (obviously — they weren't
#           employed for the whole year), and
#       (b) the year they cross the 2-year or 5-year tenure mark,
#           since they only reach the higher bracket partway through
#           that year, not from 1 January.
#     A year with NO bracket change gets the full flat entitlement.
#
# Worked examples (both confirmed correct):
#   Join 2024-03-01, now in the 2-5yr bracket (12 days) ->
#       2024 (join year): Mar-Dec = 10 months -> 12 * 10/12 = 10 days
#
#   Join 2024-03-21 ->
#       2025: still <2yr the whole year -> flat 8 days (no crossing)
#       2026: turns 2 years old on 2026-03-21 (crosses into the 12-day
#             bracket mid-year) -> Mar-Dec = 10 months -> 12*10/12 = 10 days
#       2027: already 2-5yr the whole year -> flat 12 days (no crossing)

PROBATION_MONTHS = 3

def _add_months(d: date, months: int) -> date:
    import calendar as _calendar
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, _calendar.monthrange(year, month)[1])
    return date(year, month, day)

def is_in_probation(join_date: str, as_of: date | None = None) -> bool:
    """True if, as of `as_of` (default: today), the employee is still
    within their 3-month probation period."""
    jd = parse_date(join_date)
    as_of = as_of or date.today()
    probation_end = _add_months(jd, PROBATION_MONTHS)
    return as_of < probation_end

# Updated 23 July, 2026
def _months_remaining_in_year(from_date: date) -> int:
    """
    Count eligible remaining months in the year.

    Rule:
    - Day == 1: include current month
    - Day > 1: exclude current month

    Example:
    2026-05-01 -> May-Dec = 8 months
    2026-05-15 -> Jun-Dec = 7 months
    """
    if from_date.day == 1:
        return 12 - from_date.month + 1

    return 12 - from_date.month

def _bracket_for_years(years: float, kind: str) -> int:
    """kind is 'annual' or 'medical' — mirrors get_annual_leave_entitlement /
    get_sick_leave_entitlement's exact thresholds, just parameterized."""
    if kind == "annual":
        if years < 2:
            return 8
        elif years <= 5:
            return 12
        else:
            return 16
    else:  # medical
        if years < 2:
            return 14
        elif years <= 5:
            return 16
        else:
            return 18

# Updated 23 July, 2026
def _prorated_entitlement(join_date: str, year: int, kind: str):
    jd = parse_date(join_date)

    year_start = date(year,1,1)
    year_end = date(year,12,31)

    if jd.year > year:
        return 0.0

    # join year
    if jd.year == year:
        months = _months_remaining_in_year(jd)
        entitlement = _bracket_for_years(0, kind)

        return round(entitlement * months / 12 * 2) / 2

    # entitlement at start of year
    years_at_start = (year_start - jd).days / 365.25
    current_bracket = _bracket_for_years(years_at_start, kind)

    # anniversary
    two_year_anniv = _add_months(jd,24)
    five_year_anniv = _add_months(jd,60)

    crossing_date = None
    if year_start <= two_year_anniv <= year_end:
        crossing_date = two_year_anniv
    elif year_start <= five_year_anniv <= year_end:
        crossing_date = five_year_anniv

    # no anniversary
    if crossing_date is None:
        return float(current_bracket)

    # crossing year - use NEW entitlement
    months = _months_remaining_in_year(crossing_date)
    years_after_crossing = (crossing_date.year - jd.year)
    if (crossing_date.month,crossing_date.day) < (jd.month,jd.day):
        years_after_crossing -= 1

    new_bracket = _bracket_for_years(years_after_crossing, kind)
    return round( new_bracket * months / 12 * 2) / 2

    # 4. Stable entitlement
    # Use year-end service length
    years_at_year_end = (year_end - jd).days / 365.25
    bracket = _bracket_for_years(years_at_year_end, kind)
    return float(bracket)

def get_prorated_annual_entitlement(join_date: str, year: int | None = None,
                                     as_of: date | None = None) -> float:
    """
    Annual leave entitlement for a given year — prorated for the join
    year AND for any later year in which the employee crosses into a
    new tenure bracket partway through (see module notes above).
    Blocked entirely (0) while still within the 6-month probation.
    """
    as_of = as_of or date.today()
    year = year or as_of.year

    if is_in_probation(join_date, as_of):
        return 0.0  # still on probation right now -> no annual leave yet

    return _prorated_entitlement(join_date, year, "annual")

def get_prorated_medical_entitlement(join_date: str, year: int | None = None) -> float:
    """
    Medical (sick) leave entitlement for a given year — same crossing-
    aware proration as annual leave, but NOT blocked during probation.
    """
    year = year or date.today().year
    return _prorated_entitlement(join_date, year, "medical")

# PUBLIC / SPECIAL HOLIDAYS
def get_public_holidays() -> dict[date, str]:
    """
    Load active public and special holidays from Google Sheets.

    PublicHolidays sheet columns:

        date
        holiday_name
        holiday_type
        year
        active

    holiday_type:
        Public Holiday
        Special Holiday

    Returns:
        {
            date(2026, 8, 31): "Merdeka Day",
            date(2026, 9, 16): "Malaysia Day",
            ...
        }
    """

    df = read_table("PublicHolidays")

    if df.empty:
        return {}

    holidays = {}
    for _, row in df.iterrows():
        # Active
        active = str(row.get("active", "")).strip().lower()

        # If the sheet has an active column, only accept
        # active holidays.
        if "active" in df.columns:
            if active not in ("true", "yes", "1"):
                continue

        # Date
        try:
            holiday_date = parse_date(row["date"])
        except Exception:
            continue

        # Holiday name
        holiday_name = str(row.get("holiday_name", "")).strip()
        holidays[holiday_date] = holiday_name
    return holidays

def get_holiday_info(d: date) -> dict | None:
    """
    Return holiday information for a specific date.

    PublicHolidays sheet:

        date
        holiday_name
        holiday_type
        year
        active

    Returns:

        {
            "date": date(...),
            "name": "...",
            "type": "Public Holiday"
        }

    or None if the date is not a holiday.
    """

    df = read_table("PublicHolidays")

    if df.empty:
        return None

    for _, row in df.iterrows():
        # Active
        if "active" in df.columns:
            active = str(row.get("active", "")).strip().lower()

            if active not in ("true", "yes", "1",):
                continue

        # Date
        try:
            holiday_date = parse_date(row["date"])
        except Exception:
            continue

        if holiday_date != d:
            continue

        # Holiday name
        holiday_name = str(row.get("holiday_name", "")).strip()

        # Holiday type
        holiday_type = str(row.get("holiday_type", "Public Holiday")).strip()

        # Normalize old naming
        if holiday_type == "Special Leave":
            holiday_type = "Special Holiday"

        return {
            "date": holiday_date,
            "name": holiday_name,
            "type": holiday_type,
        }
    return None

def is_public_holiday(d: date) -> bool:
    """
    True if the date is an active Public Holiday.
    """

    holiday = get_holiday_info(d)

    if not holiday:
        return False

    return holiday["type"] == "Public Holiday"

def is_special_leave_day(d: date) -> bool:
    """
    True if the date is an active Special Holiday.

    Function name is kept as-is so existing code that imports
    is_special_leave_day() will continue to work.
    """

    holiday = get_holiday_info(d)

    if not holiday:
        return False

    return holiday["type"] == "Special Holiday"

def is_rest_day(d: date) -> bool:
    """
    Saturday and Sunday are rest days.
    """

    return d.weekday() in (5, 6)

def is_working_day(d: date) -> bool:
    """
    A working day is:

    - not Saturday
    - not Sunday
    - not Public Holiday
    - not Special Holiday
    """
    return (
        not is_rest_day(d)
        and not is_public_holiday(d)
        and not is_special_leave_day(d)
    )

def count_working_days(start: date, end: date,) -> int:
    """
    Count working days between start and end inclusive.

    Excludes:

    - Saturday
    - Sunday
    - Public Holiday
    - Special Holiday
    """

    count = 0
    current = start

    while current <= end:
        if is_working_day(current):
            count += 1
        current += timedelta(days=1)
    return count

def is_non_working_day(d: date) -> bool:
    """
    True if the date is:

    - Rest Day
    - Public Holiday
    - Special Holiday
    """
    return (
        is_rest_day(d)
        or is_public_holiday(d)
        or is_special_leave_day(d)
    )

def split_annual_leave_to_unpaid(requested_days: float, annual_leave_balance: float) -> tuple[float, float]:
    """
    Allocate requested annual leave days into:
      - actual annual leave used
      - unpaid leave days if annual leave is exhausted
    """
    requested_days = float(requested_days)
    annual_leave_balance = float(max(annual_leave_balance, 0.0))

    if requested_days <= 0:
        return 0.0, 0.0

    annual_used = min(requested_days, annual_leave_balance)
    unpaid_days = round(requested_days - annual_used, 2)

    return annual_used, unpaid_days
