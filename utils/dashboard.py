"""
dashboard.py

Two distinct dashboard views, each with a single implementation reused
everywhere it's shown (keeping two hand-synced copies is exactly how
dead-link bugs crept in before):

  render_hr_dashboard()       -> "HR System > Dashboard" (hr_admin only):
                                  company-wide metrics and the approval
                                  queue. Work performance logging now
                                  lives on its own page (pages/10_Performance.py).

  render_personal_dashboard() -> "My Workspace > Dashboard": the exact
                                  same personal view for EVERYONE,
                                  hr_admin included — their own leave
                                  balance, latest payslip, quick access,
                                  and the read-only Performance chart
                                  (no logging form here).
"""
from __future__ import annotations

import streamlit as st
from datetime import date
from utils.sheets_client import read_table
from utils.leave_calc import get_leave_balance, get_all_pending_requests, get_today_on_leave_count, \
    approve_request, reject_request
from utils.performance import get_completed_counts_by_employee, get_assigned_vs_completed, get_employee_company_list, get_employee_performance_summary, get_employee_late_companies


def _quick_access_button(col, label: str, icon: str, target_page: str):
    """A button that jumps straight to another page on click (st.switch_page),
    instead of a plain link — matches the 'click Time, jump straight to Time' spec."""
    if col.button(f"{icon}  {label}", use_container_width=True):
        st.switch_page(target_page)


# Updated 24 July, 2026
def render_performance_chart(selected_employee=None):
    if selected_employee:
        st.markdown(f"##### {selected_employee}'s Performance")

        df = read_table("PerformanceRecords")
        employee_df = df[df["employee_name"] == selected_employee]
        total = len(employee_df)
        completed = len(employee_df[employee_df["completion_date"] != ""])
        on_time = len(employee_df[employee_df["status"] == "On Time"])
        late = len(employee_df[employee_df["status"] == "Late"])

        # summary = get_employee_performance_summary(selected_employee)
        c1, c2, c3 = st.columns(3)

        c1.metric("Total Companies", total)
        c2.metric("On Time", on_time)
        c3.metric("Late", late)

        st.divider()
        st.markdown("##### Late Companies")
        late_companies = get_employee_late_companies(selected_employee)
        if late_companies.empty:
            st.success("No late records 🎉")
        else:
            st.dataframe(late_companies,hide_index=True,use_container_width=True)

        st.divider()

        st.markdown("##### Company List")
        companies = get_employee_company_list(selected_employee)

        if not companies.empty:
            st.dataframe(companies, hide_index=True, use_container_width=True,)
        else:
            st.info("No completed companies.")


# def render_performance_chart(selected_employee=None):
#     # st.subheader("🏆 Performance — Completed Tasks by Employee")
#     if selected_employee:
#         st.markdown(
#             f"##### {selected_employee}'s Performance"
#         )
#         companies = get_employee_company_list(
#             selected_employee
#         )
#         st.markdown(
#             "##### Assigned Company List"
#         )

#         if not companies.empty:
#             st.dataframe(
#                 companies,
#                 hide_index=True,
#                 use_container_width=True
#             )
#         else:
#             st.info(
#                 "No assigned companies."
#             )

#         performance_df = get_assigned_vs_completed()
#         if (
#             not performance_df.empty
#             and selected_employee in performance_df.index
#         ):
#             employee_perf = performance_df.loc[
#                 [selected_employee]
#             ]
#             st.bar_chart(
#                 employee_perf
#             )
#     else:
#         counts = get_completed_counts_by_employee()
#         if not counts.empty:
#             st.bar_chart(counts)

def _greeting():
    name = st.session_state["name"]
    st.title(f"Good morning, {name} 👋")
    st.caption(date.today().strftime("%A, %d %B %Y"))
    st.divider()


def render_hr_dashboard():
    _greeting()

    employees = read_table("Employees")
    active_employees = employees[employees["status"] == "Active"] if not employees.empty else employees
    pending = get_all_pending_requests()
    today_on_leave = get_today_on_leave_count()

    c1, c2, c3 = st.columns(3)
    c1.container(border=True).metric("Total Employees", len(active_employees))
    c2.container(border=True).metric("Pending Leaves", len(pending))
    c3.container(border=True).metric("Today's Leaves", today_on_leave)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    lcol, bcol = st.columns([4, 1])
    lcol.subheader("Leave Approval Queue")
    if bcol.button("View All →", use_container_width=True):
        st.switch_page("pages/2_Leave_Management.py")

    if not pending:
        st.info("Nothing pending — all caught up.")
    else:
        for req in pending[:5]:
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 1, 1])
                col1.write(
                    f"**{req.get('employee_name', req['employee_id'])}** · {req['leave_type']} · "
                    f"{req['start_date']} → {req['end_date']} ({req['days']} day(s))"
                )
                if col2.button("Approve", key=f"dash_a_{req['request_id']}", use_container_width=True):
                    approve_request(req["request_id"], st.session_state["email"])
                    st.rerun()
                if col3.button("Reject", key=f"dash_r_{req['request_id']}", use_container_width=True):
                    reject_request(req["request_id"], st.session_state["email"])
                    st.rerun()

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    st.subheader("Quick Links")
    lc1, lc2, lc3, lc4 = st.columns(4)
    _quick_access_button(lc1, "All Employees", "👥", "pages/1_Employee_Management.py")
    _quick_access_button(lc2, "Leave Approvals", "🗓️", "pages/2_Leave_Management.py")
    _quick_access_button(lc3, "Payroll", "💰", "pages/5_Payroll_Management.py")
    _quick_access_button(lc4, "Performance", "📌", "pages/10_Performance.py")

    st.caption(
        "Not shown yet: announcements, activity feed, upcoming birthdays, and "
        "employee distribution by department — these need new data/fields that "
        "don't exist in the system yet."
    )


def render_personal_dashboard(role: str):
    _greeting()

    employee_id = st.session_state["employee_id"]
    year = date.today().year
    balance = get_leave_balance(employee_id, year)
    payslips = read_table("Payslips")
    my_payslips = payslips[payslips["employee_id"] == employee_id] if not payslips.empty else payslips

    c1, c2 = st.columns(2)
    if balance:
        remaining = int(balance["annual_total"]) - float(balance["annual_used"])
        c1.container(border=True).metric("Remaining Annual Leave", f"{remaining} days")
    else:
        c1.container(border=True).metric("Remaining Annual Leave", "—")

    if not my_payslips.empty:
        latest = my_payslips.sort_values("month", ascending=False).iloc[0]
        c2.container(border=True).metric("Latest Payslip", latest["month"])
    else:
        c2.container(border=True).metric("Latest Payslip", "—")

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    st.subheader("Quick Access")
    lc1, lc2, lc3 = st.columns(3)
    _quick_access_button(lc1, "Time", "🗓️", "pages/8_Time.py")
    _quick_access_button(lc2, "Pay", "💰", "pages/6_Pay.py")
    _quick_access_button(lc3, "My Profile", "👤", "pages/4_My_Profile.py")

    # ---------- Performance (read-only view, everyone sees the same chart) ----------
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    render_performance_chart()

    st.caption("Not shown yet: announcements and recent activity feed.")
