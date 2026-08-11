from datetime import date

from utils.supabase_client import upload_file
from utils.sheets_client import append_row, read_table


DOCUMENT_TYPE = "mc"


def upload_leave_attachment(
    request_id: str,
    employee_id: str,
    employee_name: str,
    uploaded_file,
):
    """
    Upload MC / leave attachment to Supabase Storage
    and save metadata into LeaveAttachments sheet.

    Storage structure:
        mc/{employee_id}/{filename}

    Example:
        mc/EMP001/LV0001_MC_2026-08-11.pdf
    """

    employee_id = str(employee_id).strip()
    request_id = str(request_id).strip()

    # Keep the original file name
    original_filename = uploaded_file.name

    # Add request ID to make the file name unique
    filename = f"{request_id}_{original_filename}"

    # New unified storage structure:
    # {document_type}/{employee_id}/{filename}
    file_path = f"mc/{employee_id}/{filename}"

    upload_file(
        uploaded_file.getvalue(),
        file_path,
        uploaded_file.type,
    )

    # Save metadata into Google Sheet
    append_row(
        "LeaveAttachments",
        {
            "request_id": request_id,
            "employee_id": employee_id,
            "employee_name": employee_name,
            "file_name": filename,
            "file_path": file_path,
            "uploaded_date": str(date.today()),
        },
    )

    return file_path


def get_leave_attachment(
    request_id: str,
):
    """
    Get attachment information for one leave request.
    """

    df = read_table("LeaveAttachments")

    if df.empty:
        return []

    # Make sure request_id comparison is consistent
    result = df[
        df["request_id"].astype(str)
        == str(request_id)
    ]

    return result.to_dict("records")


def get_leave_attachments_for_employee(
    employee_id: str,
):
    """
    Get all MC / leave attachments belonging
    to one employee.

    Used when an employee views their own
    leave attachments.
    """

    df = read_table("LeaveAttachments")

    if df.empty:
        return []

    result = df[
        df["employee_id"].astype(str)
        == str(employee_id)
    ]

    return result.to_dict("records")


def get_all_leave_attachments():
    """
    Get all leave attachments.

    Intended for HR/Admin users.
    """

    df = read_table("LeaveAttachments")

    if df.empty:
        return []

    return df.to_dict("records")

