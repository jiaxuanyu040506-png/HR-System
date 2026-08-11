import streamlit as st
import pandas as pd
from datetime import date
from utils.ui import inject_css, render_nav_sidebar
from utils.auth import require_login
from utils.leave_calc import (
    submit_leave_request, get_leave_balance, get_my_requests, init_year_balance,
    get_calendar_events, LEAVE_TYPES,
)
from utils.leave_attachment import upload_leave_attachment
from utils.sheets_client import read_table

inject_css()
require_login()
render_nav_sidebar(st.session_state["role"])
st.title("My Leave")

employee_id = st.session_state["employee_id"]
employees = read_table("Employees")
employee_df = employees[employees["employee_id"] == employee_id]
if employee_df.empty:
    st.error("Employee record not found.")
    st.stop()
employee = employee_df.iloc[0]
employee_name = employee["name"]

year = date.today().year

balance = get_leave_balance(employee_id, year)
if balance is None:
    init_year_balance(employee_id, year)
    balance = get_leave_balance(employee_id, year)

section = st.segmented_control(
    "Section", ["Apply Leave", "Leave Calendar", "Leave History"],
    default = "Apply Leave",
)
st.divider()

if section == "Apply Leave":
    if "leave_submit_message" in st.session_state:
        st.success(st.session_state.pop("leave_submit_message"))

    col_form, col_balance = st.columns([2, 1])

    with col_balance:
        st.markdown("#### Leave Balance")
        remaining_annual = int(balance["annual_total"]) - float(balance["annual_used"])
        medical_annual = int(balance["medical_total"]) - float(balance["medical_used"])
        balance_table = pd.DataFrame(
            {"Days Remaining": [remaining_annual, medical_annual]},
            index=["Annual Leave", "Medical Leave"],
        )
        st.table(balance_table)

    with col_form:
        with st.form("leave_form"):
            leave_type = st.selectbox("Leave Type", LEAVE_TYPES)
            col1, col2 = st.columns(2)
            start = col1.date_input("Start Date")
            end = col2.date_input("End Date")
            session = st.radio("Session", ["Full Day", "Half Day"], horizontal=True)
            if session == "Half Day":
                st.caption("Half Day applies to a single date — set Start Date = End Date.")
            reason = st.text_area("Reason")
            attachments = st.file_uploader(
                "Upload MC / Supporting Document",
                type=["pdf", "jpg", "jpeg", "png"],
                help="Accepted formats: PDF, JPG, JPEG, PNG",
            )
            submitted = st.form_submit_button("Apply Leave")

        if attachments:
            st.caption(f"{len(attachments)} file(s) selected.")

        if submitted:
            if end < start:
                st.error("End date must be on or after the start date.")
            elif session == "Half Day" and start != end:
                st.error("For Half Day, Start Date and End Date must be the same.")
            else:
                try:
                    request_id, days = submit_leave_request(employee_id, leave_type, start, end, reason, session)
                    if attachments:
                        for file in attachments:
                            upload_leave_attachment(request_id, employee_id, employee_name, file)
                    st.session_state["leave_submit_message"] = (
                        f"✅ Request {request_id} submitted successfully for {days} day(s)."
                    )
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    st.markdown(
        "<div style='background:#eaf3ff; border:1px solid #bcdcff; border-radius:8px; "
        "padding:10px 14px; margin-top:8px; color:#1e4a9e;'>"
        "📌 Note: Please apply leave at least one week in advance. For urgent leave, please inform BOSS."
        "</div>",
        unsafe_allow_html=True,
    )

elif section == "Leave Calendar":
    try:
        from streamlit_calendar import calendar
        events = get_calendar_events()
        calendar_options = {
            "initialView": "dayGridMonth",
            "height": 600,
            "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,listMonth"},
        }
        calendar(events=events, options=calendar_options, key="my_leave_calendar")
        if not events:
            st.info(
                "The calendar grid above is empty because there are no Approved leave "
                "requests yet — it only shows requests once HR approves them."
            )
        st.caption(
            "🔵 Annual  🌸 Medical  ⚪ Unpaid  🟣 Maternity  🟠 Hospitalization  🟢 Special "
            "— only Approved requests are shown, company-wide."
        )
    except ImportError:
        st.error(
            "The streamlit-calendar package isn't installed in this environment. "
            "Run `pip install streamlit-calendar` and restart the app."
        )

else:
    my_requests = get_my_requests(employee_id)
    if my_requests:
        history_df = pd.DataFrame(my_requests)[
            ["start_date", "leave_type", "days", "status", "reason"]
        ].rename(columns={
            "start_date": "Date", "leave_type": "Leave Type", "days": "Duration",
            "status": "Status", "reason": "Remarks",
        })
        st.table(history_df)
    else:
        st.caption("No requests yet.")