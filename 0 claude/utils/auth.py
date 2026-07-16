"""
auth.py

Handles login, password hashing, first-login forced password reset,
and role-based access control. Login is completely independent from
Google accounts — credentials live in the Employees sheet.
"""
from __future__ import annotations


import streamlit as st
import bcrypt
from utils.sheets_client import read_table, update_row


def _persist_login_state(row: dict) -> None:
    st.session_state["logged_in"] = True
    st.session_state["employee_id"] = row["employee_id"]
    st.session_state["email"] = row["email"]
    st.session_state["name"] = row["name"]
    st.session_state["role"] = row["role"]
    st.session_state["force_password_reset"] = str(row.get("force_password_reset", "No")) in (
        "Yes", "yes", "True", "true", "1",
    )

    st.query_params["auth"] = "1"
    st.query_params["employee_id"] = row["employee_id"]
    st.query_params["email"] = row["email"]
    st.query_params["name"] = row["name"]
    st.query_params["role"] = row["role"]
    st.query_params["force_password_reset"] = "1" if st.session_state["force_password_reset"] else "0"


def restore_login_from_query() -> bool:
    if st.session_state.get("logged_in"):
        return True

    auth_flag = st.query_params.get("auth")
    employee_id = st.query_params.get("employee_id")
    email = st.query_params.get("email")
    role = st.query_params.get("role")

    if auth_flag != "1" or not employee_id or not email or not role:
        return False

    st.session_state["logged_in"] = True
    st.session_state["employee_id"] = employee_id
    st.session_state["email"] = email
    st.session_state["name"] = st.query_params.get("name", "")
    st.session_state["role"] = role
    st.session_state["force_password_reset"] = st.query_params.get("force_password_reset", "0") in (
        "1", "true", "True", "yes", "Yes",
    )
    return True


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except Exception:
        return False


def login(email: str, password: str) -> bool:
    df = read_table("Employees")
    if df.empty:
        return False

    match = df[df["email"].str.lower() == email.strip().lower()]
    if match.empty:
        return False

    row = match.iloc[0]

    if str(row.get("status", "")) != "Active":
        return False

    if not verify_password(password, str(row.get("password_hash", ""))):
        return False

    _persist_login_state(row)
    return True


def logout():
    for key in ["logged_in", "employee_id", "email", "name", "role", "force_password_reset"]:
        st.session_state.pop(key, None)

    for key in ["auth", "employee_id", "email", "name", "role", "force_password_reset"]:
        st.query_params.pop(key, None)


def require_login():
    """Call at the top of any page that requires the user to be logged in."""
    if not st.session_state.get("logged_in"):
        if restore_login_from_query():
            st.rerun()
        st.warning("Please log in first.")
        st.stop()
    if st.session_state.get("force_password_reset"):
        st.warning("You must set a new password before continuing. Go back to the home page.")
        st.stop()


def require_role(allowed_roles: list[str]):
    """Call at the top of a page restricted to certain roles."""
    require_login()
    if st.session_state.get("role") not in allowed_roles:
        st.error("You don't have permission to view this page.")
        st.stop()


def change_password(employee_id: str, new_password: str):
    new_hash = hash_password(new_password)
    update_row(
        "Employees",
        {"employee_id": employee_id},
        {"password_hash": new_hash, "force_password_reset": "No"},
    )
    st.session_state["force_password_reset"] = False
