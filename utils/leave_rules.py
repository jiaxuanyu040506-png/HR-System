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


# ============================================================
# 1. Leave entitlement based on tenure
# ============================================================

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


# ============================================================
# 2. Public holidays (Johor) — VERIFY movable dates before relying on this
# ============================================================
#
# HOW TO UPDATE THIS EVERY YEAR (or add an ad-hoc holiday):
#   Just add a new line below with the date and a label — nothing else
#   needs to change. This dict is not tied to a single year, so 2027's
#   dates simply get added alongside 2026's; nothing needs renaming.
#   Example:
#       date(2027, 1, 1): "New Year's Day",
#
PUBLIC_HOLIDAYS = {
    date(2026, 2, 16): "Chinese New Year Eve",
    date(2026, 2, 17): "Chinese New Year Day 1",
    date(2026, 2, 18): "Chinese New Year Day 2",
    date(2026, 3, 21): "Hari Raya Aidilfitri Day 1 (初一)",
    date(2026, 3, 22): "Hari Raya Aidilfitri Day 2 (初二)",
    date(2026, 3, 23): "Johor Sultan's Birthday",
    date(2026, 5, 1): "Labour Day",
    date(2026, 5, 27): "Hari Raya Haji — ESTIMATED, confirm with JAKIM/official gazette",
    date(2026, 6, 1): "Agong's Birthday",
    date(2026, 8, 31): "Independence Day (Merdeka)",
    date(2026, 9, 16): "Malaysia Day",
    date(2026, 12, 25): "Christmas",
    # Add 2027 dates here once confirmed, e.g.:
    # date(2027, 1, 1): "New Year's Day",
}


def is_rest_day(d: date) -> bool:
    """Saturday and Sunday are rest days for this company."""
    return d.weekday() in (5, 6)  # Monday=0 ... Saturday=5, Sunday=6


def is_public_holiday(d: date) -> bool:
    return d in PUBLIC_HOLIDAYS


def is_working_day(d: date) -> bool:
    return not is_rest_day(d) and not is_public_holiday(d)


def count_working_days(start: date, end: date) -> int:
    """
    Count the number of working days (inclusive of both start and end)
    in a date range, excluding rest days (Sat/Sun) and public holidays.
    This is what actually gets deducted from an employee's leave balance
    — e.g. requesting Fri-Mon only deducts the Friday and Monday.
    """
    count = 0
    current = start
    while current <= end:
        if is_working_day(current):
            count += 1
        current += timedelta(days=1)
    return count
