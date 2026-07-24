"""
ea_forms.py

EA Forms (annual income statements) are PDFs HR uploads once a year per
employee. The actual PDF bytes live in Google Drive (see drive_client.py);
this sheet tab just tracks which Drive file belongs to which employee/year:

    EAForms tab: employee_id, employee_name, year, drive_file_id, uploaded_date

Uploading again for the same employee+year REPLACES the old file (both
the Drive file and the sheet row), so HR can fix a mistake without
leaving orphaned duplicates.
"""
from __future__ import annotations

from datetime import date
from utils.sheets_client import read_table, append_row, update_row, get_row
from utils.drive_client import upload_file, download_file, delete_file


def upload_ea_form(employee_id: str, employee_name: str, year: str, file_bytes: bytes):
    filename = f"EA_{year}_{employee_name}_{employee_id}.pdf"
    existing = get_row("EAForms", {"employee_id": employee_id, "year": str(year)})

    if existing and existing.get("drive_file_id"):
        delete_file(existing["drive_file_id"])

    new_file_id = upload_file(file_bytes, filename)

    if existing:
        update_row("EAForms", {"employee_id": employee_id, "year": str(year)}, {
            "drive_file_id": new_file_id,
            "uploaded_date": str(date.today()),
        })
    else:
        append_row("EAForms", {
            "employee_id": employee_id,
            "employee_name": employee_name,
            "year": str(year),
            "drive_file_id": new_file_id,
            "uploaded_date": str(date.today()),
        })


def get_ea_forms_for_employee(employee_id: str) -> list[dict]:
    df = read_table("EAForms")
    if df.empty:
        return []
    mine = df[df["employee_id"] == employee_id]
    return mine.sort_values("year", ascending=False).to_dict("records")


def get_all_ea_forms() -> list[dict]:
    df = read_table("EAForms")
    if df.empty:
        return []
    return df.sort_values(["year", "employee_name"], ascending=[False, True]).to_dict("records")


def download_ea_form_bytes(drive_file_id: str) -> bytes:
    return download_file(drive_file_id)