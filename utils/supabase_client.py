"""
supabase_client.py

Centralized Supabase Storage client for the HR System.

Bucket:
    hr-documents

Storage structure:
    mc/{employee_id}/{filename}
    ea_form/{employee_id}/{filename}
    payslip/{employee_id}/{filename}
"""

from __future__ import annotations

import streamlit as st
from supabase import create_client


# ============================================================
# Configuration
# ============================================================

BUCKET_NAME = "employee-documents"


# ============================================================
# Supabase Client
# ============================================================

@st.cache_resource
def get_supabase_client():
    """
    Create and cache the Supabase client.
    """

    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"],
    )


# ============================================================
# Upload
# ============================================================

def upload_file(
    file_bytes: bytes,
    file_path: str,
    mime_type: str = "application/pdf",
    upsert: bool = True,
):
    """
    Upload a file to Supabase Storage.
    """

    supabase = get_supabase_client()

    return (
        supabase.storage
        .from_(BUCKET_NAME)
        .upload(
            file_path,
            file_bytes,
            {
                "content-type": mime_type,
                "upsert": str(upsert).lower(),
            },
        )
    )

# ============================================================
# Download
# ============================================================

def download_file(
    file_path: str,
) -> bytes:
    """
    Download a file from Supabase Storage.

    Args:
        file_path:
            Full storage path.

    Returns:
        File content as bytes.
    """

    supabase = get_supabase_client()

    return (
        supabase.storage
        .from_(BUCKET_NAME)
        .download(file_path)
    )


# ============================================================
# Delete
# ============================================================

def delete_file(
    file_path: str,
):
    """
    Delete a file from Supabase Storage.

    Args:
        file_path:
            Full storage path.

    Returns:
        Supabase delete response.
    """

    supabase = get_supabase_client()

    return (
        supabase.storage
        .from_(BUCKET_NAME)
        .remove([file_path])
    )


# ============================================================
# Replace
# ============================================================

def replace_file(
    file_bytes: bytes,
    file_path: str,
    mime_type: str = "application/pdf",
):
    """
    Replace an existing file.

    This is simply an upload with upsert=True.
    """

    return upload_file(
        file_bytes=file_bytes,
        file_path=file_path,
        mime_type=mime_type,
        upsert=True,
    )

