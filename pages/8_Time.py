import streamlit as st
import pandas as pd
from datetime import date

from utils.ui import inject_css, render_nav_sidebar
from utils.auth import require_login
from utils.leave_calc import (
    submit_leave_request,
    get_leave_balance,
    get_my_requests,
    init_year_balance,
    get_calendar_events,
    LEAVE_TYPES,
)
from utils.leave_attachment import upload_leave_attachment
from utils.sheets_client import read_table

# PAGE SETUP
inject_css()
require_login()
render_nav_sidebar(st.session_state["role"])

st.title("My Leave")

# EMPLOYEE INFORMATION
employee_id = st.session_state["employee_id"]
employees = read_table("Employees")
employee_df = employees[employees["employee_id"].astype(str) == str(employee_id)]

if employee_df.empty:
    st.error("Employee record not found.")
    st.stop()

employee = employee_df.iloc[0]
employee_name = employee["name"]

# LEAVE BALANCE
year = date.today().year
balance = get_leave_balance(employee_id, year,)
if balance is None:
    init_year_balance(employee_id, year,)
    balance = get_leave_balance(employee_id, year,)

# CALCULATE BALANCE
annual_total = float(balance.get("annual_total", 0) or 0)
annual_used = float(balance.get("annual_used", 0) or 0)
annual_remaining = max(annual_total - annual_used, 0,)

medical_total = float(balance.get("medical_total", 0) or 0)
medical_used = float(balance.get("medical_used", 0) or 0)
medical_remaining = max(medical_total - medical_used, 0,)

# HELPER FUNCTIONS
def format_days(value):
    """
    Display whole numbers without .0.
    """
    value = float(value or 0)

    if value.is_integer():
        return str(int(value))

    return f"{value:.1f}"


def format_date(value):
    """
    Convert date/string to friendly format.
    Example: 2026-08-12 -> 12 Aug 2026
    """

    if value is None or value == "":
        return "-"

    try:
        return pd.to_datetime(value).strftime("%d %b %Y")
    except Exception:
        return str(value)


def status_badge(status):
    """
    Return HTML badge for leave status.
    """

    status = str(status or "Unknown")
    status_lower = status.lower()
    if status_lower == "approved":
        return (
            "<span style='"
            "background:#dcfce7;"
            "color:#166534;"
            "padding:4px 10px;"
            "border-radius:999px;"
            "font-size:0.82rem;"
            "font-weight:600;"
            "'>✓ Approved</span>"
        )

    elif status_lower == "pending":
        return (
            "<span style='"
            "background:#fef3c7;"
            "color:#92400e;"
            "padding:4px 10px;"
            "border-radius:999px;"
            "font-size:0.82rem;"
            "font-weight:600;"
            "'>◷ Pending</span>"
        )

    elif status_lower == "rejected":
        return (
            "<span style='"
            "background:#fee2e2;"
            "color:#991b1b;"
            "padding:4px 10px;"
            "border-radius:999px;"
            "font-size:0.82rem;"
            "font-weight:600;"
            "'>✕ Rejected</span>"
        )

    return (
        "<span style='"
        "background:#f1f5f9;"
        "color:#475569;"
        "padding:4px 10px;"
        "border-radius:999px;"
        "font-size:0.82rem;"
        "font-weight:600;"
        "'>"
        + status
        + "</span>"
    )

# WELCOME MESSAGE
st.html(
    f"""
    <div class="leave-welcome">
        <div class="leave-welcome-title">
            Good morning, {employee_name} 👋
        </div>

        <div class="leave-welcome-text">
            Manage your leave requests, check your leave balance,
            and view your leave history here.
        </div>
    </div>
    """
)

# NAVIGATION
section = st.segmented_control("Section", ["Apply Leave", "Leave Calendar", "Leave History",], default="Apply Leave", label_visibility="collapsed",)
st.divider()

# APPLY LEAVE
if section == "Apply Leave":
    # REMINDER
    st.markdown(
        """
        <div style="
            background:#fff7f7;
            border:1px solid #f5d0d0;
            border-radius:10px;
            padding:13px 16px;
            margin-top:18px;
            color:#475569;
            font-size:1rem;
            line-height:1.5;
        ">
            📌 <strong>Important Reminder:</strong>
            Please apply for leave at least one week in advance.
            For urgent leave, please inform BOSS.
        </div>
        """,unsafe_allow_html=True,)

    # SUCCESS MESSAGE
    if "leave_submit_message" in st.session_state:
        st.success(st.session_state.pop("leave_submit_message"))

    # MAIN LAYOUT
    col_form, col_balance = st.columns([2.1, 1], gap="large",)

    # FORM
    with col_form:
        st.subheader("Apply for Leave")
        st.caption(
            "Submit your leave request below. "
            "Your request will be reviewed by HR or your manager.")
        
        with st.form("leave_form"):
            leave_type = st.selectbox("Leave Type", LEAVE_TYPES,)

            col1, col2 = st.columns(2)
            with col1:
                start = st.date_input("Start Date", value=date.today(),)
            with col2:
                end = st.date_input("End Date", value=date.today(),)

            # Session
            session = st.radio("Session", ["Full Day", "Half Day",], horizontal=True,)
            if session == "Half Day":
                st.caption("ℹ️ Half Day leave applies to one date only.")

            # Reason
            reason = st.text_area("Reason", placeholder=("Enter a short reason for your leave (optional)."),height=100,)

            # Attachment
            attachments = st.file_uploader("Supporting Document",
                type = ["pdf", "jpg", "jpeg", "png",],
                accept_multiple_files = True,
                help = ("Accepted formats: PDF, JPG, JPEG, PNG."),)

            if attachments:
                st.caption(f"📎 {len(attachments)} file(s) selected.")

            # Submit
            submitted = st.form_submit_button("Submit Leave Request", type = "primary", use_container_width = True,)

        # FORM VALIDATION / SUBMISSION
        if submitted:
            if end < start:
                st.error("End date must be on or after the start date.")
            elif (session == "Half Day" and start != end):
                st.error("For Half Day leave, Start Date and End Date must be the same.")
            else:
                try:
                    request_id, days = (submit_leave_request(employee_id, leave_type, start, end, reason, session,))

                    # Upload attachments
                    if attachments:
                        for file in attachments:
                            upload_leave_attachment(request_id, employee_id, employee_name, file,)

                    # Success message
                    st.session_state["leave_submit_message"] = (f"✅ Leave request {request_id} submitted successfully for {format_days(days)} day(s).")
                    st.rerun()

                except ValueError as e:
                    st.error(str(e))

                except Exception as e:
                    st.error(f"Unable to submit leave request: {e}")

    # LEAVE BALANCE
    with col_balance:
        st.subheader("Leave Balance")
        st.caption(f"Your leave balance for {year}")

        # Annual Leave
        annual_percentage = (annual_used / annual_total * 100 if annual_total > 0 else 0)
        st.html(
            f"""
            <div class="balance-card">

                <div class="balance-card-title">
                    🏖️ Annual Leave
                </div>

                <div class="balance-number">
                    {format_days(annual_remaining)}
                </div>

                <div class="balance-label">
                    days remaining
                </div>

                <div class="balance-detail">
                    {format_days(annual_used)} used
                    ·
                    {format_days(annual_total)} total
                </div>

                <div class="balance-progress">
                    <div style="
                        width:{min(annual_percentage, 100)}%;
                        height:100%;
                        background:#5b8def;
                        border-radius:999px;
                    "></div>
                </div>

            </div>
            """)

        # Medical Leave
        medical_percentage = (medical_used / medical_total * 100 if medical_total > 0 else 0)
        st.html(
            f"""
            <div class="balance-card">

                <div class="balance-card-title">
                    🩺 Medical Leave
                </div>

                <div class="balance-number">
                    {format_days(medical_remaining)}
                </div>

                <div class="balance-label">
                    days remaining
                </div>

                <div class="balance-detail">
                    {format_days(medical_used)} used
                    ·
                    {format_days(medical_total)} total
                </div>

                <div class="balance-progress">
                    <div style="
                        width:{min(medical_percentage, 100)}%;
                        height:100%;
                        background:#f28c8c;
                        border-radius:999px;
                    "></div>
                </div>

            </div>
            """)

        # Helpful note
        st.markdown(
            """
            <div class="info-note">
                💡 Please make sure you have enough leave
                balance before submitting your request.
            </div>
            """,unsafe_allow_html=True,)

# LEAVE CALENDAR
elif section == "Leave Calendar":
    st.subheader("Leave Calendar")
    st.caption("View approved leave across the company.")

    try:
        from streamlit_calendar import calendar
        events = get_calendar_events()
        calendar_options = {
            "initialView": "dayGridMonth",
            "height": 620,
            "headerToolbar": {
                "left": "prev,next today",
                "center": "title",
                "right": "dayGridMonth,listMonth",
            },
            "dayMaxEvents": 3,
            "eventDisplay": "block",
            "displayEventTime": False,}

        calendar(events = events, options = calendar_options, key = "my_leave_calendar",)

        if not events:
            st.info("There are no approved leave requests to display yet.")

        st.markdown(
            """
            <div style="
                margin-top:12px;
                padding:10px 14px;
                background:#f8fafc;
                border:1px solid #e2e8f0;
                border-radius:10px;
                font-size:0.88rem;
                color:#475569;
            ">
                🔵 Annual&nbsp;&nbsp;&nbsp;
                🌸 Medical&nbsp;&nbsp;&nbsp;
                ⚪ Unpaid&nbsp;&nbsp;&nbsp;
                🟣 Maternity&nbsp;&nbsp;&nbsp;
                🟠 Hospitalization&nbsp;&nbsp;&nbsp;
                🟢 Special
                <br>
                <span style="color:#64748b;">
                    Only approved leave requests are shown.
                </span>
            </div>
            """, unsafe_allow_html=True,)

    except ImportError:
        st.error("The streamlit-calendar package isn't installed in this environment.")
        st.code("pip install streamlit-calendar")

# LEAVE HISTORY
else:
    st.subheader("Leave History")
    st.caption("View your previous and current leave requests.")

    # GET REQUESTS
    my_requests = get_my_requests(employee_id)

    # EMPTY STATE
    if not my_requests:
        st.info("You don't have any leave requests yet.")
        st.caption("Your leave requests will appear here after you submit them.")
    else:
        history_df = pd.DataFrame(my_requests)

        # KPI
        total_requests = len(history_df)
        approved_count = (history_df["status"].astype(str).str.lower().eq("approved").sum())
        pending_count = (history_df["status"].astype(str).str.lower().eq("pending").sum())

        # KPI CARDS
        st.markdown(
            """
            <style>
            .kpi-card {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
                padding: 18px 20px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.06);
                min-height: 105px;
            }

            .kpi-label {
                font-size: 14px;
                color: #6B7280;
                font-weight: 500;
                margin-bottom: 6px;
            }

            .kpi-value {
                font-size: 28px;
                font-weight: 700;
                color: #111827;
                line-height: 1.2;
            }
            </style>
            """, unsafe_allow_html=True,)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">Total Requests</div>
                    <div class="kpi-value">{total_requests}</div>
                </div>
                """,unsafe_allow_html=True,)
        with c2:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">Approved</div>
                    <div class="kpi-value">{approved_count}</div>
                </div>
                """, unsafe_allow_html=True,)
        with c3:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">Pending</div>
                    <div class="kpi-value">{pending_count}</div>
                </div>
                """, unsafe_allow_html=True,)
        st.divider()

        # FILTERS

        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            status_options = ["All Status", "Pending", "Approved", "Rejected",]
            selected_status = st.selectbox("Filter by Status", status_options, key = "my_leave_status_filter",)
        with filter_col2:
            leave_type_options = ["All Leave Types"] + list(history_df["leave_type"].dropna().astype(str).unique())
            selected_leave_type = st.selectbox("Filter by Leave Type", leave_type_options, key="my_leave_type_filter",)

        # APPLY FILTER
        filtered_df = history_df.copy()
        if selected_status != "All Status":
            filtered_df = filtered_df[filtered_df["status"].astype(str).str.lower() == selected_status.lower()]
        if (selected_leave_type != "All Leave Types"):
            filtered_df = filtered_df[filtered_df["leave_type"].astype(str) == selected_leave_type]

        # RESULT COUNT
        st.caption(f"Showing {len(filtered_df)} of {len(history_df)} request(s)")

        # HISTORY CARDS
        if filtered_df.empty:
            st.info("No leave requests match the selected filters.")
        else:
            # Newest first
            try:
                filtered_df = (filtered_df.sort_values("start_date", ascending = False,))
            except Exception:
                pass

            for index, row in filtered_df.iterrows():
                leave_type = str(row.get("leave_type", "-",))
                start_date = format_date(row.get("start_date"))
                end_date = format_date(row.get("end_date"))
                days = format_days(row.get("days", 0,))
                status = str(row.get("status", "Unknown",))
                reason = str(row.get("reason", "",) or "")
                session = str(row.get("session", "Full Day",))
                request_id = str(row.get("request_id", "-",))

                # Card
                with st.container(border=True):
                    col1, col2, col3 = st.columns([3.5, 2.5, 1.5])

                    # Main information
                    with col1:
                        st.markdown(f"**{leave_type}**")
                        if start_date == end_date:
                            st.caption(f"📅 {start_date}")
                        else:
                            st.caption(f"📅 {start_date} → {end_date}")
                        st.caption(f"⏱️ {days} day(s) · {session}")

                    # Reason
                    with col2:
                        if reason:
                            st.markdown("**Reason**")
                            st.caption(reason)
                        else:
                            st.caption("No reason provided.")

                    # Status
                    with col3:
                        st.markdown("**Status**")
                        st.markdown(status_badge(status),unsafe_allow_html=True,)

                    # Additional information
                    with st.expander("View request details"):
                        detail_col1, detail_col2 = (st.columns(2))
                        with detail_col1:
                            st.caption("Request ID")
                            st.write(request_id)
                            st.caption("Submitted")
                            st.write(format_date(row.get("submit_date")))
                        with detail_col2:
                            st.caption("Start Date")
                            st.write(start_date)
                            st.caption("End Date")
                            st.write(end_date)

                        if row.get("approved_by"):
                            st.caption("Approved / Rejected By")
                            st.write(row.get("approved_by"))
        st.divider()

        # SIMPLE TABLE VIEW
        if not filtered_df.empty:
            with st.expander("View as table"):
                table_df = filtered_df.copy()
                columns = ["start_date", "end_date", "leave_type", "days", "session", "status", "reason",]

                available_columns = [col for col in columns if col in table_df.columns]
                table_df = table_df[available_columns].copy()
                rename_map = {
                    "start_date": "Start Date",
                    "end_date": "End Date",
                    "leave_type": "Leave Type",
                    "days": "Duration",
                    "session": "Session",
                    "status": "Status",
                    "reason": "Remarks",
                }


                table_df = table_df.rename(columns=rename_map)
                if "Start Date" in table_df.columns:
                    table_df["Start Date"] = table_df["Start Date"].apply(format_date)
                if "End Date" in table_df.columns:
                    table_df["End Date"] = table_df["End Date"].apply(format_date)

                st.dataframe(table_df,use_container_width = True,hide_index = True,)