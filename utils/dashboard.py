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
import pandas as pd
from datetime import date
from utils.sheets_client import read_table
from utils.leave_calc import get_leave_balance, get_all_pending_requests, get_today_on_leave_count, \
    approve_request, reject_request, get_my_requests
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

def _greeting():
    name = st.session_state["name"]
    st.title(f"Good morning, {name} 👋")
    st.caption(date.today().strftime("%A, %d %B %Y"))
    st.divider()

def render_hr_dashboard():
    _greeting()

    employees = read_table("Employees")
    active_employees = (
        employees[employees["status"] == "Active"]
        if not employees.empty
        else employees
    )

    pending = get_all_pending_requests()
    today_on_leave = get_today_on_leave_count()

    # KPI CARDS
    c1, c2, c3 = st.columns(3)

    with c1:
        st.html(
            f"""
            <div style="
                border:1px solid #e2e8f0;
                border-radius:14px;
                padding:18px 20px;
                background:#ffffff;
                min-height:120px;
                box-shadow:0 2px 8px rgba(15,23,42,0.03);
            ">
                <div style="
                    font-size:0.9rem;
                    color:#64748b;
                    font-weight:600;
                    margin-bottom:10px;
                ">
                    👥 Total Employees
                </div>

                <div style="
                    font-size:1.9rem;
                    font-weight:700;
                    color:#172033;
                    line-height:1.1;
                ">
                    {len(active_employees)}
                </div>

                <div style="
                    font-size:0.82rem;
                    color:#64748b;
                    margin-top:7px;
                ">
                    active employees
                </div>
            </div>
            """
        )

    with c2:
        st.html(
            f"""
            <div style="
                border:1px solid #e2e8f0;
                border-radius:14px;
                padding:18px 20px;
                background:#ffffff;
                min-height:120px;
                box-shadow:0 2px 8px rgba(15,23,42,0.03);
            ">
                <div style="
                    font-size:0.9rem;
                    color:#64748b;
                    font-weight:600;
                    margin-bottom:10px;
                ">
                    🕐 Pending Leaves
                </div>

                <div style="
                    font-size:1.9rem;
                    font-weight:700;
                    color:#172033;
                    line-height:1.1;
                ">
                    {len(pending)}
                </div>

                <div style="
                    font-size:0.82rem;
                    color:#64748b;
                    margin-top:7px;
                ">
                    awaiting approval
                </div>
            </div>
            """
        )

    with c3:
        st.html(
            f"""
            <div style="
                border:1px solid #e2e8f0;
                border-radius:14px;
                padding:18px 20px;
                background:#ffffff;
                min-height:120px;
                box-shadow:0 2px 8px rgba(15,23,42,0.03);
            ">
                <div style="
                    font-size:0.9rem;
                    color:#64748b;
                    font-weight:600;
                    margin-bottom:10px;
                ">
                    🗓️ Today's Leaves
                </div>
                <div style="
                    font-size:1.9rem;
                    font-weight:700;
                    color:#172033;
                    line-height:1.1;
                ">
                    {today_on_leave}
                </div>
                <div style="
                    font-size:0.82rem;
                    color:#64748b;
                    margin-top:7px;
                ">
                    employees on leave today
                </div>
            </div>
            """
        )

    # LEAVE APPROVAL QUEUE
    st.html("<div style='height:24px'></div>")
    lcol, bcol = st.columns([4, 1])
    with lcol:
        st.html(
            """
            <div style="
                font-size:1.35rem;
                font-weight:700;
                color:#172033;
                margin-bottom:4px;
            ">
                Leave Approval Queue
            </div>
            """
        )

    with bcol:
        if st.button(
            "View All →",
            use_container_width=True,
            key="hr_view_all_leaves",
        ):
            st.switch_page("pages/2_Leave_Management.py")

    if not pending:

        with st.container(border=True):

            st.html(
                """
                <div style="
                    padding:8px 0;
                    text-align:center;
                ">
                    <div style="
                        font-size:1.8rem;
                        margin-bottom:6px;
                    ">
                        ✅
                    </div>
                    <div style="
                        font-size:1rem;
                        font-weight:600;
                        color:#172033;
                    ">
                        Nothing pending
                    </div>
                    <div style="
                        font-size:0.85rem;
                        color:#64748b;
                        margin-top:3px;
                    ">
                        All leave requests are up to date.
                    </div>
                </div>
                """
            )

    else:
        for req in pending[:5]:

            with st.container(border=True):

                col1, col2, col3 = st.columns([3, 1, 1])

                with col1:
                    st.html(
                        f"""
                        <div style="
                            padding:4px 0;
                        ">
                            <div style="
                                font-size:1rem;
                                font-weight:700;
                                color:#172033;
                                margin-bottom:5px;
                            ">
                                {req.get('employee_name', req['employee_id'])}
                            </div>
                            <div style="
                                font-size:0.88rem;
                                color:#64748b;
                                line-height:1.5;
                            ">
                                {req['leave_type']}
                                ·
                                {req['start_date']} → {req['end_date']}
                                ·
                                {req['days']} day(s)
                            </div>
                        </div>
                        """
                    )

                with col2:
                    if st.button("Approve",key = f"dash_a_{req['request_id']}", use_container_width=True,):
                        approve_request(req["request_id"], st.session_state["email"],)
                        st.rerun()

                with col3:
                    if st.button("Reject", key=f"dash_r_{req['request_id']}", use_container_width=True,):
                        reject_request(req["request_id"], st.session_state["email"],)
                        st.rerun()

    # QUICK ACCESS
    st.html("<div style='height:26px'></div>")
    st.html(
        """
        <div style="
            font-size:1.35rem;
            font-weight:700;
            color:#172033;
            margin-bottom:12px;
        ">
            Quick Access
        </div>
        """
    )

    q1, q2, q3, q4 = st.columns(4)
    _quick_access_button(q1, "All Employees", "👥", "pages/1_Employee_Management.py")
    _quick_access_button(q2, "Leave Approvals", "🗓️", "pages/2_Leave_Management.py",)
    _quick_access_button(q3, "Payroll", "💰", "pages/5_Payroll_Management.py",)
    _quick_access_button(q4, "Performance", "📌", "pages/10_Performance.py",)

# HELPER FUNCTIONS
def _format_days(value):
    """Display whole numbers without .0."""
    try:
        value = float(value or 0)

        if value.is_integer():
            return str(int(value))

        return f"{value:.1f}"

    except Exception:
        return "0"

def _format_date(value):
    """Convert date into friendly format."""
    if value is None or value == "":
        return "—"

    try:
        return pd.to_datetime(value).strftime("%d %b %Y")

    except Exception:
        return str(value)

def _status_badge(status):
    """Return HTML status badge."""

    status = str(status or "Unknown")
    status_lower = status.lower()

    if status_lower == "approved":
        return """
        <span style="
            background:#dcfce7;
            color:#166534;
            padding:5px 11px;
            border-radius:999px;
            font-size:0.78rem;
            font-weight:600;
        ">
            ✓ Approved
        </span>
        """

    elif status_lower == "pending":
        return """
        <span style="
            background:#fef3c7;
            color:#92400e;
            padding:5px 11px;
            border-radius:999px;
            font-size:0.78rem;
            font-weight:600;
        ">
            ◷ Pending
        </span>
        """

    elif status_lower == "rejected":
        return """
        <span style="
            background:#fee2e2;
            color:#991b1b;
            padding:5px 11px;
            border-radius:999px;
            font-size:0.78rem;
            font-weight:600;
        ">
            ✕ Rejected
        </span>
        """

    return f"""
    <span style="
        background:#f1f5f9;
        color:#475569;
        padding:5px 11px;
        border-radius:999px;
        font-size:0.78rem;
        font-weight:600;
    ">
        {status}
    </span>
    """

# PERSONAL DASHBOARD
def render_personal_dashboard(role: str):
    st.html(
        """
        <style>

        /* ---------------------------------------------------
           Welcome Banner
        --------------------------------------------------- */
        .dashboard-welcome {
            background: linear-gradient(
                135deg,
                #f8fbff 0%,
                #eef6ff 100%
            );
            border: 1px solid #dbeafe;
            border-radius: 16px;
            padding: 20px 22px;
            margin-bottom: 22px;
        }

        .dashboard-welcome-title {
            font-size: 1.35rem;
            font-weight: 700;
            color: #172033;
            margin-bottom: 5px;
        }

        .dashboard-welcome-text {
            font-size: 0.92rem;
            color: #64748b;
            line-height: 1.5;
        }

        /* ---------------------------------------------------
           Section Title
        --------------------------------------------------- */
        .dashboard-section-title {
            font-size: 1.15rem;
            font-weight: 700;
            color: #172033;
            margin-top: 4px;
            margin-bottom: 12px;
        }

        /* ---------------------------------------------------
           KPI Cards
        --------------------------------------------------- */
        .dashboard-kpi {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 16px;
            padding: 18px 19px;
            min-height: 125px;
            box-shadow:
                0 4px 14px rgba(15, 23, 42, 0.035);
        }

        .dashboard-kpi-label {
            font-size: 0.84rem;
            color: #64748b;
            font-weight: 600;
            margin-bottom: 9px;
        }

        .dashboard-kpi-value {
            font-size: 1.65rem;
            font-weight: 700;
            color: #172033;
            line-height: 1.2;
            margin-bottom: 5px;
        }

        .dashboard-kpi-sub {
            font-size: 0.78rem;
            color: #94a3b8;
        }

        /* ---------------------------------------------------
           Quick Access
        --------------------------------------------------- */
        .dashboard-quick-card {
            position: relative;
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 16px;
            padding: 18px;
            min-height: 105px;
            box-shadow: 0 4px 14px rgba(15, 23, 42, 0.035);
            transition: 0.2s ease;
        }

        .dashboard-quick-icon {
            font-size: 1.45rem;
            margin-bottom: 10px;
        }

        .dashboard-quick-title {
            font-size: 0.98rem;
            font-weight: 650;
            color: #172033;
        }

        .dashboard-quick-arrow {
            position: absolute;
            right: 16px;
            bottom: 14px;
            color: #94a3b8;
            font-size: 1.1rem;
        }

        /* ---------------------------------------------------
           Upcoming Leave Card
        --------------------------------------------------- */
        .dashboard-leave-card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 16px;
            padding: 17px 18px;
            margin-bottom: 10px;
            box-shadow: 0 4px 14px rgba(15, 23, 42, 0.035);
        }

        .dashboard-leave-type {
            font-size: 0.96rem;
            font-weight: 650;
            color: #172033;
            margin-bottom: 4px;
        }

        .dashboard-leave-date {
            font-size: 0.83rem;
            color: #64748b;
        }

        .dashboard-leave-days {
            font-size: 0.82rem;
            color: #94a3b8;
            margin-top: 4px;
        }

        /* ---------------------------------------------------
           Recent Requests
        --------------------------------------------------- */
        .dashboard-request-card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 14px 16px;
            margin-bottom: 9px;
        }

        .dashboard-request-title {
            font-size: 0.9rem;
            font-weight: 650;
            color: #172033;
        }

        .dashboard-request-date {
            font-size: 0.78rem;
            color: #64748b;
            margin-top: 3px;
        }

        /* ---------------------------------------------------
           Reminder
        --------------------------------------------------- */
        .dashboard-reminder {
            background: #fff5f5;
            border: 1px solid #fecaca;
            border-radius: 14px;
            padding: 14px 17px;
            color: #991b1b;
            font-size: 0.9rem;
            line-height: 1.5;
            margin-top: 4px;
        }

        /* ---------------------------------------------------
           Company Notice
        --------------------------------------------------- */
        .dashboard-notice {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 16px 18px;
            color: #475569;
            font-size: 0.88rem;
            line-height: 1.5;
        }

        .dashboard-notice-title {
            color: #172033;
            font-weight: 650;
            margin-bottom: 5px;
        }

        /* ---------------------------------------------------
           Streamlit Button
        --------------------------------------------------- */
        .dashboard-quick-card + div button {
            margin-top: -4px;
            border-radius: 10px;
        }
        </style>
        """
    )

    employee_id = st.session_state["employee_id"]

    employee_name = st.session_state.get("name",
        st.session_state.get("employee_name", "Employee"))
    
    year = date.today().year

    # GET EMPLOYEE DATA
    try:
        employees = read_table("Employees")
        employee_df = employees[employees["employee_id"].astype(str) == str(employee_id)]
        if not employee_df.empty:
            employee_name = employee_df.iloc[0].get("name", employee_name)

    except Exception:
        pass

    # LEAVE BALANCE
    balance = get_leave_balance(employee_id, year)
    if balance:
        annual_total = float(balance.get("annual_total", 0) or 0)
        annual_used = float(balance.get("annual_used", 0) or 0)
        annual_remaining = max(annual_total - annual_used, 0)

        medical_total = float(balance.get("medical_total", 0) or 0)
        medical_used = float(balance.get("medical_used", 0) or 0)
        medical_remaining = max(medical_total - medical_used, 0)
    else:
        annual_total = 0
        annual_used = 0
        annual_remaining = 0

        medical_total = 0
        medical_used = 0
        medical_remaining = 0

    # PAYSLIPS
    try:
        payslips = read_table("Payslips")
        if not payslips.empty:
            my_payslips = payslips[payslips["employee_id"].astype(str) == str(employee_id)]
        else:
            my_payslips = payslips

    except Exception:
        my_payslips = pd.DataFrame()

    # LEAVE REQUESTS
    try:
        my_requests = get_my_requests(employee_id)
    except Exception:
        my_requests = []

    requests_df = pd.DataFrame(my_requests) if my_requests else pd.DataFrame()

    # WELCOME
    current_hour = date.today()

    # Keep greeting simple and neutral
    greeting = "Welcome back"
    st.html(
        f"""
        <div class="dashboard-welcome">
            <div class="dashboard-welcome-title">
                {greeting}, {employee_name} 👋
            </div>
            <div class="dashboard-welcome-text">
                Here's a quick overview of your leave,
                payroll, and recent activity.
            </div>
        </div>
        """
    )

    # AT A GLANCE
    st.html(
        """
        <div class="dashboard-section-title">
            At a Glance
        </div>
        """
    )

    c1, c2, c3 = st.columns(3)
    # Annual Leave
    with c1:
        st.html(
            f"""
            <div class="dashboard-kpi">
                <div class="dashboard-kpi-label">
                    🏖️ Annual Leave
                </div>
                <div class="dashboard-kpi-value">
                    {_format_days(annual_remaining)} days
                </div>
                <div class="dashboard-kpi-sub">
                    remaining in {year}
                </div>
            </div>
            """
        )

    # Medical Leave
    with c2:
        st.html(
            f"""
            <div class="dashboard-kpi">
                <div class="dashboard-kpi-label">
                    🩺 Medical Leave
                </div>
                <div class="dashboard-kpi-value">
                    {_format_days(medical_remaining)} days
                </div>
                <div class="dashboard-kpi-sub">
                    remaining in {year}
                </div>
            </div>
            """
        )

    # Latest Payslip
    with c3:
        if not my_payslips.empty:
            try:
                latest = (my_payslips.sort_values("month", ascending=False).iloc[0])
                latest_month = str(latest.get("month", "—"))
            except Exception:
                latest_month = "—"
        else:
            latest_month = "—"

        st.html(
            f"""
            <div class="dashboard-kpi">
                <div class="dashboard-kpi-label">
                    💰 Latest Payslip
                </div>
                <div class="dashboard-kpi-value">
                    {latest_month}
                </div>
                <div class="dashboard-kpi-sub">
                    view and download from Pay
                </div>
            </div>
            """
        )

    # QUICK ACCESS
    st.html("<div style='height:26px'></div>")
    st.html(
        """
        <div class="dashboard-section-title">
            Quick Access
        </div>
        """
    )

    q1, q2, q3 = st.columns(3)
    _quick_access_button(q1, "Time", "🗓️", "pages/8_Time.py",)
    _quick_access_button(q2, "Pay", "💰", "pages/6_Pay.py",)
    _quick_access_button(q3, "My Profile", "👤", "pages/4_My_Profile.py",)
   
    # UPCOMING LEAVE + RECENT REQUESTS
    st.html("<div style='height:28px'></div>")
    left_col, right_col = st.columns([1.15, 1],gap="large")

    # UPCOMING LEAVE
    with left_col:
        st.html(
            """
            <div class="dashboard-section-title">
                Upcoming Leave
            </div>
            """
        )

        upcoming = pd.DataFrame()
        if not requests_df.empty:
            temp = requests_df.copy()
            try:
                temp["parsed_start"] = pd.to_datetime(temp["start_date"], errors="coerce")
                upcoming = temp[
                    (temp["parsed_start"] >= pd.Timestamp.today().normalize()) &
                    (temp["status"].astype(str).str.lower() == "approved")].sort_values("parsed_start").head(3)

            except Exception:
                upcoming = pd.DataFrame()

        if upcoming.empty:
            st.html(
                """
                <div class="dashboard-notice">
                    <div class="dashboard-notice-title">
                        No upcoming leave
                    </div>
                    You don't have any approved leave coming up.
                </div>
                """
            )

        else:
            for _, row in upcoming.iterrows():
                leave_type = str(row.get("leave_type", "Leave"))
                start = _format_date(row.get("start_date"))
                end = _format_date(row.get("end_date"))
                days = _format_days(row.get("days", 0))

                if start == end:
                    date_text = start
                else:
                    date_text = (f"{start} → {end}")

                st.html(
                    f"""
                    <div class="dashboard-leave-card">
                        <div class="dashboard-leave-type">
                            {leave_type}
                        </div>
                        <div class="dashboard-leave-date">
                            📅 {date_text}
                        </div>
                        <div class="dashboard-leave-days">
                            {days} day(s)
                        </div>
                    </div>
                    """
                )

    # RECENT REQUESTS
    with right_col:
        st.html(
            """
            <div class="dashboard-section-title">
                Recent Leave Requests
            </div>
            """
        )

        if requests_df.empty:
            st.html(
                """
                <div class="dashboard-notice">
                    <div class="dashboard-notice-title">
                        No requests yet
                    </div>
                    Your recent leave requests will appear here.
                </div>
                """
            )

        else:
            recent = requests_df.copy()
            try:
                recent["parsed_start"] = pd.to_datetime(recent["start_date"], errors="coerce")
                recent = (recent.sort_values("parsed_start", ascending=False).head(3))
            except Exception:
                recent = recent.head(3)

            for _, row in recent.iterrows():
                leave_type = str(row.get("leave_type", "Leave"))
                start_date = _format_date(row.get("start_date"))
                status = str(row.get("status", "Unknown"))
                st.html(
                    f"""
                    <div class="dashboard-request-card">
                        <div style="
                            display:flex;
                            justify-content:space-between;
                            align-items:center;
                            gap:10px;
                        ">
                            <div>
                                <div class="
                                    dashboard-request-title
                                ">
                                    {leave_type}
                                </div>
                                <div class="
                                    dashboard-request-date
                                ">
                                    📅 {start_date}
                                </div>
                            </div>
                            <div>
                                {_status_badge(status)}
                            </div>
                        </div>
                    </div>
                    """
                )

        # View all button
        if st.button("View Leave History →", key = "dashboard_leave_history", use_container_width=True,):
            st.switch_page("pages/8_Time.py")

    # REMINDER
    st.html("<div style='height:20px'></div>")
    st.html(
        """
        <div class="dashboard-reminder">
            📌 <strong>Leave Reminder</strong><br>
            Please apply for leave at least one week in advance. For urgent leave, please inform BOSS.
        </div>
        """
    )

    # COMPANY NOTICE
    st.html("<div style='height:20px'></div>")
    st.html(
        """
        <div class="dashboard-section-title">
            Company Notice
        </div>
        """
    )
    st.html(
        """
        <div class="dashboard-notice">
            <div class="dashboard-notice-title">
                📢 HR System
            </div>
            This dashboard is currently in its first version and is still under testing.
            Some features may be updated or improved as the system develops.
        </div>
        """
    )
