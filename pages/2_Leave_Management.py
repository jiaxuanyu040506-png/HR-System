import streamlit as st
from datetime import date, timedelta
from datetime import date as _date
import pandas as pd
from collections import defaultdict

try:
    import altair as alt
except ImportError:
    alt = None

from utils.ui import inject_css, render_nav_sidebar
from utils.auth import require_role
from utils.sheets_client import read_table
from utils.date_utils import parse_date
from utils.leave_rules import get_sick_leave_entitlement
from utils.leave_attachment import get_leave_attachment
from utils.supabase_client import download_file

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
        get_employee_monthly_leave_days,  get_employee_leave_type_days,
    )
except ImportError:
    from utils.leave_calc import get_pending_requests, get_all_pending_requests, approve_request, reject_request, delete_leave_request

    def get_employee_monthly_leave_days(year: int | None = None):
        return []
    
    def get_employee_leave_type_days(year: int | None = None):
        return []

    def record_leave_request(*args, **kwargs):
        raise ImportError("record_leave_request is not available")

    def get_monthly_approved_leave_headcount(year: int | None = None):
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
            # annual_remaining = annual_total - annual_used

            medical_total = float(balance["medical_total"]) if balance is not None else 0.0
            medical_used = float(balance["medical_used"]) if balance is not None else 0.0

            unpaid_used = float(balance.get("unpaid_used", 0)) if balance is not None else 0.0

            # sick_entitlement = 0.0
            # medical_used = 0.0
            # if balance is not None:
            #     try:
            #         sick_entitlement = float(get_sick_leave_entitlement(employee["join_date"]))
            #         medical_used = max(sick_entitlement - sick_balance, 0.0)
            #     except Exception:
            #         sick_entitlement = sick_balance
            #         medical_used = 0.0
            summaries.append({
                "employee_id": emp_id,
                "employee_name": employee.get("name", ""),
                "department": employee.get("department", ""),
                "annual_total": annual_total,
                "annual_used": annual_used,
                "annual_remaining": annual_total - annual_used,
                # "annual_remaining": annual_remaining,
                "medical_total": medical_total,
                "medical_used": medical_used,
                "medical_remaining": medical_total - medical_used,
                # "sick_balance": sick_balance,
                "unpaid_used": unpaid_used,
                "year": year,
            })
        return summaries

    def get_all_requests():
        requests = read_table("LeaveRequests")
        if requests.empty:
            return []
        return requests.sort_values("submit_date", ascending=False).to_dict("records")

    def get_calendar_events():
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
                "title": row.get("employee_name", row["employee_id"]),
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
# section = st.radio(
#     "Section", ["Leave Approval", "Leave Calendar", "Record Leave", "Employee Leave History"],
#     horizontal=True, label_visibility="collapsed",
# )
options = {
    "✅ Leave Approval": "Leave Approval",
    "📅 Leave Calendar": "Leave Calendar",
    "📝 Record Leave": "Record Leave",
    "📋 Employee Leave History": "Employee Leave History",
}
selected = st.segmented_control(
    "", list(options.keys()), default="✅ Leave Approval", label_visibility="collapsed",
)
section = options[selected]
st.divider()

# ---------- Record Leave ----------
if section == "Record Leave":
    view_mode = st.radio("View", ["Summary", "Record Leave"], horizontal=True, label_visibility="collapsed")

    if view_mode == "Summary":
        st.subheader("Leave Summary")
        # st.markdown("左边：每位员工的请假天数（按月堆叠）。右边：每月有多少人请假。")

        month_counts = get_monthly_approved_leave_headcount(date.today().year)
        summaries = get_employee_leave_summaries(date.today().year)
        employee_by_type = get_employee_leave_type_days(date.today().year)
        employee_monthly = get_employee_monthly_leave_days(date.today().year)

        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("##### 每位员工请假天数")
            if employee_by_type:
                emp_type_df = pd.DataFrame(employee_by_type)
                totals_df = emp_type_df.groupby("employee_name", as_index=False)["days"].sum()
                if alt is not None:
                    bars = alt.Chart(emp_type_df).mark_bar().encode(
                        x=alt.X("employee_name:N", title="Employee", sort=None),
                        y=alt.Y("days:Q", title="Days on leave", stack="zero"),
                        color=alt.Color("leave_type:N", title="Leave Type"),
                        tooltip=["employee_name", "leave_type", "days"],
                    ).properties(height=max(320, 25 * len(emp_type_df)))
                    labels = alt.Chart(totals_df).mark_text(dy=-8, fontWeight="bold").encode(
                        x=alt.X("employee_name:N", sort=None),
                        y=alt.Y("days:Q"),
                        text=alt.Text("days:Q", format=".1f"),
                    )
                    st.altair_chart(bars + labels, use_container_width=True)
                else:
                    pivot = emp_type_df.pivot_table(
                        index="employee_name", columns="leave_type", values="days", aggfunc="sum", fill_value=0
                    )
                    st.bar_chart(pivot)
            else:
                st.info("目前还没有已批准的请假记录。")

        with col_right:
            st.markdown("##### 每月请假人数")
            if month_counts:
                import calendar as _calendar
                donut_df = pd.DataFrame({
                    "month_key": list(month_counts.keys()),
                    "employees_on_leave": list(month_counts.values()),
                })
                donut_df["month"] = donut_df["month_key"].apply(
                    lambda k: _calendar.month_abbr[int(k.split("-")[1])]
                )
                if alt is not None:
                    hbar = alt.Chart(donut_df).mark_bar().encode(
                        y=alt.Y("month:N", title="Month", sort=list(donut_df["month"])),
                        x=alt.X("employees_on_leave:Q", title="Employees on leave",
                                axis=alt.Axis(format="d", tickMinStep=1)),
                        tooltip=["month", "employees_on_leave"],
                    ).properties(height=max(320, 50 * len(donut_df)))
                    hbar_labels = alt.Chart(donut_df).mark_text(dx=8, align="left").encode(
                        y=alt.Y("month:N", sort=list(donut_df["month"])),
                        x=alt.X("employees_on_leave:Q"),
                        text=alt.Text("employees_on_leave:Q", format="d"),
                    )
                    st.altair_chart(hbar + hbar_labels, use_container_width=True)
                else:
                    st.bar_chart(donut_df.set_index("month")["employees_on_leave"])
            else:
                st.info("目前还没有已批准的请假记录。")

        st.divider()
        if summaries:
            summary_table = pd.DataFrame(summaries)[[
                "employee_name", "department", "annual_total", "annual_used",
                "annual_remaining", "medical_total", "medical_used", "medical_remaining", "unpaid_used",
            ]]
            summary_table = summary_table.rename(columns={
                "employee_name": "姓名",
                "department": "部门",
                "annual_total": "Annual Total",
                "annual_used": "Annual Used",
                "annual_remaining": "Annual Remaining",
                "medical_total": "Medical Total",
                "medical_used": "Medical Used",
                "medical_remaining": "Medical Remaining",
                "unpaid_used": "Unpaid Used",
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
        # st.write(events)
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

    # --------------------------------------------------------
    # Get pending requests
    # --------------------------------------------------------

    if role == "hr_admin":

        pending = get_all_pending_requests()

    else:

        pending = get_pending_requests(
            st.session_state["email"]
        )


    # --------------------------------------------------------
    # No pending requests
    # --------------------------------------------------------

    if not pending:

        st.caption(
            "No pending requests."
        )


    # --------------------------------------------------------
    # Display pending requests
    # --------------------------------------------------------

    for req in pending:

        request_id = str(
            req["request_id"]
        )

        attachments = get_leave_attachment(
            request_id
        )


        # ====================================================
        # Leave Approval Card
        # ====================================================

        st.markdown(
            "<div class='leave-approval-card'>"
            f"<h3>{req.get('employee_name', req['employee_id'])}</h3>"
            f"<div class='leave-approval-note'>"
            f"{req.get('reason', 'No reason provided.')}"
            "</div>"
            "<div class='leave-approval-meta'>"

            f"<div><strong>Leave type</strong>"
            f"{req['leave_type']}</div>"

            f"<div><strong>Start</strong>"
            f"{req['start_date']}</div>"

            f"<div><strong>End</strong>"
            f"{req['end_date']}</div>"

            f"<div><strong>Days</strong>"
            f"{req['days']} day(s)</div>"

            f"<div><strong>Session</strong>"
            f"{req.get('session', 'Full Day')}</div>"

            f"<div><strong>Status</strong>"
            f"{req.get('status', 'Pending')}</div>"

            f"<div><strong>Requested on</strong>"
            f"{req.get('submit_date', 'Unknown')}</div>"

            f"<div><strong>Employee ID</strong>"
            f"{req['employee_id']}</div>"

            +

            (
                f"<div><strong>Attachment</strong>"
                f"{len(attachments)} file(s)</div>"
                if attachments
                else
                "<div><strong>Attachment</strong>"
                "None</div>"
            )

            +

            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )


        # ====================================================
        # Attachments
        # ====================================================

        if attachments:

            st.markdown(
                "##### 📎 Attachments"
            )

            for index, file in enumerate(
                attachments
            ):

                file_name = file.get(
                    "file_name",
                    "Attachment"
                )

                file_path = file.get(
                    "file_path"
                )

                mime_type = file.get(
                    "mime_type",
                    ""
                ).strip().lower()

                uploaded_date = file.get(
                    "uploaded_date",
                    ""
                )


                # ------------------------------------------------
                # Fallback MIME type
                # ------------------------------------------------

                if not mime_type:

                    extension = (
                        file_name
                        .lower()
                        .split(".")[-1]
                    )

                    mime_map = {
                        "pdf": "application/pdf",
                        "jpg": "image/jpeg",
                        "jpeg": "image/jpeg",
                        "png": "image/png",
                    }

                    mime_type = mime_map.get(
                        extension,
                        "application/octet-stream"
                    )


                # ------------------------------------------------
                # Missing file path
                # ------------------------------------------------

                if not file_path:

                    st.error(
                        f"{file_name}: "
                        "File path unavailable."
                    )

                    continue


                # =================================================
                # Attachment information
                # =================================================

                col1, col2, col3 = st.columns(
                    [4, 1, 1]
                )


                with col1:

                    if mime_type == "application/pdf":

                        icon = "📄"

                    elif mime_type.startswith(
                        "image/"
                    ):

                        icon = "🖼️"

                    else:

                        icon = "📎"


                    st.write(
                        f"{icon} **{file_name}**"
                    )

                    if uploaded_date:

                        st.caption(
                            f"Uploaded: "
                            f"{uploaded_date}"
                        )


                # =================================================
                # Load file from Supabase
                # =================================================

                try:

                    file_bytes = download_file(
                        file_path
                    )


                    # =================================================
                    # Preview button
                    # =================================================

                    with col2:

                        preview_key = (
                            f"preview_mc_"
                            f"{request_id}_"
                            f"{index}"
                        )

                        preview = st.toggle(
                            "Preview",
                            key=preview_key
                        )


                    # =================================================
                    # Download button
                    # =================================================

                    with col3:

                        st.download_button(
                            "Download",
                            data=file_bytes,
                            file_name=file_name,
                            mime=mime_type,
                            key=(
                                f"download_mc_"
                                f"{request_id}_"
                                f"{index}"
                            ),
                            use_container_width=True,
                        )


                    # =================================================
                    # Preview
                    # =================================================

                    if preview:

                        # -----------------------------------------
                        # PDF
                        # -----------------------------------------

                        if mime_type == "application/pdf":

                            import base64

                            base64_file = (
                                base64.b64encode(
                                    file_bytes
                                ).decode("utf-8")
                            )

                            pdf_display = f"""
                            <iframe
                                src="data:application/pdf;base64,{base64_file}"
                                width="100%"
                                height="600"
                                style="
                                    border: 1px solid #ddd;
                                    border-radius: 8px;
                                "
                                type="application/pdf">
                            </iframe>
                            """

                            st.markdown(
                                pdf_display,
                                unsafe_allow_html=True,
                            )


                        # -----------------------------------------
                        # JPG / JPEG / PNG
                        # -----------------------------------------

                        elif mime_type in [
                            "image/jpeg",
                            "image/png",
                        ]:

                            st.image(
                                file_bytes,
                                use_container_width=True,
                            )


                        # -----------------------------------------
                        # Unsupported file type
                        # -----------------------------------------

                        else:

                            st.warning(
                                "Preview is not "
                                "available for this "
                                "file type. "
                                "Please download the file."
                            )


                except Exception as e:

                    st.error(
                        f"Unable to load "
                        f"{file_name}."
                    )

                    st.caption(
                        f"Error: {e}"
                    )


        # ====================================================
        # Approve / Reject
        # ====================================================

        cols = st.columns(
            [1, 1]
        )


        with cols[0]:

            if st.button(
                "Approve",
                key=f"appr_{request_id}",
                use_container_width=True,
            ):

                approve_request(
                    request_id,
                    st.session_state["email"],
                )

                st.rerun()


        with cols[1]:

            if st.button(
                "Reject",
                key=f"rej_{request_id}",
                use_container_width=True,
            ):

                reject_request(
                    request_id,
                    st.session_state["email"],
                )

                st.rerun()

# ---------- Employee Leave History ----------
else:
    sub_view = st.radio("Sub-view", ["Pending", "History"], horizontal=True, label_visibility="collapsed")
    all_requests = get_all_requests()

    # st.subheader("Employee Leave History")

    def _render_request_card(req, show_delete=True):
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
        if show_delete:
            cols = st.columns([1, 3])
            with cols[0]:
                if st.button("Delete Entry", key=f"delete_{req['request_id']}", use_container_width=True):
                    if delete_leave_request(req["request_id"]):
                        st.success(f"Leave record {req['request_id']} deleted.")
                        st.rerun()
                    else:
                        st.error("Failed to delete the selected leave record.")
            with cols[1]:
                st.caption("Use this button to remove an incorrectly entered or mistaken leave record.")
        st.divider()

    if sub_view == "Pending":
        rows = [r for r in all_requests if r["status"] == "Pending"]
        st.subheader("Pending Requests")
        if not rows:
            st.caption("Nothing to show.")
        else:
            for req in rows:
                _render_request_card(req)

    else:
        history_rows = [r for r in all_requests if r["status"] != "Pending"]
        if not history_rows:
            st.caption("No history yet.")
        else:
            # Master list: one row per employee with a history count — click to drill in.
            from collections import Counter
            counts = Counter(r.get("employee_name", r["employee_id"]) for r in history_rows)
            employee_list = sorted(counts.keys())

            selected_employee = st.session_state.get("history_selected_employee")
            if selected_employee not in employee_list:
                selected_employee = None

            if selected_employee is None:
                st.caption("Click an employee to view their individual leave history.")
                list_df = pd.DataFrame({
                    "Employee": employee_list,
                    "Records": [counts[name] for name in employee_list],
                })
                event = st.dataframe(
                    list_df, use_container_width=True, hide_index=True,
                    on_select="rerun", selection_mode="single-row", key="history_employee_list",
                )
                if event and event.selection and event.selection["rows"]:
                    st.session_state["history_selected_employee"] = employee_list[event.selection["rows"][0]]
                    st.rerun()
            else:
                if st.button("← Back to employee list"):
                    st.session_state.pop("history_selected_employee", None)
                    st.rerun()
                st.markdown(f"#### {selected_employee}'s Leave History")
                for req in history_rows:
                    if req.get("employee_name", req["employee_id"]) == selected_employee:
                        _render_request_card(req)