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
        get_employee_monthly_leave_days,  get_employee_leave_type_days, get_leave_summary
    )
except ImportError:
    from utils.leave_calc import (
        get_pending_requests,
        get_all_pending_requests,
        approve_request,
        reject_request,
        delete_leave_request,
        get_leave_summary,
    )

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
        if employees.empty:
            return []

        summaries = []
        for _, employee in employees.iterrows():
            emp_id = str(employee["employee_id"])
            summary = get_leave_summary(emp_id, year)
            summaries.append({
                "employee_id": emp_id,
                "employee_name": employee.get("name", ""),
                "department": employee.get("department", ""),
                "annual_total": summary["annual_total"],
                "annual_used": summary["annual_used"],
                "annual_remaining": summary["annual_remaining"],
                "medical_total": summary["medical_total"],
                "medical_used": summary["medical_used"],
                "medical_remaining": summary["medical_remaining"],
                "unpaid_used": summary["unpaid_used"],
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

# Main Navigation
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
    view_mode = st.radio("View", [
            "📊 Summary",
            "📝 Record Leave",
        ], horizontal=True, label_visibility="collapsed")

    # Leave Summary
    if view_mode == "📊 Summary":
        st.subheader("Leave Summary")

        # Year Filter
        current_year = date.today().year
        balances = read_table("LeaveBalance")
        available_years = []
        if not balances.empty and "year" in balances.columns:
            try:
                available_years = sorted(balances["year"].dropna().astype(int).unique().tolist(),reverse=True,)
            except Exception:
                available_years = []

        if current_year not in available_years:
            available_years.insert(0, current_year,)

        selected_year = st.selectbox("Year", available_years, index=0, key="leave_summary_year",)

        # LOAD DATA
        employees = read_table("Employees")
        summaries = get_employee_leave_summaries(selected_year)
        employee_by_type = (get_employee_leave_type_days(selected_year))
        employee_monthly = (get_employee_monthly_leave_days(selected_year))
        month_counts = (get_monthly_approved_leave_headcount(selected_year))

        # PREPARE SUMMARY DATAFRAME
        if summaries:
            summary_df = pd.DataFrame(summaries)
        else:
            summary_df = pd.DataFrame(
                columns=[
                    "employee_id",
                    "employee_name",
                    "department",
                    "annual_total",
                    "annual_used",
                    "annual_remaining",
                    "medical_total",
                    "medical_used",
                    "medical_remaining",
                    "unpaid_used",
                    "year",
                ])

        # KPI
        total_employees = (len(employees) if not employees.empty else len(summary_df))
        employees_used_al = 0
        employees_used_medical = 0
        if not summary_df.empty:
            employees_used_al = int((summary_df["annual_used"].astype(float) > 0).sum())
            employees_used_medical = int((summary_df["medical_used"].astype(float) > 0).sum())

        # Current employees on leave
        all_requests = get_all_requests()
        today = date.today()
        employees_on_leave = set()
        for request in all_requests:
            status = str(request.get("status", "",)).strip().lower()
            if status != "approved":
                continue
            try:
                start = parse_date(request["start_date"])
                end = parse_date(request["end_date"])

            except Exception:
                continue

            if start <= today <= end:
                employees_on_leave.add(
                    str(request.get("employee_id", "",)))

        current_on_leave_count = len(employees_on_leave)

        # KPI Cards
        st.markdown("#### Overview")
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.metric("👥 Total Employees", total_employees,)
        with k2:
            st.metric("🌴 Employees Used AL", employees_used_al,)
        with k3:
            st.metric("🩺 Employees Used Medical", employees_used_medical,)
        with k4:
            st.metric("📅 Currently on Leave", current_on_leave_count,)

        st.caption(
            f"Leave overview for {selected_year}. "
            "Employee-level balances are shown below.")
        st.divider()

        # EMPLOYEE FILTERS
        st.markdown("#### Employee Leave Balance")
        f1, f2, f3 = st.columns([1, 1, 1])

        # Employee ID
        employee_ids = []
        if not summary_df.empty:
            employee_ids = sorted(summary_df["employee_id"].astype(str).unique().tolist())
        with f1:
            selected_employee_id = st.selectbox("Employee ID", ["All Employees"]  + employee_ids, key="leave_summary_employee",)

        # Department
        departments = []
        if not summary_df.empty:
            departments = sorted([str(x) for x in summary_df["department"].dropna().unique() if str(x).strip()])
        with f2:
            selected_department = st.selectbox("Department", ["All Departments"] + departments, key="leave_summary_department",)

        # Search employee
        with f3:
            search_employee = st.text_input( "Search Employee", placeholder="Name...", key="leave_summary_search",)

        # APPLY FILTER
        filtered_summary = summary_df.copy()
        if (selected_employee_id != "All Employees"):
            filtered_summary = filtered_summary[filtered_summary["employee_id"].astype(str) == selected_employee_id]
        if (selected_department != "All Departments"):
            filtered_summary = filtered_summary[filtered_summary["department"].astype(str) == selected_department]
        if search_employee.strip():
            keyword = (search_employee.strip().lower())
            filtered_summary = (
                filtered_summary[filtered_summary["employee_name"].astype(str).str.lower().str.contains(keyword,na=False,)])

        # TABLE PREPARATION
        if filtered_summary.empty:
            st.info("No employees match the selected filters.")
        else:
            display_df = filtered_summary[
                ["employee_id", "employee_name", "department",
                 "annual_total", "annual_used", "annual_remaining",
                 "medical_total", "medical_used", "medical_remaining",
                 "unpaid_used",]].copy()
            
            display_df = display_df.rename(
                columns={
                    "employee_id":"Employee ID",
                    "employee_name":"Employee",
                    "department":"Department",
                    "annual_total":"AL Total",
                    "annual_used":"AL Used",
                    "annual_remaining":"AL Remaining",
                    "medical_total":"Medical Total",
                    "medical_used":"Medical Used",
                    "medical_remaining":"Medical Remaining",
                    "unpaid_used":"Unpaid Used",})

            # Format leave numbers
            numeric_columns = [
                "AL Total", "AL Used", "AL Remaining",
                "Medical Total", "Medical Used", "Medical Remaining", "Unpaid Used",]

            for col in numeric_columns:
                if col in display_df.columns:
                    display_df[col] = (pd.to_numeric(display_df[col], errors="coerce",).fillna(0).round(1))

            display_df["Unpaid Status"] = display_df["Unpaid Used"].apply(
                lambda x: "🚨 Has Unpaid" if float(x) > 0 else "✅ No Unpaid")

            # Reorder columns

            display_df = display_df[["Employee ID", "Employee", "Department",
                                     "AL Total","AL Used","AL Remaining",
                                     "Medical Total", "Medical Used", "Medical Remaining",
                                     "Unpaid Used", "Unpaid Status",]]

            styled_df = display_df.style.map(lambda _: "font-weight: bold;", subset=["AL Remaining", "Medical Used", "Unpaid Used"],).format({
                "AL Total": "{:.1f}", "AL Used": "{:.1f}", "AL Remaining": "{:.1f}",
                "Medical Total": "{:.1f}", "Medical Used": "{:.1f}", "Medical Remaining": "{:.1f}",
                "Unpaid Used": "{:.1f}",})

            st.dataframe(styled_df, use_container_width=True, hide_index=True, column_config={
                    "AL Total":st.column_config.NumberColumn("AL Total", format="%.1f days",),
                    "AL Used":st.column_config.NumberColumn("AL Used", format="%.1f days",),
                    "AL Remaining": st.column_config.NumberColumn("AL Remaining", format="%.1f days",),
                    "Medical Total": st.column_config.NumberColumn("Medical Total", format="%.1f days",),
                    "Medical Used": st.column_config.NumberColumn("Medical Used", format="%.1f days",),
                    "Medical Remaining": st.column_config.NumberColumn("Medical Remaining", format="%.1f days",),
                    "Unpaid Used": st.column_config.NumberColumn("Unpaid Used", format="%.1f days",),
                    "Unpaid Status": st.column_config.TextColumn("Unpaid Status",),},)
        st.divider()

        # LEAVE ANALYTICS
        st.markdown("#### Leave Analytics")
        chart_col1, chart_col2 = st.columns(2)

        # CHART 1 - Leave Days by Employee
        with chart_col1:
            st.markdown("##### Leave Days by Employee")
            if employee_by_type:
                emp_type_df = pd.DataFrame(employee_by_type)

                if not emp_type_df.empty:
                    # Apply employee filter
                    if (selected_employee_id != "All Employees"):
                        emp_type_df = (emp_type_df[emp_type_df["employee_id"].astype(str) == selected_employee_id]
                            if "employee_id" in emp_type_df.columns
                            else emp_type_df[emp_type_df["employee_name"].astype(str) == str(filtered_summary["employee_name"].iloc[0])
                                if not filtered_summary.empty
                                else False
                            ])

                    # Apply department filter
                    if (selected_department != "All Departments" and not filtered_summary.empty):
                        allowed_names = set(filtered_summary["employee_name"].astype(str).tolist())
                        emp_type_df = (emp_type_df[emp_type_df["employee_name"].astype(str).isin(allowed_names)])

                    if (search_employee.strip() and not filtered_summary.empty):
                        allowed_names = set(filtered_summary["employee_name"].astype(str).tolist())
                        emp_type_df = (emp_type_df[emp_type_df["employee_name"].astype(str).isin(allowed_names)])

                    if not emp_type_df.empty:
                        if alt is not None:
                            bars = (alt.Chart(emp_type_df).mark_bar().encode(
                                x=alt.X("employee_name:N",title="Employee", sort=None,),
                                y=alt.Y("days:Q", title="Leave Days", stack="zero",),
                                color=alt.Color("leave_type:N", title="Leave Type",),
                                tooltip=["employee_name", "leave_type", "days",],).properties(height=350))
                            
                            st.altair_chart(bars, use_container_width=True,)
                        else:
                            pivot = (emp_type_df.pivot_table(index="employee_name", columns="leave_type", values="days", aggfunc="sum", fill_value=0,))
                            st.bar_chart(pivot)
                    else:
                        st.info("No leave data for the selected filters.")
                else:
                    st.info("No approved leave records yet.")
            else:
                st.info("No approved leave records yet.")


        # CHART 2 - Monthly Leave Headcount
        with chart_col2:
            st.markdown("##### Employees on Leave by Month")
            if month_counts:
                import calendar as _calendar
                donut_df = pd.DataFrame({"month_key": list(month_counts.keys()), "employees_on_leave":list(month_counts.values()),})
                donut_df["month"] = donut_df["month_key"].apply(lambda k:_calendar.month_abbr[int(str(k).split("-")[1])])

                if alt is not None:
                    hbar = (alt.Chart(donut_df).mark_bar().encode(
                        y=alt.Y("month:N", title="Month", sort=list(donut_df["month"]),),
                        x=alt.X("employees_on_leave:Q", title="Employees", axis=alt.Axis(format="d", tickMinStep=1,),),
                        tooltip=["month", "employees_on_leave",],).properties(height=350))
                    hbar_labels = (alt.Chart(donut_df).mark_text(dx=8, align="left",).encode(
                        y=alt.Y("month:N", sort=list(donut_df["month"]),),
                        x=alt.X("employees_on_leave:Q"),
                        text=alt.Text("employees_on_leave:Q", format="d",),))
                    st.altair_chart(hbar + hbar_labels, use_container_width=True,)
                else:
                    st.bar_chart(
                        donut_df.set_index("month")["employees_on_leave"])
            else:
                st.info("No approved leave records yet.")
    else:
        st.subheader("Record Leave for an Employee")
        employees = st.session_state.get("employees")
        if employees is None:
            from utils.sheets_client import read_table
            employees = read_table("Employees")

        if employees.empty:
            st.caption("No employees found to record leave for.")
        else:
            apply_to_all = st.checkbox("Apply to all employees", value=False)

            emp_map = dict(zip(employees["name"], employees["employee_id"]))
            selected_name = None
            if not apply_to_all:
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
                elif not apply_to_all and selected_name is None:
                    st.error("Please select an employee.")
                else:
                    status = "Approved" if approved else "Pending"
                    if apply_to_all:
                        created = []
                        errors = []
                        for _, employee in employees.iterrows():
                            try:
                                request_id, days = record_leave_request(
                                    str(employee["employee_id"]),
                                    leave_type,
                                    start_date,
                                    end_date,
                                    reason,
                                    session,
                                    status=status,
                                    approved_by=st.session_state["email"],
                                )
                                created.append((employee.get("name", ""), request_id, days))
                            except ValueError as e:
                                errors.append(f"{employee.get('name', employee.get('employee_id'))}: {e}")

                        if created:
                            st.success(f"Recorded leave for {len(created)} employees.")
                        if errors:
                            st.error("Some records failed:\n" + "\n".join(errors))
                    else:
                        request_id, days = record_leave_request(
                            emp_map[selected_name],
                            leave_type,
                            start_date,
                            end_date,
                            reason,
                            session,
                            status=status,
                            approved_by=st.session_state["email"],
                        )
                        st.success(
                            f"Leave request {request_id} recorded for {selected_name}. "
                            f"Duration: {days} day(s). Status: {status}."
                        )

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

    # Get pending requests
    if role == "hr_admin":
        pending = get_all_pending_requests()
    else:
        pending = get_pending_requests(st.session_state["email"])

    # No pending requests
    if not pending:
        st.caption("No pending requests.")

    # Display pending requests
    for req in pending:
        request_id = str(req["request_id"])
        attachments = get_leave_attachment(request_id)

        # Leave Approval Card
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

        # Attachments
        if attachments:
            st.markdown("##### 📎 Attachments")
            for index, file in enumerate(attachments):
                file_name = file.get("file_name", "Attachment")
                file_path = file.get("file_path")
                mime_type = file.get("mime_type", "").strip().lower()
                uploaded_date = file.get("uploaded_date", "")

                # Fallback MIME type
                if not mime_type:
                    extension = (file_name.lower().split(".")[-1])
                    mime_map = {
                        "pdf": "application/pdf",
                        "jpg": "image/jpeg",
                        "jpeg": "image/jpeg",
                        "png": "image/png",
                    }

                    mime_type = mime_map.get(extension, "application/octet-stream")

                # Missing file path
                if not file_path:
                    st.error(f"{file_name}: "
                        "File path unavailable.")
                    continue

                # Attachment information
                col1, col2, col3 = st.columns([4, 1, 1])

                with col1:
                    if mime_type == "application/pdf":
                        icon = "📄"

                    elif mime_type.startswith("image/"):
                        icon = "🖼️"
                    else:
                        icon = "📎"

                    st.write(f"{icon} **{file_name}**")

                    if uploaded_date:
                        st.caption(f"Uploaded: " f"{uploaded_date}")

                # Load file from Supabase
                try:
                    file_bytes = download_file(file_path)

                    # Preview button
                    with col2:
                        preview_key = (f"preview_mc_" f"{request_id}_" f"{index}")
                        preview = st.toggle("Preview", key=preview_key)

                    # Download button
                    with col3:
                        st.download_button("Download", data = file_bytes, file_name = file_name, mime = mime_type,
                            key=(f"download_mc_" f"{request_id}_" f"{index}"), use_container_width=True,)

                    # Preview - PDF
                    if preview:
                        if mime_type == "application/pdf":

                            import base64
                            base64_file = (base64.b64encode(file_bytes).decode("utf-8"))
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

                            st.markdown(pdf_display, unsafe_allow_html=True,)

                        # JPG / JPEG / PNG
                        elif mime_type in [
                            "image/jpeg",
                            "image/png",
                        ]:
                            st.image(file_bytes, use_container_width=True,)

                        # Unsupported file type
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

                    st.caption(f"Error: {e}")

        # Approve / Reject
        cols = st.columns([1, 1])
        with cols[0]:
            if st.button("Approve", key=f"appr_{request_id}", use_container_width=True,):
                approve_request(request_id, st.session_state["email"],)
                st.rerun()

        with cols[1]:
            if st.button("Reject", key=f"rej_{request_id}", use_container_width=True,):
                reject_request(request_id, st.session_state["email"],)
                st.rerun()

# ---------- Employee Leave History ----------
else:
    sub_view = st.radio("Sub-view", ["Pending", "History"], horizontal=True, label_visibility="collapsed")
    all_requests = get_all_requests()

    # Request card function
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

    # Pending
    if sub_view == "Pending":
        rows = [r for r in all_requests if r["status"] == "Pending"]
        st.subheader("Pending Requests")
        if not rows:
            st.caption("Nothing to show.")
        else:
            for req in rows:
                _render_request_card(req)

    # History
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

            # Employee List
            if selected_employee is None:
                st.caption("Select an employee to view their individual leave history.")
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
            # Individual history
            else:
                if st.button("← Back to employee list"):
                    st.session_state.pop("history_selected_employee", None)
                    st.rerun()
                st.markdown(f"#### {selected_employee}'s Leave History")
                for req in history_rows:
                    if req.get("employee_name", req["employee_id"]) == selected_employee:
                        _render_request_card(req)