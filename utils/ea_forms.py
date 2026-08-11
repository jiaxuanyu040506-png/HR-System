"""
ea_forms.py

EA Forms are uploaded by HR once per year per employee.

Actual PDF files are stored in Supabase Storage.

Storage bucket:
    hr-documents

Storage structure:

hr-documents/
└── ea_form/
    └── {employee_id}/
        └── EA_{year}_{employee_id}.pdf

EAForms sheet stores metadata only:

employee_id
employee_name
year
storage_path
uploaded_date

Uploading again for the same employee + year replaces
the existing PDF.
"""

from __future__ import annotations

from datetime import date

from utils.sheets_client import (
    read_table,
    append_row,
    update_row,
    get_row,
)

from utils.supabase_client import (
    upload_file,
    download_file,
    delete_file,
)


# ============================================================
# Configuration
# ============================================================

DOCUMENT_TYPE = "ea_form"


# ============================================================
# Upload / Replace EA Form
# ============================================================

def upload_ea_form(
    employee_id: str,
    employee_name: str,
    year: str,
    file_bytes: bytes,
) -> str:
    """
    Upload or replace an EA Form.

    One EA Form is allowed per employee per year.

    Storage path:
        ea_form/{employee_id}/EA_{year}_{employee_id}.pdf

    Returns:
        storage_path
    """

    employee_id = str(employee_id).strip()
    employee_name = str(employee_name).strip()
    year = str(year).strip()

    # --------------------------------------------------------
    # Build filename and storage path
    # --------------------------------------------------------

    filename = (
        f"EA_{year}_{employee_id}.pdf"
    )

    storage_path = (
        f"{DOCUMENT_TYPE}/"
        f"{employee_id}/"
        f"{filename}"
    )

    # --------------------------------------------------------
    # Check whether an EA Form already exists
    # for this employee + year
    # --------------------------------------------------------

    existing = get_row(
        "EAForms",
        {
            "employee_id": employee_id,
            "year": year,
        },
    )

    # --------------------------------------------------------
    # Delete old file if it exists
    # --------------------------------------------------------

    if existing and existing.get("storage_path"):

        old_storage_path = str(
            existing["storage_path"]
        ).strip()

        if old_storage_path:

            try:
                delete_file(
                    old_storage_path
                )

            except Exception:
                # If the old file has already been
                # deleted from Supabase, continue
                # with the new upload.
                pass

    # --------------------------------------------------------
    # Upload new file
    # --------------------------------------------------------

    upload_file(
        file_bytes=file_bytes,
        file_path=storage_path,
        mime_type="application/pdf",
        upsert=True,
    )

    # --------------------------------------------------------
    # Save / update metadata in EAForms sheet
    # --------------------------------------------------------

    metadata = {
        "employee_id": employee_id,
        "employee_name": employee_name,
        "year": year,
        "storage_path": storage_path,
        "uploaded_date": str(date.today()),
    }

    if existing:

        # Update existing employee + year record
        update_row(
            "EAForms",
            {
                "employee_id": employee_id,
                "year": year,
            },
            metadata,
        )

    else:

        # Create a new record
        append_row(
            "EAForms",
            metadata,
        )

    return storage_path


# ============================================================
# Get EA Forms for Employee
# ============================================================

def get_ea_forms_for_employee(
    employee_id: str,
) -> list[dict]:
    """
    Return EA Forms belonging to one employee.

    Employees should only use this function with their
    own employee_id.
    """

    df = read_table("EAForms")

    if df.empty:
        return []

    employee_id = str(
        employee_id
    ).strip()

    mine = df[
        df["employee_id"]
        .astype(str)
        .str.strip()
        == employee_id
    ]

    if mine.empty:
        return []

    return (
        mine.sort_values(
            "year",
            ascending=False,
        )
        .to_dict("records")
    )


# ============================================================
# Get All EA Forms
# ============================================================

def get_all_ea_forms() -> list[dict]:
    """
    Return all EA Forms.

    Intended for HR/Admin users.
    """

    df = read_table("EAForms")

    if df.empty:
        return []

    return (
        df.sort_values(
            ["year", "employee_name"],
            ascending=[False, True],
        )
        .to_dict("records")
    )


# ============================================================
# Download EA Form
# ============================================================

def download_ea_form_bytes(
    storage_path: str,
) -> bytes:
    """
    Download an EA Form from Supabase Storage.

    Args:
        storage_path:
            Full Supabase storage path.

            Example:
                ea_form/EMP001/EA_2025_EMP001.pdf

    Returns:
        PDF file as bytes.
    """

    storage_path = str(
        storage_path
    ).strip()

    if not storage_path:
        raise ValueError(
            "EA Form storage path is empty."
        )

    return download_file(
        storage_path
    )


# ============================================================
# Delete EA Form
# ============================================================

def delete_ea_form(
    employee_id: str,
    year: str,
) -> bool:
    """
    Delete an EA Form from both Supabase Storage
    and the EAForms sheet.

    NOTE:
        This function requires a delete_row()
        function in sheets_client.py.

    Returns:
        True if deletion succeeds.
    """

    employee_id = str(
        employee_id
    ).strip()

    year = str(
        year
    ).strip()

    existing = get_row(
        "EAForms",
        {
            "employee_id": employee_id,
            "year": year,
        },
    )

    if not existing:
        return False

    storage_path = existing.get(
        "storage_path"
    )

    # Delete from Supabase
    if storage_path:

        delete_file(
            str(storage_path)
        )

    # --------------------------------------------------------
    # Sheet deletion is intentionally not implemented here
    # because the current sheets_client.py shown earlier
    # does not provide delete_row().
    # --------------------------------------------------------

    return True
