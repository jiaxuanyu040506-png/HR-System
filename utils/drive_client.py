"""
drive_client.py

Handles uploading/downloading files (currently: EA Forms) to/from Google
Drive, using the same service account as sheets_client.py. Files are NOT
stored on local disk — Streamlit Cloud wipes local disk on every restart,
so anything that needs to persist across sessions goes to Drive instead.

Requires the "drive.file" scope (see utils/sheets_client.py SCOPES) —
this only grants access to files the app itself creates, not your whole
Drive, which is the safer option for a service account.
"""
from __future__ import annotations

import io
import streamlit as st
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from utils.sheets_client import get_client

@st.cache_resource
def get_drive_service():
    # Reuse the same authorized credentials gspread already built.
    creds = get_client().auth
    return build("drive", "v3", credentials=creds)

def upload_file(file_bytes: bytes, filename: str, mime_type: str = "application/pdf") -> str:
    """Upload a file to Drive and return its file_id."""
    service = get_drive_service()
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=False)
    file_metadata = {"name": filename}
    created = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    return created["id"]

def download_file(file_id: str) -> bytes:
    """Download a file's bytes from Drive by its file_id."""
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()

def delete_file(file_id: str):
    """Delete a file from Drive by its file_id (used when replacing an EA Form)."""
    service = get_drive_service()
    try:
        service.files().delete(fileId=file_id).execute()
    except Exception:
        pass  # already gone or inaccessible — not worth blocking the user's action over