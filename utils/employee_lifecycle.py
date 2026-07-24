"""
employee_lifecycle.py

Cascading delete: when HR deletes an employee record (via Employee
Management's "Delete this employee" action), this also removes every
piece of data linked to that employee_id across the other sheets —
otherwise leave requests, payslips, attendance, performance records,
and EA Forms would be left pointing at an employee that no longer
exists.

NOTE on EA Forms specifically: the Drive file itself is also deleted
(not just the sheet row), since otherwise it'd be an orphaned file
nobody can reach anymore.
"""
from __future__ import annotations

from utils.sheets_client import read_table, delete_row, delete_all_matching_rows


def delete_employee_and_all_data(employee_id: str) -> dict:
    """Delete the employee and everything linked to them. Returns a
    summary dict of how many rows were removed from each sheet, for
    a confirmation message."""
    summary = {}

    # EA Forms: delete the underlying Drive files too, not just the sheet rows.
    try:
        from utils.drive_client import delete_file
        ea_df = read_table("EAForms")
        if not ea_df.empty:
            mine = ea_df[ea_df["employee_id"] == employee_id]
            for _, row in mine.iterrows():
                if row.get("drive_file_id"):
                    delete_file(row["drive_file_id"])
    except Exception:
        pass  # Drive not configured / already gone — don't block the rest of the deletion

    summary["EAForms"] = delete_all_matching_rows("EAForms", {"employee_id": employee_id})
    summary["Payslips"] = delete_all_matching_rows("Payslips", {"employee_id": employee_id})
    summary["LeaveRequests"] = delete_all_matching_rows("LeaveRequests", {"employee_id": employee_id})
    summary["LeaveBalance"] = delete_all_matching_rows("LeaveBalance", {"employee_id": employee_id})
    summary["Attendance"] = delete_all_matching_rows("Attendance", {"employee_id": employee_id})
    summary["PerformanceRecords"] = delete_all_matching_rows("PerformanceRecords", {"employee_id": employee_id})

    delete_row("Employees", {"employee_id": employee_id})
    return summary