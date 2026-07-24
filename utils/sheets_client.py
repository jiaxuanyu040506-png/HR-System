"""
sheets_client.py

This is the ONLY module that talks to Google Sheets directly.
Every other page/module calls the functions here instead of using
gspread directly — if you ever swap Google Sheets for a real database,
this is the only file you need to rewrite.

Two separate Google Sheets files are used:
  - MAIN_DB_NAME:  Employees / LeaveRequests / LeaveBalances / Payslips
  - RATE_DB_NAME:  SOCSO / EPF / EPF_60 (official statutory rate tables)
Both must be shared with the service account's email as "Editor".
"""
from __future__ import annotations


import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",   # keeps existing "open sheet by name" working
    "https://www.googleapis.com/auth/drive.file",       # NEW: lets the app upload/manage files it creates (EA Forms)
]

MAIN_DB_NAME = "HR_System_Database"
RATE_DB_NAME = "SOCSO_EPF_RateConfig"


@st.cache_resource
def get_credentials():
    """The raw Google credentials object — reused by both gspread (Sheets)
    and the Drive API client (drive_client.py), so there's only one login."""
    creds_dict = st.secrets["gcp_service_account"]
    return Credentials.from_service_account_info(creds_dict, scopes=SCOPES)


@st.cache_resource
def get_client():
    return gspread.authorize(get_credentials())

# @st.cache_resource
# def get_credentials():
#     creds = Credentials.from_service_account_info(
#         st.secrets["google_service_account"],
#         scopes=SCOPES
#     )
#     return creds

# @st.cache_resource
# def get_client():
#     creds = get_credentials()
#     return gspread.authorize(creds)


def get_sheet(tab_name: str):
    client = get_client()
    return client.open(MAIN_DB_NAME).worksheet(tab_name)


def get_rate_sheet(tab_name: str):
    client = get_client()
    return client.open(RATE_DB_NAME).worksheet(tab_name)


@st.cache_data(ttl=60)
def read_table(tab_name: str) -> pd.DataFrame:
    """Read an entire tab from the main database as a DataFrame."""
    ws = get_sheet(tab_name)
    records = ws.get_all_records()
    return pd.DataFrame(records)


@st.cache_data(ttl=300)
def read_rate_table(tab_name: str) -> pd.DataFrame:
    """Read an entire tab from the rate config file as a DataFrame."""
    ws = get_rate_sheet(tab_name)
    records = ws.get_all_records()
    return pd.DataFrame(records)


def clear_sheet_caches() -> None:
    """Invalidate cached sheet reads so the UI reflects the latest Google Sheet state."""
    try:
        st.cache_data.clear()
    except Exception:
        pass
    try:
        read_table.clear()  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        read_rate_table.clear()  # type: ignore[attr-defined]
    except Exception:
        pass


def append_row(tab_name: str, row_dict: dict):
    """
    Append a new row. row_dict keys must match the sheet's header names —
    order doesn't matter, missing keys are written as blank.
    """
    ws = get_sheet(tab_name)
    headers = ws.row_values(1)
    row_values = [row_dict.get(h, "") for h in headers]
    ws.append_row(row_values)
    clear_sheet_caches()


def update_row(tab_name: str, match: dict, updates: dict) -> bool:
    """
    Find the first row where every (column, value) pair in `match` is true,
    then write `updates` into that row. Returns True if a row was found
    and updated, False otherwise.

    Example:
        update_row("Employees", {"employee_id": "EMP001"}, {"phone": "0123456789"})
        update_row("LeaveBalances", {"employee_id": "EMP001", "year": "2026"}, {"annual_used": 5})
    """
    ws = get_sheet(tab_name)
    headers = ws.row_values(1)
    all_values = ws.get_all_values()

    for i, row in enumerate(all_values[1:], start=2):  # sheet rows are 1-indexed, row 1 is header
        row_dict = dict(zip(headers, row))
        if all(str(row_dict.get(k, "")) == str(v) for k, v in match.items()):
            for key, value in updates.items():
                if key in headers:
                    col_idx = headers.index(key) + 1
                    ws.update_cell(i, col_idx, value)
            clear_sheet_caches()
            return True
    return False


def delete_row(tab_name: str, match: dict) -> bool:
    """Delete the first row matching all key/value pairs in `match`."""
    ws = get_sheet(tab_name)
    headers = ws.row_values(1)
    all_values = ws.get_all_values()

    for row_idx, row in enumerate(all_values[1:], start=2):
        row_dict = dict(zip(headers, row))
        if all(str(row_dict.get(k, "")) == str(v) for k, v in match.items()):
            if hasattr(ws, "delete_row"):
                ws.delete_row(row_idx)
            else:
                ws.delete_rows(row_idx, row_idx)
            clear_sheet_caches()
            return True
    return False


def delete_all_matching_rows(tab_name: str, match: dict) -> int:
    """
    Delete EVERY row matching all key/value pairs in `match` (not just
    the first) — used for cascading deletes, e.g. removing all of an
    employee's leave requests/payslips/attendance when the employee
    record itself is deleted. Returns how many rows were deleted.
    """
    ws = get_sheet(tab_name)
    headers = ws.row_values(1)
    all_values = ws.get_all_values()

    matching_row_indices = [
        row_idx for row_idx, row in enumerate(all_values[1:], start=2)
        if all(str(dict(zip(headers, row)).get(k, "")) == str(v) for k, v in match.items())
    ]

    # Delete from the bottom up so earlier row numbers don't shift under us.
    for row_idx in reversed(matching_row_indices):
        if hasattr(ws, "delete_row"):
            ws.delete_row(row_idx)
        else:
            ws.delete_rows(row_idx, row_idx)

    if matching_row_indices:
        clear_sheet_caches()
    return len(matching_row_indices)


def get_row(tab_name: str, match: dict) -> dict | None:
    """Return the first row (as a dict) matching all key/value pairs, or None."""
    df = read_table(tab_name)
    if df.empty:
        return None
    mask = pd.Series([True] * len(df))
    for k, v in match.items():
        mask &= df[k].astype(str) == str(v)
    result = df[mask]
    if result.empty:
        return None
    return result.iloc[0].to_dict()