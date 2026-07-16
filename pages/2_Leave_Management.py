import streamlit as st
from datetime import date
import pandas as pd

try:
    import altair as alt
except ImportError:
    alt = None

from utils.ui import inject_css, render_nav_sidebar
from utils.auth import require_role
from utils.sheets_client import read_table

try:
    from streamlit_calendar import calendar
    CALENDAR_AVAILABLE = True
except ImportError:
    CALENDAR_AVAILABLE = False

try:
    from utils.leave_calc import (
        get_pending_requests, get_all_pending_requests, get_all_requests,
        get_calendar_events, record_leave_request, approve_request, reject_request,
        delete_leave_request, get_monthly_approved_leave_headcount, get_employee_leave_summaries,
        get_leave_days_by_employee,
    )
except ImportError:
    from utils.leave_calc import get_pending_requests, get_all_pending_requests, approve_request, reject_request, delete_leave_request

    def get_leave_days_by_employee(year: int | None = None):
        import pandas as pd
        return pd.DataFrame()

    def record_leave_request(*args, **kwargs):
        raise ImportError("record_leave_request is not available")

    def get_monthly_approved_leave_headcount(year: int | None = None):
        from utils.sheets_client import read_table
        from utils.date_utils import parse_date
        from datetime import date as _date
        from collections import defaultdict

        df = read_table("LeaveRequests")
        if df.empty:
            return {}

        approved = df[df["status"] == "Approved"]
        month_employee_map = defaultdict(set)
        for _, row in approved.iterrows():
            try:
                start_date = parse_date(row["start_date"])
                end_date = parse_date(row["end_date"])
            except ValueError:
                continue
            if year is None:
                year = _date.today().year
            if end_date.year < year or start_date.year > year:
                if start_date.year != year and end_date.year != year:
                    continue
            current = max(start_date, _date(year, 1, 1))
            last_of_year = min(end_date, _date(year, 12, 31))
            while current <= last_of_year:
                month_key = (current.year, current.month)
                month_employee_map[month_key].add(str(row["employee_id"]))
                if current.month == 12:
                    current = _date(current.year + 1, 1, 1)
                else:
                    current = _date(current.year, current.month + 1, 1)
        return {f"{year}-{month:02d}": len(ids) for (year, month), ids in sorted(month_employee_map.items())}

    def get_employee_leave_summaries(year: int | None = None):
        from utils.sheets_client import read_table
        from utils.leave_rules import get_sick_leave_entitlement

        if year is None:
            year = date.today().year
        employees = read_table("Employees")
        balances = read_table("LeaveBalance")
        if employees.empty:
            return []
        balance_rows = {}
        if not balances.empty:
            balance_rows = {(str(row["employee_id"]), int(row["year"])): row for _, row in balances.iterrows()}
        summaries = []
        for _, employee in employees.iterrows():
            emp_id = str(employee["employee_id"])
            key = (emp_id, year)
            balance = balance_rows.get(key)
            annual_total = float(balance["annual_total"]) if balance is not None else 0.0
            annual_used = float(balance["annual_used"]) if balance is not None else 0.0
            annual_remaining = annual_total - annual_used
            sick_balance = float(balance["sick_balance"]) if balance is not None else 0.0
            sick_entitlement = 0.0
            medical_used = 0.0
            if balance is not None:
                try:
                    sick_entitlement = float(get_sick_leave_entitlement(employee["join_date"]))
                    medical_used = max(sick_entitlement - sick_balance, 0.0)
                except Exception:
                    sick_entitlement = sick_balance
                    medical_used = 0.0
            summaries.append({
                "employee_id": emp_id,
                "employee_name": employee.get("name", ""),
                "department": employee.get("department", ""),
                "annual_total": annual_total,
                "annual_used": annual_used,
                "annual_remaining": annual_remaining,
                "medical_used": medical_used,
                "sick_balance": sick_balance,
                "year": year,
            })
        return summaries

    def get_all_requests():
        from utils.sheets_client import read_table
        requests = read_table("LeaveRequests")
        if requests.empty:
            return []
        return requests.sort_values("submit_date", ascending=False).to_dict("records")

    def get_calendar_events():
        from utils.sheets_client import read_table
        from utils.date_utils import parse_date
        from datetime import timedelta

        df = read_table("LeaveRequests")
        if df.empty:
            return []
        approved = df[df["status"] == "Approved"]

        colors = {
            "Annual": "#5B8DEF",
            "Medical": "#F28C8C",
            "Unpaid": "#A8A8A8",
            "Maternity": "#B48AD9",
            "Hospitalization": "#F2B36D",
            "Special": "#7BCB9A",
        }
        events = []
        for _, row in approved.iterrows():
            end_exclusive = parse_date(row["end_date"]) + timedelta(days=1)
            events.append({
                "title": f"{row.get('employee_name', row['employee_id'])} - {row['leave_type']}",
                "start": str(row["start_date"]),
                "end": str(end_exclusive),
                "color": colors.get(row["leave_type"], "#2f80ed"),
            })
        return events

inject_css()
require_role(["hr_admin", "manager"])
render_nav_sidebar(st.session_state["role"])
st.title("Leave Management")

role = st.session_state["role"]
section = st.radio(
    "Section", ["Leave Approval", "Leave Calendar", "Record Leave", "Employee Leave History"],
    horizontal=True, label_visibility="collapsed",
)
st.divider()

# ---------- Record Leave ----------
if section == "Record Leave":
    view_mode = st.radio("View", ["Summary", "Record Leave"], horizontal=True, label_visibility="collapsed")

    if view_mode == "Summary":
        st.subheader("Leave Summary")
        month_counts = get_monthly_approved_leave_headcount(date.today().year)
        summaries = get_employee_leave_summaries(date.today().year)
        leave_by_employee = get_leave_days_by_employee(date.today().year)

        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("##### Leave Days per Employee (by type)")
            if leave_by_employee.empty:
                st.info("No approved leave yet this year.")
            else:
                if alt is not None:
                    long_df = leave_by_employee.reset_index().melt(
                        id_vars="employee_name", var_name="leave_type", value_name="days"
                    )
                    chart = alt.Chart(long_df).mark_bar().encode(
                        x=alt.X("employee_name:N", title="Employee", sort=None),
                        y=alt.Y("days:Q", title="Days"),
                        color=alt.Color("leave_type:N", title="Leave Type"),
                        tooltip=["employee_name", "leave_type", "days"],
                    )
                    st.altair_chart(chart, use_container_width=True)
                else:
                    st.bar_chart(leave_by_employee)

        with col_right:
            st.markdown("##### Employees on Leave per Month")
            if month_counts:
                summary_df = pd.DataFrame({
                    "month": list(month_counts.keys()),
                    "employees_on_leave": list(month_counts.values()),
                })
                if alt is not None:
                    pie = alt.Chart(summary_df).mark_arc(innerRadius=60).encode(
                        theta=alt.Theta(field="employees_on_leave", type="quantitative"),
                        color=alt.Color(field="month", type="nominal", legend=alt.Legend(title="Month")),
                        tooltip=["month", "employees_on_leave"],
                    )
                    st.altair_chart(pie, use_container_width=True)
                else:
                    st.bar_chart(summary_df.set_index("month")["employees_on_leave"])
            else:
                st.info("No approved leave requests yet.")

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        if summaries:
            summary_table = pd.DataFrame(summaries)[[
                "employee_name", "department", "annual_total", "annual_used",
                "annual_remaining", "medical_used", "unpaid_used"
            ]]
            summary_table = summary_table.rename(columns={
                "employee_name": "姓名",
                "department": "部门",
                "annual_total": "Annual Total",
                "annual_used": "Annual Used",
                "annual_remaining": "Annual Remaining",
                "medical_used": "Medical Used",
                "unpaid_used": "Unpaid Leave Taken",
            })
            st.markdown("#### 员工请假余额汇总")
            st.dataframe(summary_table, use_container_width=True)
        else:
            st.warning("没有员工数据可用于显示请假余额。")
    else:
        st.subheader("Record Leave for an Employee")
        employees = st.session_state.get("employees")
        if employees is None:
            from utils.sheets_client import read_table
            employees = read_table("Employees")

        if employees.empty:
            st.caption("No employees found to record leave for.")
        else:
            emp_map = dict(zip(employees["name"], employees["employee_id"]))
            selected_name = st.selectbox("Employee", list(emp_map.keys()))
            leave_type = st.selectbox("Leave Type", ["Annual", "Unpaid", "Medical", "Maternity", "Hospitalization", "Special"])
            col1, col2 = st.columns(2)
            start_date = col1.date_input("Start Date")
            end_date = col2.date_input("End Date")
            session = st.radio("Session", ["Full Day", "Half Day"], horizontal=True)
            reason = st.text_area("Reason")
            approved = st.checkbox("Mark as Approved immediately", value=True)
            submitted = st.button("Record Leave", use_container_width=True)

            if submitted:
                if end_date < start_date:
                    st.error("End date must be on or after the start date.")
                elif session == "Half Day" and start_date != end_date:
                    st.error("Half Day leave must start and end on the same date.")
                else:
                    try:
                        status = "Approved" if approved else "Pending"
                        request_id, days = record_leave_request(
                            emp_map[selected_name], leave_type, start_date, end_date,
                            reason, session, status=status, approved_by=st.session_state["email"],
                        )
                        st.success(
                            f"Leave request {request_id} recorded for {selected_name}. "
                            f"Duration: {days} day(s). Status: {status}."
                        )
                    except ValueError as e:
                        st.error(str(e))

elif section == "Leave Calendar":
    if not CALENDAR_AVAILABLE:
        st.error(
            "The streamlit-calendar package isn't installed in this environment. "
            "Run `pip install streamlit-calendar` and restart the app."
        )
    else:
        events = get_calendar_events()
        calendar_options = {
            "initialView": "dayGridMonth",
            "height": 650,
            "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,listMonth"},
            "dayMaxEvents": 3,
            "eventDisplay": "block",
            "displayEventTime": False,
        }
        calendar(events=events, options=calendar_options, key="leave_calendar")
        if not events:
            st.info(
                "The calendar grid above is empty because there are no Approved leave "
                "requests yet — it only shows requests once they're approved, not "
                "pending ones. Approve one in the 'Leave Approval' section to test it."
            )
        st.markdown(
            "<div style='margin-top: 0.5rem; line-height: 1.8; font-size: 0.95rem;'>"
            "🔵 Annual &nbsp;&nbsp; 🌸 Medical &nbsp;&nbsp; ⚪ Unpaid &nbsp;&nbsp; 🟣 Maternity &nbsp;&nbsp; "
            "🟠 Hospitalization &nbsp;&nbsp; 🟢 Special"
            "<br><span style='color: #64748b;'>Only approved requests are shown.</span>"
            "</div>",
            unsafe_allow_html=True,
        )

# ---------- Leave Approval ----------
elif section == "Leave Approval":
    if role == "hr_admin":
        pending = get_all_pending_requests()
    else:
        pending = get_pending_requests(st.session_state["email"])

    if not pending:
        st.caption("No pending requests.")
    for req in pending:
        st.markdown(
            "<div class='leave-approval-card'>"
            f"<h3>{req.get('employee_name', req['employee_id'])}</h3>"
            f"<div class='leave-approval-note'>{req.get('reason', 'No reason provided.')}</div>"
            "<div class='leave-approval-meta'>"
            f"<div><strong>Leave type</strong>{req['leave_type']}</div>"
            f"<div><strong>Start</strong>{req['start_date']}</div>"
            f"<div><strong>End</strong>{req['end_date']}</div>"
            f"<div><strong>Days</strong>{req['days']} day(s)</div>"
            f"<div><strong>Session</strong>{req.get('session', 'Full Day')}</div>"
            f"<div><strong>Status</strong>{req.get('status', 'Pending')}</div>"
            f"<div><strong>Requested on</strong>{req.get('submit_date', 'Unknown')}</div>"
            f"<div><strong>Employee ID</strong>{req['employee_id']}</div>"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        cols = st.columns([1, 1])
        with cols[0]:
            if st.button("Approve", key=f"appr_{req['request_id']}", use_container_width=True):
                approve_request(req["request_id"], st.session_state["email"])
                st.rerun()
        with cols[1]:
            if st.button("Reject", key=f"rej_{req['request_id']}", use_container_width=True):
                reject_request(req["request_id"], st.session_state["email"])
                st.rerun()

# ---------- Employee Leave History ----------
else:
    st.subheader("Employee Leave History")
    all_requests = get_all_requests()
    employees_df = read_table("Employees")

    if employees_df.empty:
        st.caption("No employees found.")
    else:
        emp_names = employees_df["name"].tolist()
        selected_emp_name = st.selectbox(
            "Select an employee to view their leave history", emp_names, key="history_emp_select"
        )
        selected_emp_id = employees_df[employees_df["name"] == selected_emp_name].iloc[0]["employee_id"]
        emp_requests = [r for r in all_requests if str(r.get("employee_id")) == str(selected_emp_id)]

        sub_view = st.radio("Sub-view", ["Pending", "History"], horizontal=True, label_visibility="collapsed")
        st.divider()

        if sub_view == "Pending":
            rows = [r for r in emp_requests if r["status"] == "Pending"]
        else:
            rows = [r for r in emp_requests if r["status"] != "Pending"]

        if not rows:
            st.caption(f"Nothing to show for {selected_emp_name}.")
        else:
            for req in rows:
                st.markdown(
                    "<div class='leave-approval-card'>"
                    f"<h4>{req.get('employee_name', req['employee_id'])}</h4>"
                    f"<div class='leave-approval-note'>{req.get('reason', 'No reason provided.')}</div>"
                    "<div class='leave-approval-meta'>"
                    f"<div><strong>Leave type</strong>{req['leave_type']}</div>"
                    f"<div><strong>Start</strong>{req['start_date']}</div>"
                    f"<div><strong>End</strong>{req['end_date']}</div>"
                    f"<div><strong>Days</strong>{req['days']} day(s)</div>"
                    f"<div><strong>Session</strong>{req.get('session', 'Full Day')}</div>"
                    f"<div><strong>Status</strong>{req.get('status', 'Unknown')}</div>"
                    f"<div><strong>Submitted</strong>{req.get('submit_date', 'Unknown')}</div>"
                    f"<div><strong>Approved by</strong>{req.get('approved_by', 'N/A')}</div>"
                    f"<div><strong>Request ID</strong>{req['request_id']}</div>"
                    "</div>"
                    "</div>",
                    unsafe_allow_html=True,
                )
                cols = st.columns([1, 3])
                with cols[0]:
                    if st.button(
                        "Delete Entry",
                        key=f"delete_{req['request_id']}",
                        use_container_width=True,
                    ):
                        if delete_leave_request(req["request_id"]):
                            st.success(f"Leave record {req['request_id']} deleted.")
                            st.rerun()
                        else:
                            st.error("Failed to delete the selected leave record.")
                with cols[1]:
                    st.caption("Use this button to remove an incorrectly entered or mistaken leave record.")
                st.divider()
            st.divider()