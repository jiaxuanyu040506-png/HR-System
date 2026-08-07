import streamlit as st
import pandas as pd
from datetime import date, datetime
from utils.ui import inject_css, render_nav_sidebar
from utils.auth import require_role
from utils.sheets_client import read_table
from utils.attendance import (
    get_attendance_for_month, get_monthly_summary, get_yearly_summary,
    get_attendance_matrix_for_employee_year, mark_attendance,
    clear_attendance_override, get_attendance_matrix, get_attendance_matrices_for_year,
    get_rest_day_columns, MANUAL_STATUSES, STATUS_CODES,
)
from utils.leave_calc import get_leave_balance, get_leave_history
from utils.excel_export import attendance_month_to_excel, attendance_year_to_excel

inject_css()
require_role(["hr_admin"])
render_nav_sidebar(st.session_state["role"])
st.title("Attendance")
# st.caption(
#     "Every day defaults automatically: Present on working days, Rest Day on "
#     "weekends, Public Holiday on holidays, and On Leave when there's an "
#     "approved leave request covering that date. You only need to mark "
#     "actual exceptions (Absent / Late / Half Day) below."
# )

employees = read_table("Employees")
if employees.empty:
    st.caption("No employees found yet.")
    st.stop()

name_to_id = dict(zip(employees["name"], employees["employee_id"]))

view_mode = st.segmented_control(
    "View", ["Individual Employee", "Monthly Overview (All Employees)"],
    default = "Individual Employee",
)
st.divider()

LEGEND_ITEMS = [
    ("/", "Present"), ("AL", "Annual Leave"), ("MC", "Medical Leave"), ("UPL", "Unpaid Leave"),
    ("SL", "Special Leave"), ("ML", "Maternity Leave"), ("MRL", "Married Leave"), ("PH", "Public Holiday"), ("grey column", "Rest Day"),
]
legend_text = "  ·  ".join(f"**{code}** = {label}" for code, label in LEGEND_ITEMS)


def _grey_rest_days(matrix: pd.DataFrame, rest_day_columns: list[int]):
    """Styler that greys out whole rest-day columns on screen, matching the Excel export."""
    return matrix.style.apply(
        lambda col: ["background-color: #d9d9d9" if col.name in rest_day_columns else "" for _ in col],
        axis=0,
    )


# ============================================================
# Individual Employee — drill-down + mark/clear exceptions
# ============================================================
# if view_mode == "Individual Employee":
#     col1, col2 = st.columns([2, 1])

#     selected_name = col1.selectbox(
#         "Employee",
#         list(name_to_id.keys())
#     )

#     selected_year = col2.number_input(
#         "Year",
#         min_value=2000,
#         max_value=2100,
#         value=date.today().year,
#         step=1,
#     )

#     emp_id = name_to_id[selected_name]

#     st.divider()

#     summary = get_yearly_summary(emp_id, selected_name, selected_year,)
#     summary_items = list(summary.items())
#     for row in range(0, len(summary_items), 4):
#         cols = st.columns(4)
#         for col, (status, count) in zip(cols, summary_items[row:row+4]):
#             col.metric(status, count)

#     st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
#     matrix = get_attendance_matrix_for_employee_year(emp_id, selected_name, selected_year,)
#     st.dataframe(matrix, use_container_width=True,)

#     st.divider()

#     # Get current employee leave balance
#     # employee_id = st.session_state["employee_id"]
#     # year = datetime.now().year

#     balance = get_leave_balance(emp_id, selected_year,)

#     if balance:
#         total_leave = float(balance["annual_total"])
#         leave_taken = float(balance["annual_used"])
#         leave_balance = total_leave - leave_taken
#     else:
#         total_leave = 0
#         leave_taken = 0
#         leave_balance = 0

#     # st.write(st.session_state)
#     c1, c2, c3 = st.columns(3)

#     c1.metric(
#         "Total Leave Entitled",
#         f"{total_leave:.1f} Days"
#     )

#     c2.metric(
#         "Leave Taken",
#         f"{leave_taken:.1f} Days"
#     )

#     c3.metric(
#         "Balance",
#         f"{leave_balance:.1f} Days"
#     )

#     st.markdown("""
#                 ### Symbols
#                 | Code | Meaning |
#                 |------|---------|
#                 | / | Present |
#                 | AL | Annual Leave |
#                 | MC | Medical Leave |
#                 | SL | Special Leave |
#                 | UPL | Unpaid Leave |
#                 | ML | Maternity Leave |
#                 | MRL | Married Leave |
#                 | PH | Public Holiday |
#                 | A | Absent |
#                 | L | Late |
#                 | HD | Half Day |
#                 """)

    # st.subheader("Mark an Exception")
    # with st.form("mark_attendance_form"):
    #     exception_date = st.date_input(
    #         "Date", value=date.today(),
    #         min_value=date(selected_year, selected_month, 1),
    #         max_value=date(selected_year, selected_month, pd.Timestamp(selected_year, selected_month, 1).days_in_month),
    #     )
    #     status = st.selectbox("Status", MANUAL_STATUSES)
    #     remarks = st.text_input("Remarks (optional)")
    #     submitted = st.form_submit_button("Save")

    # if submitted:
    #     mark_attendance(emp_id, selected_name, exception_date, status, remarks)
    #     st.success(f"Marked {exception_date} as {status}.")
    #     st.rerun()

    # with st.expander("↩️ Clear an exception (revert a date back to auto-derived)"):
    #     manual_rows = [r for r in rows if r["source"] == "manual"]
    #     if not manual_rows:
    #         st.caption("No manual exceptions this month.")
    #     else:
    #         options = {f"{r['date']} — {r['status']}": r["date"] for r in manual_rows}
    #         pick = st.selectbox("Select entry", list(options.keys()), key="clear_exception_select")
    #         if st.button("Clear this exception"):
    #             clear_attendance_override(emp_id, date.fromisoformat(options[pick]))
    #             st.success("Cleared — that date will now show its auto-derived status.")
    #             st.rerun()

if view_mode == "Individual Employee":
    
    # Employee Selection
    st.markdown("### 👤 Employee Attendance")

    col1, col2 = st.columns([3, 1])
    selected_name = col1.selectbox("Employee",list(name_to_id.keys()),label_visibility="collapsed")
    selected_year = col2.number_input("Year", min_value=2000, max_value=2100, value=date.today().year,step=1, label_visibility="collapsed")
    emp_id = name_to_id[selected_name]

    st.caption(f"Attendance record for **{selected_name}** ({selected_year})")
    st.divider()

    # Attendance Summary
    st.markdown("### 📊 Attendance Summary")

    summary = get_yearly_summary(emp_id,selected_name,selected_year,)

    if summary:
        # summary_items = list(summary.items())
        # cols = st.columns(len(summary_items))
        # for col, (status, count) in zip(cols,summary_items):
        #     col.metric(label=status,value=count)
        display_order = ["Present", "AL", "MC", "Public Holiday", "Rest Day",]
        summary_items = [
            (status, summary[status])
            for status in display_order
            if status in summary
        ]
        cols = st.columns(len(summary_items))
        for col, (status, count) in zip(cols,summary_items):
            col.metric(label=status,value=count)
    else:
        st.info("No attendance records found.")

    st.markdown("<div style='height:20px'></div>",unsafe_allow_html=True)

    # Attendance Matrix
    st.markdown("### 📅 Attendance Record")

    matrix = get_attendance_matrix_for_employee_year(emp_id,selected_name,selected_year,)
    with st.container(border=True):
        if matrix is not None and not matrix.empty:
            st.dataframe(matrix,use_container_width=True,height=420)
        else:
            st.info("No attendance data available.")
    st.divider()

    # Leave Impact
    st.markdown("### 🏖 Leave Impact")
    balance = get_leave_balance(emp_id,selected_year,)
    if balance:
        annual_used = float(balance.get("annual_used", 0) or 0)
        medical_used = float(balance.get("medical_used", 0) or 0)
        unpaid_used = float(balance.get("unpaid_used", 0) or 0)
    else:
        annual_used = 0
        medical_used = 0
        unpaid_used = 0

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric( "Annual Leave Taken",f"{annual_used:.1f} days")
    with c2:
        st.metric("Medical Leave Taken",f"{medical_used:.1f} days")
    with c3:
        st.metric("Unpaid Leave Taken",f"{unpaid_used:.1f} days")

    st.markdown("<div style='height:20px'></div>",unsafe_allow_html=True)

    # Updated 7 Aug, 2026 - Added detailed leave history accordion with month filter
    with st.expander("🗂 Detailed Leave History", expanded=False):
        history_month = st.selectbox(
            "Month",
            list(range(1, 13)),
            index=datetime.now().month - 1,
            format_func=lambda m: date(2000, m, 1).strftime("%B"),
            key="leave_history_month",
        )

        history_rows = get_leave_history(
            year=selected_year,
            month=history_month,
            employee_id=emp_id,
        )

        if history_rows:
            history_df = pd.DataFrame(history_rows)
            display_cols = ["leave_type", "start_date", "end_date", "days", "status", "reason"]
            history_df = history_df[[c for c in display_cols if c in history_df.columns]]
            st.dataframe(history_df, use_container_width=True, hide_index=True)

            # Updated 7 Aug, 2026 - Added leave totals summary below the history table
            if "days" in history_df.columns and "leave_type" in history_df.columns:
                history_df["days"] = pd.to_numeric(history_df["days"], errors="coerce").fillna(0)

                summary_df = (
                    history_df.groupby("leave_type", dropna=False)["days"]
                    .sum()
                    .reset_index()
                    .rename(columns={"days": "days_taken"})
                )
                summary_df["days_taken"] = summary_df["days_taken"].round(1)

                total_row = pd.DataFrame([{
                    "leave_type": "Total",
                    "days_taken": round(float(summary_df["days_taken"].sum()), 1),
                }])

                summary_df = pd.concat([summary_df, total_row], ignore_index=True)

                st.caption("Leave totals for selected month")
                st.dataframe(summary_df, use_container_width=True, hide_index=True)

        else:
            st.info(f"No leave history found for {date(2000, history_month, 1).strftime('%B')} {selected_year}.")

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # Attendance Symbols
    with st.expander("📖 Attendance Symbols"):
        st.markdown(
            """
            | Code | Meaning |
            |------|---------|
            | `/` | Present |
            | AL | Annual Leave |
            | MC | Medical Leave |
            | SL | Special Leave |
            | UPL | Unpaid Leave |
            | ML | Maternity Leave |
            | MRL | Married Leave |
            | PH | Public Holiday |
            | A | Absent |
            | L | Late |
            | HD | Half Day |
            """
        )

# ============================================================
# Monthly Overview — everyone, one grid; full-year Excel lives here too
# ============================================================
else:
    col1, col2 = st.columns(2)
    selected_year = col1.number_input("Year", min_value=2000, max_value=2100, value=date.today().year, step=1, key="mo_year")
    selected_month = col2.selectbox(
        "Month", list(range(1, 13)), index=date.today().month - 1,
        format_func=lambda m: date(2000, m, 1).strftime("%B"), key="mo_month",
    )
    st.caption(legend_text)

    matrix = get_attendance_matrix(selected_year, selected_month)
    rest_day_columns = get_rest_day_columns(selected_year, selected_month)
    st.dataframe(_grey_rest_days(matrix, rest_day_columns), use_container_width=True)

    excel_bytes = attendance_month_to_excel(matrix, selected_year, selected_month, rest_day_columns)
    st.download_button(
        f"⬇️ Download {date(2000, selected_month, 1).strftime('%B')} {selected_year} (Excel)",
        excel_bytes,
        file_name=f"attendance_{selected_year}_{selected_month:02d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.divider()
    st.markdown(f"##### Want the whole year of {selected_year} instead?")
    st.caption("Generates one workbook with all 12 months, one sheet each (same grid as above).")
    if st.button(f"📊 Generate full-year Excel for {selected_year}"):
        with st.spinner("Building the workbook — this reads a full year of data, may take a moment..."):
            matrices = get_attendance_matrices_for_year(selected_year)
            rest_days_by_month = {m: get_rest_day_columns(selected_year, m) for m in range(1, 13)}
            year_excel_bytes = attendance_year_to_excel(matrices, selected_year, rest_days_by_month)
        st.download_button(
            f"⬇️ Download full year {selected_year} (Excel, 12 sheets)",
            year_excel_bytes,
            file_name=f"attendance_{selected_year}_full_year.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
