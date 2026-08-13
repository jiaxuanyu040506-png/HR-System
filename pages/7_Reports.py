import streamlit as st
from datetime import date
from utils.ui import inject_css, render_nav_sidebar
from utils.auth import require_role
from utils.sheets_client import read_table

inject_css()
require_role(["hr_admin", "manager"])
render_nav_sidebar(st.session_state["role"])
st.title("Reports")
st.caption(
    "These are data summaries with CSV export, not formatted PDF reports — "
    "let me know if you need a polished printable report format instead."
)

employees = read_table("Employees")
leave_requests = read_table("LeaveRequests")
payslips = read_table("Payslips")

tab_employee, tab_leave, tab_payroll = st.tabs(["Employee Report", "Leave Report", "Payroll Report"])

with tab_employee:
    st.subheader("Employee Summary")
    total = len(employees)
    active = len(employees[employees["status"] == "Active"]) if not employees.empty else 0
    inactive = total - active
    this_month = date.today().strftime("%Y-%m")
    new_this_month = (
        employees[employees["join_date"].astype(str).str.startswith(this_month)].shape[0]
        if not employees.empty else 0
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Employees", total)
    c2.metric("Active Employees", active)
    c3.metric("Inactive Employees", inactive)
    c4.metric("New This Month", new_this_month)

    status_filter = st.selectbox("Filter by status", ["All", "Active", "Resigned"])
    filtered = employees if status_filter == "All" else employees[employees["status"] == status_filter]
    st.dataframe(filtered, use_container_width=True)
    if not filtered.empty:
        st.download_button("Export CSV", filtered.to_csv(index=False), file_name="employee_report.csv")

with tab_leave:
    st.subheader("Leave Summary")
    if leave_requests.empty:
        st.caption("No leave requests yet.")
    else:
        status_filter = st.selectbox("Filter by status", ["All", "Pending", "Approved", "Rejected"], key="leave_status")
        filtered = leave_requests if status_filter == "All" else leave_requests[leave_requests["status"] == status_filter]
        st.dataframe(filtered, use_container_width=True)
        st.download_button("Export CSV", filtered.to_csv(index=False), file_name="leave_report.csv")

with tab_payroll:
    st.subheader("Payroll Summary")
    if payslips.empty:
        st.caption("No payslips generated yet.")
    else:
        summary = payslips.groupby("month").agg(
            employees=("employee_id", "count"),
            total_net_pay=("net_pay", lambda s: s.astype(float).sum()),
        ).reset_index().sort_values("month", ascending=False)
        st.dataframe(summary, use_container_width=True)
        st.download_button("Export CSV", payslips.to_csv(index=False), file_name="payroll_report.csv")
