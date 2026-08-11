import streamlit as st
from utils.ui import inject_css, render_nav_sidebar
from utils.auth import require_login, change_password, logout
from utils.sheets_client import read_table, update_row

inject_css()
require_login()
render_nav_sidebar(st.session_state["role"])

employees = read_table("Employees")
me = employees[employees["employee_id"] == st.session_state["employee_id"]]

if me.empty:
    st.error("Could not find your employee record.")
    st.stop()

me = me.iloc[0]
initials = "".join([p[0] for p in str(me["name"]).split()[:2]]).upper() or "?"

# ---------- Header ----------
# Updated 7 Aug, 2026 - Add top padding so full profile name is visible below the page header
st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

st.markdown(
    f"""
    <div style="margin:0; padding:12px 0 4px 0;">
        <div style="display:flex; align-items:center; gap:10px; min-width:0;">
            <div style="width:42px; height:42px; border-radius:50%; background:#1e4a9e;
                        color:white; display:flex; align-items:center; justify-content:center;
                        font-size:1.3rem; font-weight:700; flex-shrink:0;">
                {initials}
            </div>
            <div style="min-width:0; flex:1;">
                <div style="font-size:1.25rem; font-weight:700; line-height:1.2; margin:0; padding:0;
                            overflow-wrap:anywhere; word-break:break-word;">
                    {me['name']}
                </div>
                <div style="font-size:0.95rem; color:#64748b; margin:0; padding:0;
                            overflow-wrap:anywhere; word-break:break-word;">
                    {st.session_state['role'].replace('_', ' ').title()} · {me.get('department', '-')}
                </div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.divider()

col_account, col_personal = st.columns(2, gap="large")

# ---------- Account Information ----------
with col_account:
    with st.container(border=True):
        st.markdown("#### 🔐 Account Information")
        st.write(f"**Username:** {me['email']}")
        st.write("**Password:** ••••••••••")

        with st.expander("Change Password"):
            with st.form("change_password_form"):
                new_password = st.text_input("New password", type="password")
                confirm_password = st.text_input("Confirm new password", type="password")
                submitted2 = st.form_submit_button("Update password")
            if submitted2:
                if new_password != confirm_password:
                    st.error("Passwords do not match.")
                elif len(new_password) < 8:
                    st.error("Password must be at least 8 characters.")
                else:
                    change_password(me["employee_id"], new_password)
                    st.success("Password updated.")

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("#### 💼 Employment Details")
        st.write(f"**Employee ID:** {me['employee_id']}")
        st.write(f"**Department:** {me.get('department', '-')}")
        st.write(f"**Join Date:** {me.get('join_date', '-')}")
        st.write(f"**Status:** {me.get('status', '-')}")
        st.write(f"**Income Tax No.:** {me.get('income_tax_no', '-') or '-'}")
        st.write(f"**EPF No.:** {me.get('epf_no', '-') or '-'}")

# ---------- Personal Details ----------
with col_personal:
    with st.container(border=True):
        st.markdown("#### 👤 Personal Details")
        st.write(f"**Full Name:** {me['name']}")
        st.write(f"**Email:** {me['email']}")
        st.write(f"**Phone Number:** {me.get('phone', '-')}")
        st.write(f"**Bank A/C:** {me.get('bank_account', '-') or '-'}")
        st.write(f"**Date of Birth:** {me.get('date_of_birth', '-')}")
        st.write(f"**Address:** {me.get('address', '-') or '-'}")

        with st.expander("Update Phone Number"):
            with st.form("update_phone_form"):
                new_phone = st.text_input("Phone", value=str(me.get("phone", "")))
                submitted = st.form_submit_button("Update phone")
            if submitted:
                update_row("Employees", {"employee_id": me["employee_id"]}, {"phone": new_phone})
                st.success("Updated.")
                st.rerun()

        with st.expander("Update Address"):
            with st.form("update_address_form"):
                new_address = st.text_area("Address", value=str(me.get("address", "")))
                submitted3 = st.form_submit_button("Update address")
            if submitted3:
                update_row("Employees", {"employee_id": me["employee_id"]}, {"address": new_address})
                st.success("Updated.")
                st.rerun()

# ---------- Quick Links ----------
st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
st.markdown("#### Quick Links")
lc1, lc2, lc3 = st.columns(3)
lc1.page_link("pages/8_Time.py", label="🗓️ View Leave History")
lc2.page_link("pages/6_Pay.py", label="💰 View Payslips")
if lc3.button("🚪  Logout", use_container_width=True):
    logout()
    st.rerun()
