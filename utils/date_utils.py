"""
date_utils.py

Google Sheets can return dates as strings in several different formats
depending on how the cell is formatted / your locale settings (e.g.
"2026-07-01", "2026/7/1", "01/07/2026"), even if the sheet visually
displays it consistently. This module centralizes date parsing so every
part of the app handles all of these the same way, instead of each file
assuming one exact format.
"""
from __future__ import annotations

from datetime import date, datetime

# Try these formats in order. Add more here if you ever see a new
# ValueError for an unrecognized format.
_KNOWN_FORMATS = [
    "%Y-%m-%d",   # 2026-07-01 (ISO, what we store when the app itself writes dates)
    "%Y/%m/%d",   # 2026/7/1   (what Google Sheets sometimes returns)
    "%d/%m/%Y",   # 01/07/2026 (DD/MM/YYYY, as displayed in your Sheets)
    "%d-%m-%Y",   # 01-07-2026
]


def parse_date(value) -> date:
    """
    Parse a date coming from Google Sheets (or anywhere else in the app)
    into a Python date object, trying several common formats.
    Raises ValueError with a clear message if none match.
    """
    text = str(value).strip()
    for fmt in _KNOWN_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(
        f"Unrecognized date format: '{text}'. "
        f"Add its format to _KNOWN_FORMATS in utils/date_utils.py."
    )
