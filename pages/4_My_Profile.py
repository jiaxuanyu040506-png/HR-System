import streamlit as st
from utils.ui import inject_css, render_nav_sidebar
from utils.auth import require_login, change_password, logout
from utils.sheets_client import read_table, update_row


# INITIALIZE
inject_css()
require_login()
render_nav_sidebar(st.session_state["role"])

# LOAD EMPLOYEE
employees = read_table("Employees")

me = employees[employees["employee_id"] == st.session_state["employee_id"]]
if me.empty:
    st.error("Could not find your employee record.")
    st.stop()
me = me.iloc[0]


# PROFILE HEADER
initials = "".join([p[0] for p in str(me["name"]).split()[:2]]).upper() or "?"
st.html('<div class="spacer-md"></div>')
st.html(
    f"""
    <div class="profile-shell">
        <div class="profile-header">
            <div class="profile-avatar">{initials}</div>
            <div class="profile-meta">
                <div class="profile-name">{me['name']}</div>
                <div class="profile-role">
                    {st.session_state['role'].replace('_', ' ').title()}
                    ·
                    {me.get('department', '-')}
                </div>
            </div>
        </div>
    </div>
    """
)
st.divider()

# ACCOUNT + PERSONAL INFORMATION
col_account, col_personal = st.columns(2, gap="large")

# ACCOUNT INFORMATION
with col_account:
    with st.container(border=True):
        st.html(
            """
            <div class="panel-title">🔐 Account Information</div>
            """
        )

        st.write(f"**Username:** {me['email']}")
        st.write("**Password:** ••••••••••")

        # Change Password
        with st.expander("Change Password"):
            with st.form("change_password_form"):
                new_password = st.text_input("New password", type="password")
                confirm_password = st.text_input("Confirm new password", type="password") 
                submitted_password = st.form_submit_button("Update password", use_container_width=True)

            if submitted_password:
                if not new_password:
                    st.error("Please enter a new password.")
                elif new_password != confirm_password:
                    st.error("Passwords do not match.")
                elif len(new_password) < 8:
                    st.error("Password must be at least 8 characters.")
                else:
                    change_password(me["employee_id"], new_password)
                    st.success("Password updated successfully.")

    # Employment Details
    st.html('<div class="spacer-sm"></div>')
    with st.container(border=True):
        st.html(
            """
            <div class="panel-title">💼 Employment Details</div>
            """
        )

        st.write(f"**Employee ID:** {me['employee_id']}")
        st.write(f"**Department:** {me.get('department', '-')}")
        st.write(f"**Join Date:** {me.get('join_date', '-')}")
        st.write(f"**Status:** {me.get('status', '-')}")
        st.write(f"**Income Tax No.:** " f"{me.get('income_tax_no', '-') or '-'}")
        st.write(f"**EPF No.:** " f"{me.get('epf_no', '-') or '-'}")

# PERSONAL DETAILS
with col_personal:
    with st.container(border=True):
        st.html(
            """
            <div class="panel-title">👤 Personal Details</div>
            """
        )

        st.write(f"**Full Name:** {me['name']}")
        st.write(f"**Email:** {me['email']}")
        st.write(f"**Phone Number:** " f"{me.get('phone', '-') or '-'}")
        st.write(f"**Bank A/C:** " f"{me.get('bank_account', '-') or '-'}")
        st.write(f"**Date of Birth:** " f"{me.get('date_of_birth', '-') or '-'}")
        st.write(f"**Address:** " f"{me.get('address', '-') or '-'}")

        # Update Phone
        with st.expander("Update Phone Number"):
            with st.form("update_phone_form"):
                new_phone = st.text_input("Phone", value=str(me.get("phone", "") or ""))
                submitted_phone = st.form_submit_button("Update phone", use_container_width=True)

            if submitted_phone:
                update_row("Employees",
                    {"employee_id": me["employee_id"]},
                    {"phone": new_phone.strip()})
                st.success("Phone number updated.")
                st.rerun()

        # Update Address
        with st.expander("Update Address"):
            with st.form("update_address_form"):
                new_address = st.text_area("Address", value=str(me.get("address", "") or ""), height=100)
                submitted_address = st.form_submit_button("Update address",use_container_width=True)

            if submitted_address:
                update_row(
                    "Employees", {"employee_id": me["employee_id"]},
                    { "address": new_address.strip()})
                st.success("Address updated.")
                st.rerun()

# LOGOUT
st.html('<div class="spacer-lg"></div>')
with st.container(border=True):
    logout_col1, logout_col2 = st.columns([4, 1])
    with logout_col1:
        st.html(
            """
            <div class="panel-title panel-title-compact">🚪 Sign Out</div>
            <div class="muted-text">Sign out of your employee account.</div>
            """
        )

    with logout_col2:
        if st.button("Logout",use_container_width=True):
            logout()
            st.rerun()